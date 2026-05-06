"""U2 Ingestion Service extensions to U1 stacks.

Each function mutates the given stack to add U2-specific resources. Keeping these in a
helper module (rather than editing the U1 stack files directly) preserves layering and
makes U2's diff reviewable in isolation. The U1 stack `__init__` calls these helpers.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from aws_cdk import custom_resources as cr
from constructs import Construct


def extend_data_stack(stack: Construct, cfg, *, novels_bucket: s3.Bucket, jobs_table) -> None:
    """Add U2 resources to the DataStack."""
    novels_bucket.add_lifecycle_rule(
        id="U2CrawlCacheExpiry",
        prefix="teams/",
        expiration=cdk.Duration.days(7),
        tag_filters={"novelgen-cache-kind": "crawl"},
    )
    novels_bucket.add_lifecycle_rule(
        id="U2UploadsTmpExpiry",
        prefix="teams/",
        expiration=cdk.Duration.days(1),
        tag_filters={"novelgen-kind": "upload-tmp"},
    )

    for name, value in [
        ("max-upload-size-mb", "200"),
        ("parse-timeout-seconds", "180"),
        ("browser-session-timeout-seconds", "60"),
        ("crawl-cache-ttl-days", "7"),
        ("search-sources-enabled", "gutenberg,ctext,wikisource,baidu,bing"),
        ("crawler-user-agent", "NovelGenBot/0.1 (+https://novelgen.example.com/bot)"),
        ("browser-max-concurrency", "10"),
    ]:
        ssm.StringParameter(
            stack,
            f"U2Param{name.replace('-', '').title()}",
            parameter_name=f"/novelgen/{cfg.env_name}/config/{name}",
            string_value=value,
        )

    # Initialize Browser concurrency counter row via CustomResource
    cr.AwsCustomResource(
        stack,
        "U2BrowserCounterInit",
        on_create=cr.AwsSdkCall(
            service="DynamoDB",
            action="putItem",
            parameters={
                "TableName": jobs_table.table_name,
                "Item": {
                    "pk": {"S": "COUNTER"},
                    "sk": {"S": "BROWSER_CONCURRENCY"},
                    "current_count": {"N": "0"},
                    "max_count": {"N": "10"},
                    "holders": {"L": []},
                },
                "ConditionExpression": "attribute_not_exists(pk)",
            },
            physical_resource_id=cr.PhysicalResourceId.of(f"{cfg.prefix}-browser-counter"),
            ignore_error_codes_matching="ConditionalCheckFailedException",
        ),
        policy=cr.AwsCustomResourcePolicy.from_statements(
            [iam.PolicyStatement(actions=["dynamodb:PutItem"], resources=[jobs_table.table_arn])]
        ),
    )


def extend_messaging_stack(stack: Construct, cfg, *, jobs_table):
    """Add ingestion SQS + EventBridge rule. Returns the queue for ComputeStack wiring."""
    dlq = sqs.Queue(
        stack,
        "U2IngestionDlq",
        queue_name=f"{cfg.prefix}-ingestion-dlq",
        retention_period=cdk.Duration.days(14),
    )
    queue = sqs.Queue(
        stack,
        "U2IngestionQueue",
        queue_name=f"{cfg.prefix}-ingestion",
        visibility_timeout=cdk.Duration.seconds(360),
        retention_period=cdk.Duration.days(4),
        dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
    )

    events.Rule(
        stack,
        "U2NovelIngestedRule",
        rule_name=f"{cfg.prefix}-novel-ingested",
        event_pattern=events.EventPattern(
            source=["novelgen.ingestion"],
            detail_type=["novel.ingested"],
        ),
    )
    return queue, dlq


def extend_identity_stack(stack: Construct, cfg) -> iam.Role:
    """Create the worker-ingestion task role and return it for ComputeStack wiring."""
    role = iam.Role(
        stack,
        "U2WorkerIngestionRole",
        role_name=f"{cfg.prefix}-worker-ingestion",
        assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    )
    role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "bedrock-agentcore:CreateBrowserSession",
                "bedrock-agentcore:DeleteBrowserSession",
                "bedrock-agentcore:GetBrowserSession",
                "bedrock:InvokeModel",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "states:SendTaskSuccess",
                "states:SendTaskFailure",
                "states:SendTaskHeartbeat",
                "events:PutEvents",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
            ],
            resources=["*"],
        )
    )
    # DynamoDB + S3 grants are applied by the caller (who holds table/bucket refs).
    return role


def extend_compute_stack(
    stack: Construct,
    cfg,
    *,
    cluster: ecs.Cluster,
    worker_role: iam.Role,
    exec_role: iam.Role,
    security_group,
    ingestion_queue_url: str,
    novels_bucket_name: str,
    tenancy_table_name: str,
    jobs_table_name: str,
) -> None:
    repo = ecr.Repository(
        stack,
        "U2WorkerIngestionRepo",
        repository_name="novelgen/worker-ingestion",
        image_scan_on_push=True,
        removal_policy=cdk.RemovalPolicy.DESTROY
        if cfg.env_name == "dev"
        else cdk.RemovalPolicy.RETAIN,
    )

    task_def = ecs.FargateTaskDefinition(
        stack,
        "U2WorkerIngestionTaskDef",
        cpu=2048,
        memory_limit_mib=4096,
        task_role=worker_role,
        execution_role=exec_role,
    )
    task_def.add_container(
        "Container",
        image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
        logging=ecs.LogDriver.aws_logs(stream_prefix="worker-ingestion"),
        environment={
            "ENV": cfg.env_name,
            "WORKER_TYPE": "ingestion",
            "INGESTION_QUEUE_URL": ingestion_queue_url,
            "NOVELS_BUCKET": novels_bucket_name,
            "TENANCY_TABLE": tenancy_table_name,
            "JOBS_TABLE": jobs_table_name,
            "INGESTION_MAX_CONCURRENCY": "5",
        },
    )
    service = ecs.FargateService(
        stack,
        "U2WorkerIngestionService",
        service_name=f"{cfg.prefix}-worker-ingestion",
        cluster=cluster,
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


def extend_observability_stack(stack: Construct, cfg, *, alerts_topic) -> None:
    alarms_spec = [
        ("U2CrawlDowngradeRate", "CrawlTierDowngraded", 30, "Sum"),
        ("U2SearchDowngradeRate", "SearchTierDowngraded", 30, "Sum"),
        ("U2BrowserOverused", "BrowserSessionCount", 100, "Sum"),
        ("U2IngestionTimeoutP95", "IngestionDurationMs", 120000, "p95"),
        ("U2RobotsBlockedHigh", "RobotsTxtBlocked", 20, "Sum"),
    ]
    for name, metric_name, threshold, statistic in alarms_spec:
        metric = cw.Metric(
            namespace="NovelGen",
            metric_name=metric_name,
            statistic=statistic,
            period=cdk.Duration.minutes(5),
        )
        alarm = cw.Alarm(
            stack,
            f"Alarm{name}",
            alarm_name=f"novelgen-{name}",
            metric=metric,
            threshold=threshold,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))
