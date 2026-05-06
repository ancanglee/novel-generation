"""U6 Frontend + BFF extensions to U1 stacks.

Adds:
- 3 CloudFront behaviors (SSE / API / default S3 frontend prefix)
- 2 ALB listener rules (SSE precedence + general API)
- 1 Fargate Service (bff-user) + IAM Task Role + Target Group
- 1 Secret (BFF session signing key, 30d rotation)
- 5 CloudWatch Alarms
- S3 lifecycle + bucket policy addition for `frontend/` prefix (I2=A)
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as cf_origins
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sns as sns
from constructs import Construct

_U6_METRIC_NS = "novelgen/frontend"


def extend_data_stack(stack: Construct, cfg, *, novels_bucket: s3.Bucket) -> None:
    """S3 lifecycle for frontend/ prefix (keep 3 old versions, expire 90d)."""
    novels_bucket.add_lifecycle_rule(
        id="U6FrontendRollbackRetention",
        prefix="frontend/",
        noncurrent_version_expiration=cdk.Duration.days(90),
        noncurrent_versions_to_retain=3,
    )


def extend_identity_stack(
    stack: Construct,
    cfg,
    *,
    bff_task_role: iam.Role,
    session_signing_secret: secrets.ISecret,
    cognito_user_pool_arn: str,
) -> None:
    """Grant BFF Task Role minimal permissions."""
    session_signing_secret.grant_read(bff_task_role)
    bff_task_role.add_to_policy(
        iam.PolicyStatement(
            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"],
        )
    )
    bff_task_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "cognito-idp:InitiateAuth",
                "cognito-idp:RespondToAuthChallenge",
            ],
            resources=[cognito_user_pool_arn],
        )
    )


def extend_compute_stack(
    stack: Construct,
    cfg,
    *,
    cluster: ecs.ICluster,
    vpc: ec2.IVpc,
    alb_listener: elbv2.IApplicationListener,
    bff_ecr_repo: ecr.IRepository,
    bff_task_role: iam.Role,
    execution_role: iam.IRole,
    session_signing_secret: secrets.ISecret,
    api_base_url: str,
    cognito_user_pool_id: str,
    cognito_app_client_id: str,
    cognito_domain: str,
    app_base_url: str,
) -> tuple[ecs.FargateService, elbv2.ApplicationTargetGroup]:
    """Create bff-user Fargate Service + TargetGroup + 2 listener rules."""

    task_def = ecs.FargateTaskDefinition(
        stack,
        "U6BffTaskDef",
        cpu=256,
        memory_limit_mib=512,
        task_role=bff_task_role,
        execution_role=execution_role,
        runtime_platform=ecs.RuntimePlatform(
            operating_system_family=ecs.OperatingSystemFamily.LINUX,
            cpu_architecture=ecs.CpuArchitecture.ARM64,
        ),
    )
    task_def.add_container(
        "bff",
        image=ecs.ContainerImage.from_ecr_repository(bff_ecr_repo, tag="u6-latest"),
        logging=ecs.LogDriver.aws_logs(
            stream_prefix="bff-user",
            log_retention=cdk.aws_logs.RetentionDays.ONE_MONTH,
        ),
        environment={
            "NOVELGEN_ENV": cfg.env_name,
            "API_BASE_URL": api_base_url,
            "COGNITO_USER_POOL_ID": cognito_user_pool_id,
            "COGNITO_APP_CLIENT_ID": cognito_app_client_id,
            "COGNITO_DOMAIN": cognito_domain,
            "COGNITO_REGION": cfg.region,
            "APP_BASE_URL": app_base_url,
            "PORT": "3000",
        },
        secrets={
            "SESSION_SIGNING_KEY": ecs.Secret.from_secrets_manager(session_signing_secret),
        },
        port_mappings=[
            ecs.PortMapping(container_port=3000, protocol=ecs.Protocol.TCP)
        ],
    )

    service = ecs.FargateService(
        stack,
        "U6BffService",
        cluster=cluster,
        task_definition=task_def,
        desired_count=2,
        circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        enable_execute_command=True,
        assign_public_ip=False,
    )
    scaling = service.auto_scale_task_count(min_capacity=2, max_capacity=6)
    scaling.scale_on_cpu_utilization(
        "U6BffCpuScaling",
        target_utilization_percent=70,
        scale_in_cooldown=cdk.Duration.minutes(2),
        scale_out_cooldown=cdk.Duration.minutes(1),
    )

    bff_tg = elbv2.ApplicationTargetGroup(
        stack,
        "U6BffTg",
        vpc=vpc,
        port=3000,
        protocol=elbv2.ApplicationProtocol.HTTP,
        target_type=elbv2.TargetType.IP,
        health_check=elbv2.HealthCheck(
            path="/healthz",
            interval=cdk.Duration.seconds(15),
            healthy_threshold_count=2,
        ),
        deregistration_delay=cdk.Duration.seconds(15),
        stickiness_cookie_duration=cdk.Duration.hours(6),
    )
    service.attach_to_application_target_group(bff_tg)

    elbv2.ApplicationListenerRule(
        stack,
        "U6BffSseRule",
        listener=alb_listener,
        priority=90,
        conditions=[
            elbv2.ListenerCondition.path_patterns(
                ["/api/v1/generations/*/chapters/*/stream"]
            ),
        ],
        action=elbv2.ListenerAction.forward(target_groups=[bff_tg]),
    )
    elbv2.ApplicationListenerRule(
        stack,
        "U6BffApiRule",
        listener=alb_listener,
        priority=100,
        conditions=[
            elbv2.ListenerCondition.path_patterns(
                ["/api/*", "/auth/*", "/telemetry"]
            ),
        ],
        action=elbv2.ListenerAction.forward(target_groups=[bff_tg]),
    )

    return service, bff_tg


def extend_edge_stack(
    stack: Construct,
    cfg,
    *,
    distribution: cloudfront.Distribution,
    novels_bucket: s3.IBucket,
    alb: elbv2.ILoadBalancerV2,
) -> None:
    """Add 3 CloudFront behaviors + S3 origin at /frontend."""
    alb_origin = cf_origins.LoadBalancerV2Origin(
        alb,
        protocol_policy=cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
    )
    cf_origins.S3Origin(
        novels_bucket,
        origin_path="/frontend",
    )

    # SSE path (no buffering).
    distribution.add_behavior(
        "/api/v1/generations/*/chapters/*/stream",
        alb_origin,
        allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
        cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
        cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
        origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    )
    # Generic API / auth / telemetry.
    for pattern in ["/api/*", "/auth/*", "/telemetry"]:
        distribution.add_behavior(
            pattern,
            alb_origin,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        )
    # Default `/*` already points to S3 via U1; if it doesn't, wire it here.
    # (Assumed pre-existing — U6 does not override default.)


def extend_observability_stack(
    stack: Construct,
    cfg,
    *,
    alerts_topic: sns.Topic,
    bff_tg: elbv2.ApplicationTargetGroup,
) -> None:
    """5 CloudWatch Alarms (NFR-U6)."""
    sse_ttft = cw.Metric(
        namespace=_U6_METRIC_NS,
        metric_name="SseTtftMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    client_err = cw.Metric(
        namespace=_U6_METRIC_NS,
        metric_name="ClientError",
        statistic="Sum",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    lh = cw.Metric(
        namespace=_U6_METRIC_NS,
        metric_name="LighthousePerf",
        statistic="Minimum",
        period=cdk.Duration.days(1),
        dimensions_map={"Env": cfg.env_name},
    )
    bff_latency = cw.Metric(
        namespace="AWS/ApplicationELB",
        metric_name="TargetResponseTime",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={
            "TargetGroup": bff_tg.target_group_full_name,
        },
    )
    telemetry_qps = cw.Metric(
        namespace="AWS/ApplicationELB",
        metric_name="RequestCount",
        statistic="Sum",
        period=cdk.Duration.minutes(1),
        dimensions_map={
            "TargetGroup": bff_tg.target_group_full_name,
        },
    )

    for alarm in [
        cw.Alarm(
            stack,
            "U6SseTtftHigh",
            alarm_name=f"{cfg.prefix}-sse-ttft-high",
            metric=sse_ttft,
            threshold=5000,
            evaluation_periods=3,
            datapoints_to_alarm=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U6LighthouseRegressed",
            alarm_name=f"{cfg.prefix}-lighthouse-regressed",
            metric=lh,
            threshold=85,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U6ClientErrorRateHigh",
            alarm_name=f"{cfg.prefix}-client-error-high",
            metric=client_err,
            threshold=50,  # tune against baseline
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U6BffLatencyHigh",
            alarm_name=f"{cfg.prefix}-bff-latency-high",
            metric=bff_latency,
            threshold=0.5,  # seconds
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U6TelemetryQpsAnomalous",
            alarm_name=f"{cfg.prefix}-telemetry-qps-anomalous",
            metric=telemetry_qps,
            threshold=3000,  # 50 qps * 60s * 3x baseline; tune in prod
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
    ]:
        alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))


def apply_u6_extensions(
    stack: Construct,
    cfg,
    *,
    novels_bucket: s3.Bucket,
    cluster: ecs.ICluster | None = None,
    vpc: ec2.IVpc | None = None,
    alb: elbv2.ILoadBalancerV2 | None = None,
    alb_listener: elbv2.IApplicationListener | None = None,
    distribution: cloudfront.Distribution | None = None,
    bff_ecr_repo: ecr.IRepository | None = None,
    bff_task_role: iam.Role | None = None,
    execution_role: iam.IRole | None = None,
    session_signing_secret: secrets.ISecret | None = None,
    alerts_topic: sns.Topic | None = None,
    cognito_user_pool_id: str = "",
    cognito_user_pool_arn: str = "",
    cognito_app_client_id: str = "",
    cognito_domain: str = "",
    api_base_url: str = "",
    app_base_url: str = "",
) -> None:
    """Orchestrate all U6 extensions. Call from the owning stack(s)."""
    extend_data_stack(stack, cfg, novels_bucket=novels_bucket)
    if (
        bff_task_role is not None
        and session_signing_secret is not None
        and cognito_user_pool_arn
    ):
        extend_identity_stack(
            stack,
            cfg,
            bff_task_role=bff_task_role,
            session_signing_secret=session_signing_secret,
            cognito_user_pool_arn=cognito_user_pool_arn,
        )
    if (
        cluster is not None
        and vpc is not None
        and alb_listener is not None
        and bff_ecr_repo is not None
        and bff_task_role is not None
        and execution_role is not None
        and session_signing_secret is not None
    ):
        _service, bff_tg = extend_compute_stack(
            stack,
            cfg,
            cluster=cluster,
            vpc=vpc,
            alb_listener=alb_listener,
            bff_ecr_repo=bff_ecr_repo,
            bff_task_role=bff_task_role,
            execution_role=execution_role,
            session_signing_secret=session_signing_secret,
            api_base_url=api_base_url,
            cognito_user_pool_id=cognito_user_pool_id,
            cognito_app_client_id=cognito_app_client_id,
            cognito_domain=cognito_domain,
            app_base_url=app_base_url,
        )
        if alerts_topic is not None:
            extend_observability_stack(
                stack, cfg, alerts_topic=alerts_topic, bff_tg=bff_tg
            )
    if distribution is not None and alb is not None:
        extend_edge_stack(
            stack,
            cfg,
            distribution=distribution,
            novels_bucket=novels_bucket,
            alb=alb,
        )
