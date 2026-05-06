"""U3 Understanding Agents extensions to U1 stacks.

Mutates existing U1 stacks to add U3-specific resources. Keeping these in a helper
module (rather than editing U1 stack files) preserves layering and makes U3 diffs
reviewable in isolation.
"""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_ssm as ssm
from aws_cdk import aws_stepfunctions as sfn
from constructs import Construct


def extend_data_stack(stack: Construct, cfg) -> None:
    """Add 5 U3-specific SSM parameters."""
    for name, value in [
        ("titan-embed-model", "amazon.titan-embed-text-v2:0"),
        ("titan-embed-dim", "1024"),
        ("supervisor-max-steps", "50"),
        ("chapter-retry-max", "3"),
        ("memory-write-timeout-ms", "2000"),
    ]:
        ssm.StringParameter(
            stack,
            f"U3Param{name.replace('-', '').title()}",
            parameter_name=f"/novelgen/{cfg.env_name}/config/{name}",
            string_value=value,
        )


def extend_identity_stack(stack: Construct, cfg, worker_analysis_role: iam.Role) -> None:
    """Augment worker-analysis Role with Neptune / AOSS / AgentCore permissions."""
    worker_analysis_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:Converse",
                "bedrock-agentcore:InvokeAgent",
                "bedrock-agentcore:CreateAgent",
                "bedrock-agentcore:DescribeAgent",
                "bedrock-agentcore:PutMemoryItem",
                "bedrock-agentcore:GetMemoryItem",
                "bedrock-agentcore:QueryMemory",
                "neptune-db:ReadDataViaQuery",
                "neptune-db:WriteDataViaQuery",
                "aoss:APIAccessAll",
                "aoss:BatchGetCollection",
            ],
            resources=["*"],
        )
    )


def extend_messaging_stack(
    stack: Construct,
    cfg,
    *,
    jobs_table,
    analysis_queue,
    sfn_role: iam.Role,
) -> tuple[_lambda.Function, sfn.StateMachine]:
    """Add load-novel-metadata Lambda and replace the skeleton AnalysisStateMachine."""
    metadata_fn = _lambda.Function(
        stack,
        "U3LoadNovelMetadata",
        function_name=f"{cfg.prefix}-load-novel-metadata",
        runtime=_lambda.Runtime.PYTHON_3_12,
        handler="handler.handler",
        code=_lambda.Code.from_asset("../../lambdas/load-novel-metadata"),
        timeout=cdk.Duration.seconds(30),
        environment={
            "TENANCY_TABLE": cfg.ddb_prefix + "_tenancy",
        },
    )

    asl_path = Path(__file__).resolve().parent.parent / "asl" / "analysis_workflow.json"
    with open(asl_path, encoding="utf-8") as fh:
        asl_body = fh.read()

    state_machine = sfn.StateMachine(
        stack,
        "U3AnalysisStateMachine",
        state_machine_name=f"{cfg.prefix}-analysis",
        definition_body=sfn.DefinitionBody.from_string(asl_body),
        role=sfn_role,
        timeout=cdk.Duration.hours(2),
        tracing_enabled=False,
    )
    # Grant SFN the ability to invoke the Lambda + send SQS
    metadata_fn.grant_invoke(sfn_role)
    analysis_queue.grant_send_messages(sfn_role)

    return metadata_fn, state_machine


def extend_observability_stack(stack: Construct, cfg, *, alerts_topic) -> None:
    """Add 5 U3 Alarms."""
    alarms_spec = [
        ("U3AnalysisTimeoutP95", "JobDurationMs", 900000, "p95"),
        ("U3SupervisorDrift", "SupervisorStepCount", 40, "Maximum"),
        ("U3MemoryWriteFailureHigh", "MemoryWriteFailure", 20, "Sum"),
        ("U3NeptuneSlowUpsert", "NeptuneLatencyMs", 500, "p95"),
        ("U3ChapterPartialRateHigh", "ChapterProcessingMs", 10, "Sum"),
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


def extend_agentcore_stack(stack: Construct, cfg) -> None:
    """Declare AgentCore Memory namespace pattern + Observability project name via SSM."""
    ssm.StringParameter(
        stack,
        "U3AgentCoreMemoryNsPattern",
        parameter_name=f"/novelgen/{cfg.env_name}/agentcore/memory-namespace-pattern",
        string_value="{team_id}:{novel_id}",
    )
    ssm.StringParameter(
        stack,
        "U3AgentCoreObsProject",
        parameter_name=f"/novelgen/{cfg.env_name}/agentcore/observability-project",
        string_value=f"novelgen-{cfg.env_name}",
    )
