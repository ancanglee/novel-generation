"""05-ComputeStack: ECS Cluster, ECR, Services, ALB."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from config import EnvConfig
from constructs import Construct

from stacks.data_stack import DataStack
from stacks.identity_stack import IdentityStack
from stacks.messaging_stack import MessagingStack
from stacks.network_stack import NetworkStack


class ComputeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        network: NetworkStack,
        data: DataStack,
        identity: IdentityStack,
        messaging: MessagingStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        # ---- ECR repositories ---------------------------------------------
        self.repos: dict[str, ecr.Repository] = {}
        repo_names = [
            "frontend-user",
            "frontend-admin",
            "api-service",
            "worker-analysis",
            "worker-generation",
            "worker-critic",
            "worker-consistency",
            "worker-moderation",
        ]
        for name in repo_names:
            self.repos[name] = ecr.Repository(
                self,
                f"Repo{name.title().replace('-', '')}",
                repository_name=f"novelgen/{name}",
                image_scan_on_push=True,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        max_image_count=20,
                        rule_priority=1,
                        tag_status=ecr.TagStatus.TAGGED,
                        tag_prefix_list=["v"],
                    ),
                    ecr.LifecycleRule(
                        max_image_age=cdk.Duration.days(30),
                        rule_priority=2,
                        tag_status=ecr.TagStatus.UNTAGGED,
                    ),
                ],
                removal_policy=cdk.RemovalPolicy.DESTROY if cfg.env_name == "dev" else cdk.RemovalPolicy.RETAIN,
            )

        # ---- ECS Cluster --------------------------------------------------
        # 本 stack 自建 ECS ExecutionRole，避免 identity_stack 与 compute_stack
        # 之间因 LogGroup.grant_write 形成循环依赖（identity -> compute）。
        self._local_exec_role = iam.Role(
            self, "EcsExecRole",
            role_name=f"{cfg.prefix}-ecs-exec-compute",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"{cfg.prefix}-cluster",
            vpc=network.vpc,
            container_insights=True,
            enable_fargate_capacity_providers=True,
        )

        # ---- ALB ----------------------------------------------------------
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            load_balancer_name=f"{cfg.prefix}-alb",
            vpc=network.vpc,
            internet_facing=True,
            security_group=network.sg_alb,
            idle_timeout=cdk.Duration.seconds(600),  # SSE long connections
        )

        # In dev: HTTP listener on 80 (no ACM cert). Prod should terminate TLS here.
        self.listener = self.alb.add_listener(
            "Listener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            open=True,
        )

        # Build shared business env map once; per-service additions below.
        alb_base_url = f"http://{self.alb.load_balancer_dns_name}"
        common_env: dict[str, str] = {
            "ENV": cfg.env_name,
            "NOVELGEN_ENV": cfg.env_name,
            "AWS_REGION": cfg.region,
            "AWS_DEFAULT_REGION": cfg.region,
            "TENANCY_TABLE": data.tenancy_table.table_name,
            "JOBS_TABLE": data.jobs_table.table_name,
            "CONFIG_TABLE": data.config_table.table_name,
            "AUDIT_EVENTS_TABLE": data.audit_table.table_name,
            "NOVELS_BUCKET": data.novels_bucket.bucket_name,
            "EXPORTS_BUCKET": data.exports_bucket.bucket_name,
            "CHAPTER_BUCKET": data.novels_bucket.bucket_name,
            "OUTLINE_BUCKET": data.novels_bucket.bucket_name,
            "COGNITO_USER_POOL_ID": identity.user_pool.user_pool_id,
            "COGNITO_APP_CLIENT_ID": identity.app_client.user_pool_client_id,
            "COGNITO_REGION": cfg.region,
            "ANALYSIS_QUEUE_URL": messaging.queues["analysis"].queue_url,
            "GENERATION_QUEUE_URL": messaging.queues["generation"].queue_url,
            "CRITIC_QUEUE_URL": messaging.queues["critic"].queue_url,
            "CONSISTENCY_QUEUE_URL": messaging.queues["consistency"].queue_url,
            "MODERATION_QUEUE_URL": messaging.queues["moderation"].queue_url,
            "REVIEW_QUEUE_URL": messaging.queues["review"].queue_url,
            "INGESTION_STATE_MACHINE_ARN": messaging.state_machines["ingestion"].state_machine_arn,
            "ANALYSIS_STATE_MACHINE_ARN": messaging.state_machines["analysis"].state_machine_arn,
            "OUTLINE_STATE_MACHINE_ARN": messaging.state_machines["outline"].state_machine_arn,
            "CHAPTER_STATE_MACHINE_ARN": messaging.state_machines["chapter"].state_machine_arn,
            "CONSISTENCY_STATE_MACHINE_ARN": messaging.state_machines["consistency"].state_machine_arn,
            "NEPTUNE_ENDPOINT": data.neptune_cluster.cluster_endpoint.socket_address,
            "OPENSEARCH_ENDPOINT": data.aoss_collection.attr_collection_endpoint,
            "LOG_LEVEL": "info",
        }

        # APP_BASE_URL must be the public CloudFront domain (redirect_uri origin
        # that Cognito was registered with). Pass via context: `-c user_cf_url=...`
        # Falls back to ALB URL when unset (dev-only, OAuth will fail).
        user_cf_url = self.node.try_get_context("user_cf_url") or alb_base_url
        bff_env = {
            **common_env,
            "API_BASE_URL": alb_base_url,
            "APP_BASE_URL": user_cf_url,
            "COGNITO_DOMAIN": f"{identity.user_pool_domain.domain_name}.auth.{cfg.region}.amazoncognito.com",
            "PORT": "3000",
        }
        bff_secrets = {
            "SESSION_SIGNING_KEY": ecs.Secret.from_secrets_manager(identity.session_signing_secret),
        }

        # Target groups + services
        self.api_service = self._make_fargate_service(
            name="api-service",
            cfg=cfg,
            vpc=network.vpc,
            security_group=network.sg_ecs_api,
            task_role=identity.api_task_role,
            exec_role=self._local_exec_role,
            cpu=1024,
            memory_mb=2048,
            port=8000,
            spot=False,
            env=common_env,
        )
        self.front_user_service = self._make_fargate_service(
            name="frontend-user",
            cfg=cfg,
            vpc=network.vpc,
            security_group=network.sg_ecs_front,
            task_role=iam.Role(
                self,
                "FrontUserRole",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            exec_role=self._local_exec_role,
            cpu=512,
            memory_mb=1024,
            port=3000,
            spot=False,
            env=bff_env,
            secrets=bff_secrets,
        )
        self.front_admin_service = self._make_fargate_service(
            name="frontend-admin",
            cfg=cfg,
            vpc=network.vpc,
            security_group=network.sg_ecs_front,
            task_role=iam.Role(
                self,
                "FrontAdminRole",
                assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            ),
            exec_role=self._local_exec_role,
            cpu=256,
            memory_mb=512,
            port=3001,
            spot=False,
            env={"ENV": cfg.env_name, "SERVICE_NAME": "frontend-admin"},
        )

        # Workers (no ALB, Spot)
        self.worker_services: dict[str, ecs.FargateService] = {}
        for wt in ["analysis", "generation", "critic", "consistency", "moderation"]:
            self.worker_services[wt] = self._make_worker_service(
                wt, cfg, network.vpc, network.sg_ecs_worker,
                identity.worker_roles[wt], self._local_exec_role,
                env=common_env,
            )

        # ---- Listener rules ----------------------------------------------
        self.listener.add_action(
            "DefaultToFront",
            action=elbv2.ListenerAction.forward([self.api_service["target_group"]]),
        )

        self.listener.add_action(
            "FrontRoute",
            priority=100,
            conditions=[
                elbv2.ListenerCondition.path_patterns(
                    ["/healthz", "/", "/auth/*", "/telemetry/*"]
                )
            ],
            action=elbv2.ListenerAction.forward([self.front_user_service["target_group"]]),
        )
        self.listener.add_action(
            "ApiRoute",
            priority=50,
            conditions=[elbv2.ListenerCondition.path_patterns(["/api/*"])],
            action=elbv2.ListenerAction.forward([self.api_service["target_group"]]),
        )
        self.listener.add_action(
            "AdminRoute",
            priority=30,
            conditions=[elbv2.ListenerCondition.path_patterns(["/admin/*"])],
            action=elbv2.ListenerAction.forward([self.front_admin_service["target_group"]]),
        )

        cdk.CfnOutput(self, "AlbDnsName", value=self.alb.load_balancer_dns_name)

    def _make_fargate_service(
        self,
        *,
        name: str,
        cfg: EnvConfig,
        vpc: ec2.Vpc,
        security_group: ec2.SecurityGroup,
        task_role: iam.Role,
        exec_role: iam.Role,
        cpu: int,
        memory_mb: int,
        port: int,
        spot: bool,
        env: dict[str, str] | None = None,
        secrets: dict[str, ecs.Secret] | None = None,
    ) -> dict:
        task_def = ecs.FargateTaskDefinition(
            self,
            f"{name.title().replace('-', '')}TaskDef",
            cpu=cpu,
            memory_limit_mib=memory_mb,
            task_role=task_role,
            execution_role=exec_role,
        )
        container_env = {"SERVICE_NAME": name, **(env or {})}
        task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_ecr_repository(self.repos[name], tag="latest"),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=name,
                log_group=logs.LogGroup(
                    self,
                    f"{name.title().replace('-', '')}LogGroup",
                    log_group_name=f"/novelgen/{cfg.env_name}/{name}",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=cdk.RemovalPolicy.DESTROY,
                ),
            ),
            port_mappings=[ecs.PortMapping(container_port=port)],
            environment=container_env,
            secrets=secrets or None,
        )

        service = ecs.FargateService(
            self,
            f"{name.title().replace('-', '')}Service",
            service_name=f"{cfg.prefix}-{name}",
            cluster=self.cluster,
            task_definition=task_def,
            desired_count=2 if name in ("api-service", "frontend-user") else 1,
            security_groups=[security_group],
            health_check_grace_period=cdk.Duration.seconds(60),
            capacity_provider_strategies=(
                [
                    ecs.CapacityProviderStrategy(
                        capacity_provider="FARGATE_SPOT", weight=4
                    ),
                    ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1),
                ]
                if spot
                else [ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1)]
            ),
        )

        tg = elbv2.ApplicationTargetGroup(
            self,
            f"{name.title().replace('-', '')}Tg",
            vpc=vpc,
            port=port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            targets=[service],
            health_check=elbv2.HealthCheck(
                path="/healthz",
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            deregistration_delay=cdk.Duration.seconds(30),
        )

        # Auto scaling
        scalable = service.auto_scale_task_count(
            min_capacity=2 if name in ("api-service", "frontend-user") else 1,
            max_capacity=10 if name == "api-service" else 6,
        )
        scalable.scale_on_cpu_utilization("CpuScaling", target_utilization_percent=60)

        return {"service": service, "target_group": tg, "task_def": task_def}

    def _make_worker_service(
        self,
        wt: str,
        cfg: EnvConfig,
        vpc: ec2.Vpc,
        security_group: ec2.SecurityGroup,
        task_role: iam.Role,
        exec_role: iam.Role,
        env: dict[str, str] | None = None,
    ) -> ecs.FargateService:
        cpu, mem = (2048, 4096) if wt in ("analysis", "generation") else (1024, 2048)
        task_def = ecs.FargateTaskDefinition(
            self,
            f"Worker{wt.capitalize()}TaskDef",
            cpu=cpu,
            memory_limit_mib=mem,
            task_role=task_role,
            execution_role=exec_role,
        )
        container_env = {"WORKER_TYPE": wt, **(env or {})}
        task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_ecr_repository(self.repos[f"worker-{wt}"], tag="latest"),
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=f"worker-{wt}",
                log_group=logs.LogGroup(
                    self,
                    f"Worker{wt.title().replace('-','')}LogGroup",
                    log_group_name=f"/novelgen/{cfg.env_name}/worker-{wt}",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=cdk.RemovalPolicy.DESTROY,
                ),
            ),
            environment=container_env,
        )
        service = ecs.FargateService(
            self,
            f"Worker{wt.capitalize()}Service",
            service_name=f"{cfg.prefix}-worker-{wt}",
            cluster=self.cluster,
            task_definition=task_def,
            desired_count=1,
            security_groups=[security_group],
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=4),
                ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1),
            ],
        )
        scalable = service.auto_scale_task_count(min_capacity=1, max_capacity=5)
        scalable.scale_on_cpu_utilization("CpuScaling", target_utilization_percent=70)
        return service
