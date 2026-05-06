# U2 基础设施设计（Infrastructure Design）

**Unit**：U2 Ingestion Service
**阶段**：Infrastructure Design
**日期**：2026-04-27
**Stack 策略**: 扩展 U1 现有 Stack（I1=A）
**Browser 并发**: 全局 DynamoDB 计数器（I2=B，上限 10）
**Workflow**: 单 IngestionStateMachine + Choice 分支（I3=A）

---

## 1. U1 Stack 扩展清单

| U1 Stack | U2 新增内容 |
|---|---|
| `MessagingStack` | `ingestion-queue` + DLQ；`NovelIngestedRule`；填充 `IngestionStateMachine` ASL |
| `ComputeStack` | `worker-ingestion` ECS Service + TaskDef + ECR repo；扩展 ALB 路由 `/api/v1/novels/*` |
| `DataStack` | S3 Lifecycle 扩展（crawl-cache 7d / uploads 1d）；6 条 SSM Parameter；**novelgen_jobs 表的 BrowserCounter 项** |
| `IdentityStack` | worker-ingestion IAM Role + Browser 相关权限 |
| `ObservabilityStack` | 5 条新 Alarm |
| `AgentCoreStack` | 注册 Browser 会话配置 |

---

## 2. Browser 全局并发限制（I2=B）

### 2.1 计数器存储
复用 U1 `novelgen_jobs` 表（无需新表）：
- PK: `COUNTER`
- SK: `BROWSER_CONCURRENCY`
- 属性：`current_count: N`, `max_count: 10`, `updated_at: timestamp`, `holders: [job_id, ...]`

### 2.2 租用算法（CAS）
```python
async def acquire_browser_slot(job_id: str) -> bool:
    try:
        await ddb.update(
            pk="COUNTER", sk="BROWSER_CONCURRENCY",
            update_expression="SET current_count = current_count + :one, holders = list_append(holders, :h)",
            condition="current_count < max_count",
            expression_values={":one": 1, ":h": [job_id]},
        )
        return True
    except ConditionalCheckFailedException:
        return False

async def release_browser_slot(job_id: str) -> None:
    # Remove job_id from holders, decrement count
    await ddb.update(
        pk="COUNTER", sk="BROWSER_CONCURRENCY",
        update_expression="SET current_count = current_count - :one",
        condition="current_count > :zero",
        expression_values={":one": 1, ":zero": 0},
    )
```

### 2.3 僵尸计数回收
- Worker 持有 slot 但进程崩溃 → `holders` 列表残留
- 兜底：Worker 启动时注册 `atexit` hook 释放；另加每 5 分钟的清理 Lambda 扫描 `holders` 中过期 job_id

### 2.4 获取失败时的行为
- 10 次 exponential backoff 重试（1s → 8s）
- 仍失败 → 放弃降级，回到 Tier 1 结果（即使正文抽取不完整）
- 记 metric `BrowserSlotAcquireFailed`

---

## 3. IngestionStateMachine 完整 ASL（填充骨架）

