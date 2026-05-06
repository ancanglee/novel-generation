"""07-ObservabilityStack: Log Groups, Metric Filters, Alarms, SNS, Aggregator Lambdas."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as sns_subs
from constructs import Construct

from config import EnvConfig
from stacks.compute_stack import ComputeStack
from stacks.data_stack import DataStack


class ObservabilityStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        data: DataStack,
        compute: ComputeStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        # ---- SNS topic for alerts -----------------------------------------
        self.alerts_topic = sns.Topic(
            self,
            "AlertsTopic",
            topic_name=f"{cfg.prefix}-admin-alerts",
            display_name="NovelGen admin alerts",
        )
        self.alerts_topic.add_subscription(sns_subs.EmailSubscription(cfg.alert_email))

        # ---- EMF source log group -----------------------------------------
        self.emf_log_group = logs.LogGroup(
            self,
            "EmfLogGroup",
            log_group_name=f"/{cfg.prefix}/metrics/emf",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # ---- Metric filters (extract from EMF log stream) -----------------
        # Note: Powertools emits EMF that CloudWatch already reads natively;
        # these filters provide additional extraction for non-EMF log lines if needed.
        for metric in [
            ("BedrockErrors", '{ $.metric_type = "bedrock_error" }'),
            ("JobDurationCustom", '{ $.event = "job.done" }'),
        ]:
            logs.MetricFilter(
                self,
                f"Filter{metric[0]}",
                log_group=self.emf_log_group,
                filter_pattern=logs.FilterPattern.string_value("$.metric_type", "=", "bedrock_error"),
                metric_namespace="NovelGen",
                metric_name=metric[0],
                metric_value="1",
            )

        # ---- Alarms -------------------------------------------------------
        self._make_alarm("JobTokenSpike", "NovelGen/BedrockTokensOutput", 200000, cw.Statistic.MAXIMUM)
        self._make_alarm("TeamHourlyTokens", "NovelGen/BedrockTokensOutput", 500000, cw.Statistic.SUM)
        self._make_alarm("CrossTeamDeniedHigh", "NovelGen/CrossTeamDenied", 10, cw.Statistic.SUM)
        self._make_alarm(
            "Api5xxHigh",
            "AWS/ApplicationELB",
            1.0,
            cw.Statistic.AVERAGE,
            metric_name="HTTPCode_ELB_5XX_Count",
            dimensions={"LoadBalancer": compute.alb.load_balancer_full_name},
        )
        self._make_alarm(
            "EcsApiUnhealthy",
            "AWS/ApplicationELB",
            0.5,
            cw.Statistic.AVERAGE,
            metric_name="UnHealthyHostCount",
            dimensions={"LoadBalancer": compute.alb.load_balancer_full_name},
        )

        # ---- Daily cost aggregator Lambda ---------------------------------
        self.cost_aggregator_fn = _lambda.Function(
            self,
            "CostAggregatorFn",
            function_name=f"{cfg.prefix}-cost-aggregator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../../lambdas/daily-cost-aggregator"),
            timeout=cdk.Duration.minutes(5),
            environment={"CONFIG_TABLE": data.config_table.table_name, "ENV": cfg.env_name},
        )
        data.config_table.grant_read_write_data(self.cost_aggregator_fn)
        self.cost_aggregator_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:GetMetricData", "cloudwatch:ListMetrics"], resources=["*"]
            )
        )

        # ---- Daily audit archiver Lambda ----------------------------------
        self.audit_archiver_fn = _lambda.Function(
            self,
            "AuditArchiverFn",
            function_name=f"{cfg.prefix}-audit-archiver",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../../lambdas/daily-audit-archiver"),
            timeout=cdk.Duration.minutes(15),
            environment={
                "AUDIT_TABLE": data.audit_table.table_name,
                "ARCHIVE_BUCKET": data.audit_archive_bucket.bucket_name,
                "ENV": cfg.env_name,
            },
        )
        data.audit_table.grant_read_data(self.audit_archiver_fn)
        data.audit_archive_bucket.grant_put(self.audit_archiver_fn)

        # ---- Schedule via EventBridge rules (cron) -------------------------
        events.Rule(
            self,
            "DailyCostRule",
            rule_name=f"{cfg.prefix}-daily-cost",
            schedule=events.Schedule.cron(minute="0", hour="2"),
            targets=[targets.LambdaFunction(self.cost_aggregator_fn)],
        )
        events.Rule(
            self,
            "DailyAuditRule",
            rule_name=f"{cfg.prefix}-daily-audit",
            schedule=events.Schedule.cron(minute="0", hour="3"),
            targets=[targets.LambdaFunction(self.audit_archiver_fn)],
        )

    def _make_alarm(
        self,
        name: str,
        namespace: str,
        threshold: float,
        statistic: cw.Statistic,
        metric_name: str | None = None,
        dimensions: dict[str, str] | None = None,
    ) -> None:
        metric = cw.Metric(
            namespace=namespace,
            metric_name=metric_name or name,
            statistic=statistic.name if isinstance(statistic, cw.Statistic) else str(statistic),
            period=cdk.Duration.minutes(5),
            dimensions_map=dimensions or {},
        )
        alarm = cw.Alarm(
            self,
            f"Alarm{name}",
            alarm_name=f"novelgen-{name}",
            metric=metric,
            threshold=threshold,
            evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(cw_actions.SnsAction(self.alerts_topic))
