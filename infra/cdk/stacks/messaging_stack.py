"""04-MessagingStack: SQS × 10, EventBridge rules, Step Functions state machines."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from config import EnvConfig
from constructs import Construct

from stacks.data_stack import DataStack
from stacks.identity_stack import IdentityStack


class MessagingStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id_: str,
        *,
        cfg: EnvConfig,
        data: DataStack,
        identity: IdentityStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, id_, **kwargs)

        # ---- SQS queues (5 + 5 DLQs) --------------------------------------
        queue_names = ["analysis", "generation", "critic", "consistency", "moderation"]
        self.queues: dict[str, sqs.Queue] = {}
        self.dlqs: dict[str, sqs.Queue] = {}
        for name in queue_names:
            dlq = sqs.Queue(
                self,
                f"{name.capitalize()}Dlq",
                queue_name=f"{cfg.prefix}-{name}-dlq",
                retention_period=cdk.Duration.days(14),
            )
            q = sqs.Queue(
                self,
                f"{name.capitalize()}Queue",
                queue_name=f"{cfg.prefix}-{name}",
                visibility_timeout=cdk.Duration.seconds(360),
                retention_period=cdk.Duration.days(4),
                dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
            )
            self.queues[name] = q
            self.dlqs[name] = dlq

        # ---- EventBridge Rules --------------------------------------------
        events.Rule(
            self,
            "ChapterCompletedToCritic",
            rule_name=f"{cfg.prefix}-chapter-completed-critic",
            event_pattern=events.EventPattern(
                source=["novelgen.generation"],
                detail_type=["generation.chapter.completed"],
            ),
            targets=[targets.SqsQueue(self.queues["critic"])],
        )
        events.Rule(
            self,
            "ChapterCompletedToModeration",
            rule_name=f"{cfg.prefix}-chapter-completed-moderation",
            event_pattern=events.EventPattern(
                source=["novelgen.generation"],
                detail_type=["generation.chapter.completed"],
            ),
            targets=[targets.SqsQueue(self.queues["moderation"])],
        )

        # ---- EventBridge Scheduler (alpha) --------------------------------
        # Note: aws_scheduler is alpha in CDK; will be generally available
        cdk.CfnOutput(
            self,
            "SchedulerNote",
            value="daily-cost-aggregator & daily-audit-archiver schedules wired in ObservabilityStack lambdas",
        )

        # ---- Step Functions state machines (skeletons) --------------------
        # Each state machine: UpdateJobRunning -> <business> -> UpdateJobSucceeded/Failed
        # U2-U5 fill in the <business> branch. Here we provide the skeleton.

        self.state_machines: dict[str, sfn.StateMachine] = {}
        for sm_name, queue in [
            ("ingestion", self.queues["analysis"]),  # placeholder queue
            ("analysis", self.queues["analysis"]),
            ("outline", self.queues["generation"]),
            ("chapter", self.queues["generation"]),
            ("consistency", self.queues["consistency"]),
        ]:
            self.state_machines[sm_name] = self._make_skeleton_state_machine(
                sm_name, cfg, data, queue
            )

        cdk.CfnOutput(self, "AnalysisQueueUrl", value=self.queues["analysis"].queue_url)
        cdk.CfnOutput(
            self,
            "AnalysisSMArn",
            value=self.state_machines["analysis"].state_machine_arn,
        )

    def _make_skeleton_state_machine(
        self,
        name: str,
        cfg: EnvConfig,
        data: DataStack,
        default_queue: sqs.Queue,
    ) -> sfn.StateMachine:
        """Skeleton SM: UpdateJobRunning -> SendMessage waitForTaskToken -> UpdateJobSucceeded."""

        update_running = sfn_tasks.DynamoUpdateItem(
            self,
            f"{name.capitalize()}UpdateRunning",
            table=data.jobs_table,
            key={
                "pk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.team_pk")
                ),
                "sk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.job_sk")
                ),
            },
            update_expression="SET #s = :r, started_at = :t",
            expression_attribute_names={"#s": "status"},
            expression_attribute_values={
                ":r": sfn_tasks.DynamoAttributeValue.from_string("RUNNING"),
                ":t": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
            result_path=sfn.JsonPath.DISCARD,
        )

        send_task = sfn_tasks.SqsSendMessage(
            self,
            f"{name.capitalize()}EnqueueWorker",
            queue=default_queue,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            message_body=sfn.TaskInput.from_object(
                {
                    "task": sfn.JsonPath.entire_payload,
                    "taskToken": sfn.JsonPath.task_token,
                }
            ),
            timeout=cdk.Duration.hours(2),
            result_path="$.worker_result",
        )
        send_task.add_retry(
            errors=["States.TaskFailed", "Bedrock.ThrottlingException"],
            interval=cdk.Duration.seconds(2),
            max_attempts=3,
            backoff_rate=2.0,
        )

        update_success = sfn_tasks.DynamoUpdateItem(
            self,
            f"{name.capitalize()}UpdateSucceeded",
            table=data.jobs_table,
            key={
                "pk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.team_pk")
                ),
                "sk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.job_sk")
                ),
            },
            update_expression="SET #s = :r, ended_at = :t",
            expression_attribute_names={"#s": "status"},
            expression_attribute_values={
                ":r": sfn_tasks.DynamoAttributeValue.from_string("SUCCEEDED"),
                ":t": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
        )

        update_failed = sfn_tasks.DynamoUpdateItem(
            self,
            f"{name.capitalize()}UpdateFailed",
            table=data.jobs_table,
            key={
                "pk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.team_pk")
                ),
                "sk": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.job_sk")
                ),
            },
            update_expression="SET #s = :r, ended_at = :t",
            expression_attribute_names={"#s": "status"},
            expression_attribute_values={
                ":r": sfn_tasks.DynamoAttributeValue.from_string("FAILED"),
                ":t": sfn_tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
        ).next(sfn.Fail(self, f"{name.capitalize()}Fail"))

        send_task.add_catch(update_failed, errors=["States.ALL"], result_path="$.error")

        definition = update_running.next(send_task).next(update_success)

        return sfn.StateMachine(
            self,
            f"{name.capitalize()}StateMachine",
            state_machine_name=f"{cfg.prefix}-{name}",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=cdk.Duration.hours(6),
            role=None,  # CDK creates default role for skeleton
            tracing_enabled=False,
            logs=sfn.LogOptions(
                destination=cdk.aws_logs.LogGroup(
                    self,
                    f"{name.capitalize()}SmLogs",
                    log_group_name=f"/aws/vendedlogs/states/{cfg.prefix}-{name}",
                    retention=cdk.aws_logs.RetentionDays.THREE_MONTHS,
                    removal_policy=cdk.RemovalPolicy.DESTROY,
                ),
                level=sfn.LogLevel.ERROR,
            ),
        )