```json
{
  "Comment": "U2 Ingestion workflow: upload/download/crawl with Choice branching",
  "StartAt": "UpdateJobRunning",
  "States": {
    "UpdateJobRunning": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_dev_jobs",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, started_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {
          ":r": {"S": "RUNNING"},
          ":t.$": "$$.State.EnteredTime"
        }
      },
      "ResultPath": null,
      "Next": "RouteByKind"
    },

    "RouteByKind": {
      "Type": "Choice",
      "Choices": [
        {"Variable": "$.payload.kind", "StringEquals": "upload", "Next": "ProcessUpload"},
        {"Variable": "$.payload.kind", "StringEquals": "download", "Next": "SearchAndDownload"},
        {"Variable": "$.payload.kind", "StringEquals": "crawl", "Next": "CrawlUrl"}
      ],
      "Default": "JobFailed"
    },

    "ProcessUpload": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${IngestionQueueUrl}",
        "MessageBody": {
          "kind": "upload",
          "task.$": "$",
          "taskToken.$": "$$.Task.Token"
        }
      },
      "TimeoutSeconds": 240,
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed", "UpstreamTransient"],
        "IntervalSeconds": 2, "BackoffRate": 2.0, "MaxAttempts": 2
      }],
      "Catch": [
        {"ErrorEquals": ["RobotsDenied", "ParseError"], "Next": "JobFailed", "ResultPath": "$.error"},
        {"ErrorEquals": ["States.ALL"], "Next": "TryBrowserFallback", "ResultPath": "$.error"}
      ],
      "ResultPath": "$.worker_result",
      "Next": "PublishEvent"
    },

    "SearchAndDownload": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${IngestionQueueUrl}",
        "MessageBody": {"kind": "download", "task.$": "$", "taskToken.$": "$$.Task.Token"}
      },
      "TimeoutSeconds": 120,
      "Retry": [{"ErrorEquals": ["UpstreamTransient"], "IntervalSeconds": 2, "BackoffRate": 2.0, "MaxAttempts": 2}],
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed", "ResultPath": "$.error"}],
      "ResultPath": "$.worker_result",
      "Next": "PublishEvent"
    },

    "CrawlUrl": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${IngestionQueueUrl}",
        "MessageBody": {"kind": "crawl", "task.$": "$", "taskToken.$": "$$.Task.Token"}
      },
      "TimeoutSeconds": 240,
      "Retry": [{"ErrorEquals": ["UpstreamTransient"], "IntervalSeconds": 5, "BackoffRate": 2.0, "MaxAttempts": 2}],
      "Catch": [
        {"ErrorEquals": ["RobotsDenied"], "Next": "JobFailed", "ResultPath": "$.error"},
        {"ErrorEquals": ["States.ALL"], "Next": "TryBrowserFallback", "ResultPath": "$.error"}
      ],
      "ResultPath": "$.worker_result",
      "Next": "PublishEvent"
    },

    "TryBrowserFallback": {
      "Comment": "SFN 层兜底 Browser 降级（Worker 层已做主决策，此处为罕见场景兜底）",
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${IngestionQueueUrl}",
        "MessageBody": {"kind": "browser_fallback", "task.$": "$", "taskToken.$": "$$.Task.Token"}
      },
      "TimeoutSeconds": 180,
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed", "ResultPath": "$.error"}],
      "ResultPath": "$.worker_result",
      "Next": "PublishEvent"
    },

    "PublishEvent": {
      "Type": "Task",
      "Resource": "arn:aws:states:::events:putEvents",
      "Parameters": {
        "Entries": [{
          "Source": "novelgen.ingestion",
          "DetailType": "novel.ingested",
          "Detail": {"team_id.$": "$.team_id", "novel_id.$": "$.novel_id", "job_id.$": "$.job_id"}
        }]
      },
      "ResultPath": null,
      "Next": "JobSucceeded"
    },

    "JobSucceeded": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_dev_jobs",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":r": {"S": "SUCCEEDED"}, ":t.$": "$$.State.EnteredTime"}
      },
      "End": true
    },

    "JobFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName": "novelgen_dev_jobs",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t, error_code = :ec",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {
          ":r": {"S": "FAILED"},
          ":t.$": "$$.State.EnteredTime",
          ":ec.$": "$.error.Error"
        }
      },
      "Next": "Fail"
    },

    "Fail": {"Type": "Fail"}
  }
}
```

---

## 4. MessagingStack 扩展

### 4.1 新增 SQS
```python
self.queues["ingestion"] = sqs.Queue(
    self, "IngestionQueue",
    queue_name=f"{cfg.prefix}-ingestion",
    visibility_timeout=cdk.Duration.seconds(360),
    retention_period=cdk.Duration.days(4),
    dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=self.dlqs["ingestion"]),
)
```

### 4.2 新增 EventBridge Rule
```python
events.Rule(self, "NovelIngestedRule",
    rule_name=f"{cfg.prefix}-novel-ingested",
    event_pattern=events.EventPattern(
        source=["novelgen.ingestion"],
        detail_type=["novel.ingested"],
    ),
    # targets: ApiService SSE 转发，U3 Analysis Worker（U3 落地时挂）
)
```

---

## 5. ComputeStack 扩展

### 5.1 worker-ingestion Service
```python
worker_ingestion_role = iam.Role(self, "WorkerIngestionRole",
    role_name=f"{cfg.prefix}-worker-ingestion",
    assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
)
# 授予：DDB RW (4 tables), S3 RW (novels + exports), SQS recv/delete,
#      Bedrock InvokeModel (LLM 章节切分), AgentCore InvokeBrowser*,
#      SSM GetParameter, EventBridge PutEvents

task_def = ecs.FargateTaskDefinition(
    self, "WorkerIngestionTaskDef",
    cpu=2048, memory_limit_mib=4096,
    task_role=worker_ingestion_role,
    execution_role=identity.ecs_exec_role,
)
task_def.add_container("Container",
    image=ecs.ContainerImage.from_ecr_repository(
        self.repos["worker-ingestion"]  # 新增 ECR repo
    ),
    logging=ecs.LogDriver.aws_logs(stream_prefix="worker-ingestion"),
    environment={
        "ENV": cfg.env_name, "WORKER_TYPE": "ingestion",
        "INGESTION_QUEUE_URL": self.queues["ingestion"].queue_url,
    },
)

service = ecs.FargateService(
    self, "WorkerIngestionService",
    service_name=f"{cfg.prefix}-worker-ingestion",
    task_definition=task_def,
    cluster=self.cluster,
    desired_count=1,
    capacity_provider_strategies=[
        ecs.CapacityProviderStrategy(capacity_provider="FARGATE_SPOT", weight=4),
        ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1),
    ],
)
scalable = service.auto_scale_task_count(min_capacity=1, max_capacity=5)
scalable.scale_on_metric("IngestionQueueDepth",
    metric=self.queues["ingestion"].metric_approximate_number_of_messages_visible(),
    scaling_steps=[
        {"upper": 3, "change": 0},
        {"lower": 10, "change": +1},
        {"lower": 30, "change": +2},
    ],
)
```

