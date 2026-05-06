"""U7 Admin extensions to U1 stacks.

Adds:
- S3 lifecycle for `admin/` prefix (90d, 3 noncurrent versions)
- IAM: Deny Update/Delete on audit_events + CloudWatch GetMetricData + Cognito admin API
- CloudFront behavior: `/admin/*` → S3 origin path=/admin
- 3 CloudWatch Alarms (AdminAuditWriteFailureHigh / AdminRequestP95High / MonitoringAggregationSlow)

DEFERRED to V2 (per U7 decisions):
- I2=C: audit-archive bucket with Object Lock
- I3=C: Cognito Admin Group with MFA required
- F6=C: Budget / CostGuardRule resources
- D4=C: PII masking middleware
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as cf_origins
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from constructs import Construct

_ADMIN_NS = "novelgen/admin"


def extend_data_stack(stack: Construct, cfg, *, novels_bucket: s3.Bucket) -> None:
    """S3 lifecycle for admin/ prefix — keep 3 noncurrent versions for rollback, expire at 90d."""
    novels_bucket.add_lifecycle_rule(
        id="U7AdminFrontendRollback",
        prefix="admin/",
        noncurrent_version_expiration=cdk.Duration.days(90),
        noncurrent_versions_to_retain=3,
    )
    # NOTE: audit-archive bucket with Object Lock governance deferred to V2 (I2=C).


def extend_identity_stack(
    stack: Construct,
    cfg,
    *,
    api_service_role: iam.Role,
    audit_events_table: dynamodb.ITable,
    cognito_user_pool: cognito.IUserPool,
) -> None:
    """IAM: Deny audit Update/Delete + CloudWatch GetMetricData + Cognito admin API."""
    # Runtime immutability for audit_events (Layer 3 of current RBAC defense).
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=[
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:BatchWriteItem",
            ],
            resources=[audit_events_table.table_arn],
        )
    )
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "cloudwatch:GetMetricData",
                "cloudwatch:ListMetrics",
            ],
            resources=["*"],
        )
    )
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "cognito-idp:ListUsers",
                "cognito-idp:ListGroups",
                "cognito-idp:AdminDisableUser",
                "cognito-idp:AdminEnableUser",
                "cognito-idp:AdminResetUserPassword",
                "cognito-idp:AdminAddUserToGroup",
                "cognito-idp:AdminRemoveUserFromGroup",
            ],
            resources=[cognito_user_pool.user_pool_arn],
        )
    )
    # NOTE: Admin group + MFA enforcement deferred to V2 (I3=C).


def extend_edge_stack(
    stack: Construct,
    cfg,
    *,
    distribution: cloudfront.Distribution,
    novels_bucket: s3.IBucket,
) -> None:
    """Add `/admin/*` CloudFront behavior pointing to S3 /admin prefix."""
    admin_origin = cf_origins.S3Origin(novels_bucket, origin_path="/admin")
    distribution.add_behavior(
        "/admin/*",
        admin_origin,
        allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    )


def extend_observability_stack(
    stack: Construct,
    cfg,
    *,
    alerts_topic: sns.Topic,
) -> None:
    """Create 3 U7 Admin alarms."""
    audit_failure = cw.Metric(
        namespace=_ADMIN_NS,
        metric_name="AdminAuditWriteFailure",
        statistic="Sum",
        period=cdk.Duration.minutes(1),
        dimensions_map={"Env": cfg.env_name},
    )
    req_p95 = cw.Metric(
        namespace=_ADMIN_NS,
        metric_name="AdminRequestDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    mon_p95 = cw.Metric(
        namespace=_ADMIN_NS,
        metric_name="AdminRequestDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name, "Route": "/admin/monitoring/summary"},
    )

    alarms = [
        cw.Alarm(
            stack,
            "U7AdminAuditWriteFailureHigh",
            alarm_name=f"{cfg.prefix}-admin-audit-write-failure-high",
            metric=audit_failure,
            threshold=0,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U7AdminRequestP95High",
            alarm_name=f"{cfg.prefix}-admin-request-p95-high",
            metric=req_p95,
            threshold=2000,
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(
            stack,
            "U7MonitoringAggregationSlow",
            alarm_name=f"{cfg.prefix}-monitoring-aggregation-slow",
            metric=mon_p95,
            threshold=5000,
            evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
    ]
    for alarm in alarms:
        alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))


def apply_u7_extensions(
    stack: Construct,
    cfg,
    *,
    novels_bucket: s3.Bucket | None = None,
    audit_events_table: dynamodb.ITable | None = None,
    api_service_role: iam.Role | None = None,
    cognito_user_pool: cognito.IUserPool | None = None,
    distribution: cloudfront.Distribution | None = None,
    alerts_topic: sns.Topic | None = None,
) -> None:
    """Orchestrate U7 extensions across the 4 owning stacks."""
    if novels_bucket is not None:
        extend_data_stack(stack, cfg, novels_bucket=novels_bucket)
    if (
        api_service_role is not None
        and audit_events_table is not None
        and cognito_user_pool is not None
    ):
        extend_identity_stack(
            stack,
            cfg,
            api_service_role=api_service_role,
            audit_events_table=audit_events_table,
            cognito_user_pool=cognito_user_pool,
        )
    if distribution is not None and novels_bucket is not None:
        extend_edge_stack(
            stack,
            cfg,
            distribution=distribution,
            novels_bucket=novels_bucket,
        )
    if alerts_topic is not None:
        extend_observability_stack(stack, cfg, alerts_topic=alerts_topic)
