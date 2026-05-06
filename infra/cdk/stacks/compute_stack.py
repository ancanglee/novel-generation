"""05-ComputeStack: ECS Cluster, ECR, Services, ALB."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from constructs import Construct

from config import EnvConfig
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

        # Target groups + services
        self.api_service = self._make_fargate_service(
            name="api-service",
            cfg=cfg,
            vpc=network.vpc,
            security_group=network.sg_ecs_api,
            task_role=identity.api_task_role,
            exec_role=identity.ecs_exec_role,
            cpu=1024,
            memory_mb=2048,
            port=8000,
            spot=False,
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
            exec_role=identity.ecs_exec_role,
            cpu=512,
            memory_mb=1024,
            port=3000,
            spot=False,
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
            exec_role=identity.ecs_exec_role,
            cpu=256,
            memory_mb=512,
            port=3001,
            spot=False,
        )

        # Workers (no ALB, Spot)
        self.worker_services: dict[str, ecs.FargateService] = {}
        for wt in ["analysis", "generation", "critic", "consistency", "moderation"]:
            self.worker_services[wt] = self._make_worker_service(
                wt, cfg, network.vpc, network.sg_ecs_worker,
                identity.worker_roles[wt], identity.ecs_exec_role,
            )

        # ---- Listener rules ----------------------------------------------
        self.listener.add_action(
            "DefaultToFront",
            action=elbv2.ListenerAction.forward([self.api_service["target_group"]]),
        )

        self.listener.add_action(
            "FrontRoute",
            priority=100,
            conditions=[elbv2.ListenerCondition.path_patterns(["/healthz", "/"])],
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
    ) -> dict:
        task_def = ecs.FargateTaskDefinition(
            self,
            f"{name.title().replace('-', '')}TaskDef",
            cpu=cpu,
            memory_limit_mib=memory_mb,
            task_role=task_role,
            execution_role=exec_role,
        )
        task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_registry(
                "public.ecr.aws/amazonlinux/amazonlinux:2023"  # placeholder before first push
            ),
            logging=ecs.LogDriver.aws_logs(stream_prefix=name),
            port_mappings=[ecs.PortMapping(container_port=port)],
            environment={"ENV": cfg.env_name, "SERVICE_NAME": name},
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
        task_def.add_container(
            "Container",
            image=ecs.ContainerImage.from_registry(
                "public.ecr.aws/amazonlinux/amazonlinux:2023"
            ),
            logging=ecs.LogDriver.aws_logs(stream_prefix=f"worker-{wt}"),
            environment={"ENV": cfg.env_name, "WORKER_TYPE": wt},
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