### 5.2 新增 ECR Repo
`novelgen/worker-ingestion`（复用 U1 ECR 生命周期策略）。

---

## 6. DataStack 扩展

### 6.1 S3 Lifecycle
```python
novels_bucket.add_lifecycle_rule(
    id="CrawlCacheExpiry",
    prefix="teams/*/crawl-cache/",
    expiration=cdk.Duration.days(7),
)
novels_bucket.add_lifecycle_rule(
    id="UploadsTmpExpiry",
    prefix="teams/*/uploads/tmp/",
    expiration=cdk.Duration.days(1),
)
```

### 6.2 SSM Parameters（6 条）
```
/novelgen/{env}/config/max-upload-size-mb = 200
/novelgen/{env}/config/parse-timeout-seconds = 180
/novelgen/{env}/config/browser-session-timeout-seconds = 60
/novelgen/{env}/config/crawl-cache-ttl-days = 7
/novelgen/{env}/config/search-sources-enabled = "gutenberg,ctext,wikisource,baidu,bing"
/novelgen/{env}/config/crawler-user-agent = "NovelGenBot/0.1 (+https://novelgen.example.com/bot)"
/novelgen/{env}/config/browser-max-concurrency = 10
```

### 6.3 Browser Counter 初始化项
CDK 的 CustomResource 部署时写入初始计数：
```json
{
  "pk": "COUNTER",
  "sk": "BROWSER_CONCURRENCY",
  "current_count": 0,
  "max_count": 10,
  "holders": []
}
```

---

## 7. IdentityStack 扩展（worker-ingestion IAM）

```python
worker_ingestion_role.add_to_policy(iam.PolicyStatement(
    actions=[
        # AgentCore Browser
        "bedrock-agentcore:CreateBrowserSession",
        "bedrock-agentcore:DeleteBrowserSession",
        "bedrock-agentcore:GetBrowserSession",
        # Bedrock LLM for chapter splitting
        "bedrock:InvokeModel",
        # SQS
        "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes",
        # Step Functions callback
        "states:SendTaskSuccess", "states:SendTaskFailure", "states:SendTaskHeartbeat",
        # EventBridge
        "events:PutEvents",
        # SSM
        "ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath",
    ],
    resources=["*"],
))
# DynamoDB & S3 granted via table/bucket grant_read_write methods
```

---

## 8. ObservabilityStack 扩展（5 条新 Alarm）

```python
for name, metric_name, threshold, statistic in [
    ("U2CrawlDowngradeRate", "CrawlTierDowngraded", 0.3, "Average"),  # ratio
    ("U2SearchDowngradeRate", "SearchTierDowngraded", 0.3, "Average"),
    ("U2BrowserOverused", "BrowserSessionCount", 100, "Sum"),
    ("U2IngestionTimeoutP95", "IngestionDurationMs", 120000, "p95"),
    ("U2RobotsBlockedHigh", "RobotsTxtBlocked", 20, "Sum"),
]:
    cw.Alarm(self, f"Alarm{name}",
        alarm_name=f"novelgen-{name}",
        metric=cw.Metric(namespace="NovelGen", metric_name=metric_name, statistic=statistic,
                         period=cdk.Duration.minutes(5)),
        threshold=threshold,
        evaluation_periods=1,
        comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
    ).add_alarm_action(cw_actions.SnsAction(self.alerts_topic))
```

---

## 9. 部署顺序

因为 U2 全部扩展 U1 Stack，部署顺序不变：
```
01-Network → 02-Data → 03-Identity → 04-Messaging → 05-Compute → 06-Edge → 07-Observability → 08-AgentCore
```

U2 变更的实际范围：
- 修改 `data_stack.py`（Lifecycle + SSM）
- 修改 `identity_stack.py`（新 worker-ingestion role）
- 修改 `messaging_stack.py`（ingestion queue + Rule + 填充 ASL）
- 修改 `compute_stack.py`（worker-ingestion service + ECR）
- 修改 `observability_stack.py`（5 Alarms）

单次 `cdk deploy --all` 增量时间 ~8 分钟。

---

## 10. 未决项（Code Generation 阶段处理）

- Dockerfile（worker-ingestion）
- ASL 从 JSON 文件 import 到 CDK 还是 CDK 代码直接构造？（推荐 CDK 代码构造，类型安全）
- Browser 计数器的租用/释放逻辑封装为共享库？（倾向在 `packages/agentcore-browser-pool/` 新建）
