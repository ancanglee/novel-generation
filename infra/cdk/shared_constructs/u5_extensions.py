"""U5 Critic & Consistency extensions to U1 stacks.

Keeps U5 resources (3 SSM + 4 CloudWatch Alarms + IAM grants) in one helper
module. The consistency.trigger EventBridge Rule lives in u4_extensions.py
(I3=C decision — the event source is U4 ChapterAgent).
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

_U5_METRIC_NS = "novelgen/critic"


def extend_data_stack(stack: Construct, cfg) -> None:
    """Add 3 U5-specific SSM parameters."""
    for name, value in [
        ("consistency-interval", "10"),
        ("conflict-rewrite-max-attempts", "3"),
        ("critic-layer2-recent-summary-count", "5"),
    ]:
        ssm.StringParameter(
            stack,
            f"U5Param{name.replace('-', '').title()}",
            parameter_name=f"/novelgen/{cfg.env_name}/config/{name}",
            string_value=value,
        )


def extend_identity_stack(
    stack: Construct,
    cfg,
    *,
    worker_critic_role: iam.Role,
    worker_consistency_role: iam.Role,
    api_role: iam.Role,
) -> None:
    """Grant Bedrock / EventBridge / SSM / AOSS / Neptune to U5 workers."""

    bedrock_model_arns = [
        f"arn:aws:bedrock:{cfg.region}::foundation-model/claude-opus-4-7*",
        f"arn:aws:bedrock:{cfg.region}::foundation-model/claude-sonnet-4-6*",
    ]

    for role in (worker_critic_role, worker_consistency_role):
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                ],
                resources=bedrock_model_arns,
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "events:PutEvents",
                    "aoss:APIAccessAll",
                    "neptune-db:ReadDataViaQuery",
                ],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{cfg.region}:{cfg.account}:parameter/novelgen/{cfg.env_name}/config/*",
                ],
            )
        )

    api_role.add_to_policy(
        iam.PolicyStatement(
            actions=["events:PutEvents"],
            resources=["*"],
        )
    )


def extend_observability_stack(
    stack: Construct,
    cfg,
    *,
    alerts_topic: sns.Topic,
) -> None:
    """Add 4 U5 CloudWatch Alarms (Critic + Consistency)."""

    critic_duration = cw.Metric(
        namespace=_U5_METRIC_NS,
        metric_name="CriticDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    consistency_duration = cw.Metric(
        namespace=_U5_METRIC_NS,
        metric_name="ConsistencyDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    critic_failures = cw.Metric(
        namespace=_U5_METRIC_NS,
        metric_name="CriticFailureCount",
        statistic="Sum",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    critic_total = cw.Metric(
        namespace=_U5_METRIC_NS,
        metric_name="CriticTotalCount",
        statistic="Sum",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    critic_failure_rate = cw.MathExpression(
        expression="IF(total > 0, (fail / total) * 100, 0)",
        using_metrics={"fail": critic_failures, "total": critic_total},
        label="Critic failure %",
        period=cdk.Duration.minutes(5),
    )
    conflict_loop = cw.Metric(
        namespace=_U5_METRIC_NS,
        metric_name="ConflictLoopDetected",
        statistic="Sum",
        period=cdk.Duration.minutes(1),
        dimensions_map={"Env": cfg.env_name},
    )

    alarms: list[cw.Alarm] = []

    alarms.append(
        cw.Alarm(
            stack,
            "U5CriticDurationHigh",
            alarm_name=f"{cfg.prefix}-critic-duration-high",
            metric=critic_duration,
            threshold=60_000,
            evaluation_periods=3,
            datapoints_to_alarm=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
    )
    alarms.append(
        cw.Alarm(
            stack,
            "U5ConsistencyDurationHigh",
            alarm_name=f"{cfg.prefix}-consistency-duration-high",
            metric=consistency_duration,
            threshold=240_000,
            evaluation_periods=3,
            datapoints_to_alarm=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
    )
    alarms.append(
        cw.Alarm(
            stack,
            "U5CriticFailureRateHigh",
            alarm_name=f"{cfg.prefix}-critic-failure-rate-high",
            metric=critic_failure_rate,
            threshold=5,
            evaluation_periods=3,
            datapoints_to_alarm=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
    )
    alarms.append(
        cw.Alarm(
            stack,
            "U5ConflictLoopDetected",
            alarm_name=f"{cfg.prefix}-conflict-loop-detected",
            metric=conflict_loop,
            threshold=0,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
    )

    for alarm in alarms:
        alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))


def apply_u5_extensions(
    stack: Construct,
    cfg,
    *,
    worker_critic_role: iam.Role | None = None,
    worker_consistency_role: iam.Role | None = None,
    api_role: iam.Role | None = None,
    alerts_topic: sns.Topic | None = None,
) -> None:
    """Convenience entrypoint — orchestrate all U5 extensions in one call.

    Callers may pass None for components that live on a different stack; those
    extensions must then be invoked separately on the owning stack.
    """
    extend_data_stack(stack, cfg)
    if (
        worker_critic_role is not None
        and worker_consistency_role is not None
        and api_role is not None
    ):
        extend_identity_stack(
            stack,
            cfg,
            worker_critic_role=worker_critic_role,
            worker_consistency_role=worker_consistency_role,
            api_role=api_role,
        )
    if alerts_topic is not None:
        extend_observability_stack(stack, cfg, alerts_topic=alerts_topic)
