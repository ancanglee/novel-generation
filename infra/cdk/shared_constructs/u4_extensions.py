"""U4 Generation Agents extensions to U1 stacks.

Exposes 5 extend_* helpers that mutate existing U1 stacks to add U4 resources:
review-queue + SNS fan-out topic + EventBridge Archive + load-generation-context
Lambda + ChapterStateMachine / OutlineStateMachine with full ASL + 3 Alarms.
"""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct


def extend_data_stack(stack: Construct, cfg, novels_bucket: s3.Bucket) -> None:
    """5 SSM + S3 NoncurrentVersion Lifecycle for chapter rewrites (NFR-3.1)."""
    for name, value in [
        ("chapter-rewrite-max", "5"),
        ("cancel-cache-ttl-seconds", "8"),
        ("chapter-target-words-default", "3000"),
        ("outline-review-timeout-seconds", "120"),
        ("chapter-retention-versions", "10"),
    ]:
        ssm.StringParameter(
            stack,
            f"U4Param{name.replace('-', '').title()}",
            parameter_name=f"/novelgen/{cfg.env_name}/config/{name}",
            string_value=value,
        )

    novels_bucket.add_lifecycle_rule(
        id="U4ChapterRewriteVersions",
        prefix="teams/",
        noncurrent_version_expiration=cdk.Duration.days(30),
        noncurrent_versions_to_retain=10,
    )


def extend_identity_stack(
    stack: Construct, cfg, worker_generation_role: iam.Role, api_role: iam.Role
) -> None:
    """Augment roles with U4 permissions."""
    worker_generation_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:Converse",
                "bedrock:ConverseStream",
                "aoss:APIAccessAll",
                "neptune-db:ReadDataViaQuery",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "states:SendTaskSuccess",
                "states:SendTaskFailure",
                "events:PutEvents",
            ],
            resources=["*"],
        )
    )
    api_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "sns:Subscribe",
                "sns:Unsubscribe",
                "sqs:CreateQueue",
                "sqs:DeleteQueue",
                "sqs:GetQueueAttributes",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:SetQueueAttributes",
                "events:ListArchives",
                "events:StartReplay",
            ],
            resources=["*"],
        )
    )


def extend_messaging_stack(
    stack: Construct,
    cfg,
    *,
    jobs_table,
    tenancy_table,
    generation_queue: sqs.Queue,
    sfn_role: iam.Role,
    consistency_queue: sqs.Queue | None = None,
) -> tuple[sqs.Queue, sns.Topic, sfn.StateMachine, sfn.StateMachine, _lambda.Function]:
    """Create U4 messaging + workflow resources."""

    review_dlq = sqs.Queue(
        stack,
        "U4ReviewDlq",
        queue_name=f"{cfg.prefix}-review-dlq",
        retention_period=cdk.Duration.days(14),
    )
    review_queue = sqs.Queue(
        stack,
        "U4ReviewQueue",
        queue_name=f"{cfg.prefix}-review",
        visibility_timeout=cdk.Duration.seconds(180),
        retention_period=cdk.Duration.days(4),
        dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=review_dlq),
    )

    topic = sns.Topic(
        stack,
        "U4GenerationEventsTopic",
        topic_name=f"{cfg.prefix}-generation-events",
        display_name="NovelGen generation events (fan-out for SSE relay)",
    )

    events.Rule(
        stack,
        "U4GenerationEventsRule",
        rule_name=f"{cfg.prefix}-generation-to-sns",
        event_pattern=events.EventPattern(source=["novelgen.generation"]),
        targets=[targets.SnsTopic(topic)],
    )

    events.CfnArchive(
        stack,
        "U4GenArchive",
        archive_name=f"{cfg.prefix}-gen-archive",
        source_arn=f"arn:aws:events:{cfg.region}:*:event-bus/default",
        retention_days=7,
        event_pattern='{"source": ["novelgen.generation"]}',
    )

    context_lambda = _lambda.Function(
        stack,
        "U4LoadGenContext",
        function_name=f"{cfg.prefix}-load-generation-context",
        runtime=_lambda.Runtime.PYTHON_3_12,
        handler="handler.handler",
        code=_lambda.Code.from_asset("../../lambdas/load-generation-context"),
        timeout=cdk.Duration.seconds(30),
        environment={
            "TENANCY_TABLE": tenancy_table.table_name,
            "JOBS_TABLE": jobs_table.table_name,
        },
    )
    tenancy_table.grant_read_data(context_lambda)
    jobs_table.grant_read_write_data(context_lambda)

    asl_dir = Path(__file__).resolve().parent.parent / "asl"
    chapter_asl = (asl_dir / "chapter_workflow.json").read_text(encoding="utf-8")
    outline_asl = (asl_dir / "outline_workflow.json").read_text(encoding="utf-8")

    chapter_sm = sfn.StateMachine(
        stack,
        "U4ChapterStateMachine",
        state_machine_name=f"{cfg.prefix}-chapter",
        definition_body=sfn.DefinitionBody.from_string(chapter_asl),
        role=sfn_role,
        timeout=cdk.Duration.hours(6),
    )
    outline_sm = sfn.StateMachine(
        stack,
        "U4OutlineStateMachine",
        state_machine_name=f"{cfg.prefix}-outline",
        definition_body=sfn.DefinitionBody.from_string(outline_asl),
        role=sfn_role,
        timeout=cdk.Duration.hours(1),
    )
    context_lambda.grant_invoke(sfn_role)
    generation_queue.grant_send_messages(sfn_role)
    review_queue.grant_send_messages(sfn_role)
    jobs_table.grant_read_write_data(sfn_role)

    # --- U5 retrofit (I3=C): consistency.trigger events are produced by U4
    # ChapterAgent, so the EventBridge Rule routing them to the U1-pre-built
    # consistency-queue belongs to U4 semantics.
    if consistency_queue is not None:
        events.Rule(
            stack,
            "U4ConsistencyTriggerRule",
            rule_name=f"{cfg.prefix}-consistency-trigger",
            event_pattern=events.EventPattern(
                source=["novelgen.chapter_agent", "novelgen.generation"],
                detail_type=["consistency.trigger"],
            ),
            targets=[targets.SqsQueue(consistency_queue)],
        )

    return review_queue, topic, chapter_sm, outline_sm, context_lambda


def extend_observability_stack(stack: Construct, cfg, *, alerts_topic: sns.Topic) -> None:
    for name, metric_name, threshold, statistic in [
        ("U4ChapterTTFTHigh", "ChapterTTFTMs", 3000, "p95"),
        ("U4ChapterGenerationSlow", "ChapterGenerationMs", 60_000, "p95"),
        ("U4CancelResponseSlow", "CancelResponseMs", 10_000, "p95"),
    ]:
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
