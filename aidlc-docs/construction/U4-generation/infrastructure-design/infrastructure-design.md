# U4 基础设施设计（Infrastructure Design）

**Unit**：U4 Generation Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28
**Stack 策略**: 扩展 U1（I1=A，`shared_constructs/u4_extensions.py`）
**SSE 实现**: sse-starlette（I2=A）
**Event 中继**: EventBridge → SQS 缓冲 → ApiService 消费（I3=B）

---

## 1. U1 Stack 扩展清单

| U1 Stack | U4 扩展 |
|---|---|
| `MessagingStack` | 新增 review-queue + sse-relay-queue + EventBridge Archive + 填充 ChapterStateMachine + OutlineStateMachine |
| `ComputeStack` | worker-generation 镜像更新；ApiService 镜像加 sse-starlette + SQS consumer 协程 |
| `DataStack` | 5 SSM + S3 Lifecycle（NoncurrentVersionExpiration 保留 10）|
| `IdentityStack` | worker-generation Role + ApiService Role 补 SQS ReceiveMessage |
| `ObservabilityStack` | 3 Alarms |

---

## 2. 新增 SQS 队列

### 2.1 review-queue
- Name: `novelgen-review-{env}`
- Visibility Timeout: 180s
- maxReceive 3 → `review-dlq`
- Consumer: worker-generation 扩展循环

### 2.2 sse-relay-queue
- Name: `novelgen-sse-relay-{env}`
- Visibility Timeout: 30s（短时 SSE 中继）
- maxReceive 2 → DLQ
- **为每个 ApiService replica 单独消费**：队列订阅 EventBridge 所有 `novelgen.generation.*` 事件
- **注意**：为支持多 replica 各自持有 SSE 连接的场景，使用 **FIFO 否** 普通 SQS（每事件只被一个 replica 消费）
- **替代方案**：用 SNS Topic + 每 replica 订阅（见 §2.3）

### 2.3 SNS Fan-out（推荐方案用于 SSE 中继）
**修订 I3=B**：为了让所有 replica 都能收到事件并匹配自己持有的 SSE 连接，改用 **SNS Topic → 每个 replica 订阅一个临时 SQS 队列**：

```
EventBridge Rule (generation.*) → SNS Topic (novelgen-generation-events)
                                    │
                                    ├→ replica-1 SQS (TTL 1h auto-created)
                                    ├→ replica-2 SQS
                                    └→ replica-N SQS
```

- 每个 ApiService 启动时创建一个临时 SQS 订阅 SNS；shutdown 时删除
- 每个 replica 独立消费，匹配本地 SSE 连接；未匹配的事件丢弃
- Archive 仍保留 7 天用于 Last-Event-ID 回放

---

## 3. EventBridge Archive（D2=A）

```python
events.CfnArchive(
    self, "U4GenArchive",
    archive_name=f"novelgen-gen-archive-{cfg.env_name}",
    source_arn=default_bus.event_bus_arn,
    retention_days=7,
    event_pattern={"source": ["novelgen.generation"]},
)
```

---

## 4. ChapterStateMachine 完整 ASL（显式 Choice 循环，D3=B）

```json
{
  "Comment": "U4 chapter batch generation with strict serial loop and cancel support",
  "StartAt": "LoadGenerationContext",
  "States": {
    "LoadGenerationContext": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName.$": "$.context_lambda_arn",
        "Payload": {
          "team_id.$": "$.team_id",
          "generation_id.$": "$.generation_id"
        }
      },
      "ResultSelector": {"context.$": "$.Payload"},
      "ResultPath": "$.ctx",
      "Next": "InitLoop"
    },
    "InitLoop": {
      "Type": "Pass",
      "Parameters": {
        "i": 1,
        "chapter_count.$": "$.ctx.context.chapter_count",
        "team_id.$": "$.team_id",
        "team_pk.$": "$.team_pk",
        "job_sk.$": "$.job_sk",
        "generation_id.$": "$.generation_id",
        "queue_url.$": "$.queue_url"
      },
      "Next": "LoopGuard"
    },
    "LoopGuard": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:getItem",
      "Parameters": {
        "TableName.$": "$.jobs_table",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"}
      },
      "ResultSelector": {
        "cancel_requested.$": "$.Item.cancel_requested.BOOL"
      },
      "ResultPath": "$.status_check",
      "Next": "DecideContinue"
    },
    "DecideContinue": {
      "Type": "Choice",
      "Choices": [
        {"Variable": "$.status_check.cancel_requested", "BooleanEquals": true, "Next": "JobCanceled"},
        {"Variable": "$.i", "NumericGreaterThanEqualsPath": "$.chapter_count", "Next": "JobSucceeded"}
      ],
      "Default": "GenerateChapter"
    },
    "GenerateChapter": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl.$": "$.queue_url",
        "MessageBody": {
          "kind": "chapter",
          "taskToken.$": "$$.Task.Token",
          "task": {
            "team_id.$": "$.team_id",
            "generation_id.$": "$.generation_id",
            "chapter_idx.$": "$.i"
          }
        }
      },
      "TimeoutSeconds": 300,
      "Retry": [{"ErrorEquals": ["States.TaskFailed", "Bedrock.ThrottlingException"],
                 "IntervalSeconds": 2, "BackoffRate": 2.0, "MaxAttempts": 3}],
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed", "ResultPath": "$.error"}],
      "ResultPath": "$.chapter_result",
      "Next": "IncrementCounter"
    },
    "IncrementCounter": {
      "Type": "Pass",
      "Parameters": {
        "i.$": "States.MathAdd($.i, 1)",
        "chapter_count.$": "$.chapter_count",
        "team_id.$": "$.team_id",
        "team_pk.$": "$.team_pk",
        "job_sk.$": "$.job_sk",
        "generation_id.$": "$.generation_id",
        "queue_url.$": "$.queue_url",
        "jobs_table.$": "$.jobs_table"
      },
      "Next": "LoopGuard"
    },
    "JobSucceeded": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName.$": "$.jobs_table",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {
          ":r": {"S": "SUCCEEDED"},
          ":t.$": "$$.State.EnteredTime"
        }
      },
      "End": true
    },
    "JobCanceled": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName.$": "$.jobs_table",
        "Key": {"pk.$": "$.team_pk", "sk.$": "$.job_sk"},
        "UpdateExpression": "SET #s = :r, ended_at = :t",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {
          ":r": {"S": "CANCELED"},
          ":t.$": "$$.State.EnteredTime"
        }
      },
      "End": true
    },
    "JobFailed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::dynamodb:updateItem",
      "Parameters": {
        "TableName.$": "$.jobs_table",
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

## 5. OutlineStateMachine ASL（简化）

```json
{
  "Comment": "U4 outline generation workflow",
  "StartAt": "UpdateJobRunning",
  "States": {
    "UpdateJobRunning": { "Type": "Task", "Resource": "arn:aws:states:::dynamodb:updateItem", "Parameters": {"...": "..."}, "Next": "EnqueueOutline" },
    "EnqueueOutline": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl.$": "$.queue_url",
        "MessageBody": {
          "kind": "outline",
          "taskToken.$": "$$.Task.Token",
          "task": {"generation_id.$": "$.generation_id", "team_id.$": "$.team_id"}
        }
      },
      "TimeoutSeconds": 600,
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed"}],
      "Next": "PublishOutlineReady"
    },
    "PublishOutlineReady": { "Type": "Task", "Resource": "arn:aws:states:::events:putEvents", "Parameters": {"Entries": [{"Source": "novelgen.generation", "DetailType": "generation.outline.ready", "Detail": {"...": "..."}}]}, "Next": "JobSucceeded" },
    "JobSucceeded": { "Type": "Task", "Resource": "arn:aws:states:::dynamodb:updateItem", "Parameters": {"...": "..."}, "End": true },
    "JobFailed": { "Type": "Task", "Resource": "arn:aws:states:::dynamodb:updateItem", "Parameters": {"...": "..."}, "Next": "Fail" },
    "Fail": {"Type": "Fail"}
  }
}
```

---

## 6. `shared_constructs/u4_extensions.py` 接口

```python
def extend_data_stack(stack, cfg, novels_bucket) -> None:
    """Add 5 SSM + S3 Lifecycle for chapter NoncurrentVersions."""

def extend_identity_stack(stack, cfg, worker_generation_role, api_role) -> None:
    """Add SQS / Bedrock / Neptune / AOSS / EventBridge permissions."""

def extend_messaging_stack(stack, cfg, data, generation_queue, sfn_role):
    """
    Returns (review_queue, sns_topic, archive, chapter_sm, outline_sm, context_lambda).
    Creates:
      - review-queue + DLQ
      - SNS Topic novelgen-generation-events (fan-out)
      - EventBridge Rule → SNS
      - EventBridge Archive (7d)
      - load-generation-context Lambda
      - ChapterStateMachine / OutlineStateMachine with full ASL
    """

def extend_observability_stack(stack, cfg, alerts_topic) -> None:
    """Add 3 Alarms (TTFT / GenerationSlow / CancelSlow)."""
```

---

## 7. IAM 策略扩展

### 7.1 worker-generation Task Role（补充）
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModelWithResponseStream",
    "bedrock:InvokeModel",
    "aoss:APIAccessAll",
    "neptune-db:ReadDataViaQuery",
    "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes",
    "events:PutEvents",
    "states:SendTaskSuccess", "states:SendTaskFailure"
  ],
  "Resource": "*"
}
```

### 7.2 ApiService Task Role（补充）
```json
{
  "Effect": "Allow",
  "Action": [
    "sns:Subscribe",
    "sns:Unsubscribe",
    "sqs:CreateQueue", "sqs:DeleteQueue",
    "sqs:ReceiveMessage", "sqs:DeleteMessage",
    "events:ListArchives",
    "events:StartReplay"
  ],
  "Resource": "*"
}
```

每 ApiService replica 启动时动态创建一个 SQS 订阅 SNS，关闭时删除。

---

## 8. load-generation-context Lambda

- Runtime: Python 3.12
- Handler: `handler.handler`
- 职责：读 Generation → 调 MemoryFacade.hybrid_search → 写 GEN_CONTEXT 行
- IAM：DDB RW + bedrock-runtime:InvokeModel + aoss:APIAccessAll
- Timeout: 30s

---

## 9. CloudWatch Alarms（3 条）

| Alarm | Metric | 阈值 |
|---|---|---|
| `U4ChapterTTFTHigh` | `ChapterTTFTMs` p95 | > 3000 |
| `U4ChapterGenerationSlow` | `ChapterGenerationMs` p95 | > 60_000 |
| `U4CancelResponseSlow` | `CancelResponseMs` p95 | > 10_000 |

---

## 10. 部署增量

```
DataStack     +5 SSM + S3 Lifecycle   ~零时间
IdentityStack Role 扩展                零时间
MessagingStack +review-queue + SNS Topic + Archive +
               load-generation-context Lambda +
               ChapterStateMachine (replace) +
               OutlineStateMachine (replace)  ~3 min
ComputeStack  镜像更新仅走 docker push   ~5 min (两服务)
ObservabilityStack +3 Alarm              零时间
```

**U4 增量 `cdk deploy --all` 估算：~5 分钟**（不含 docker push）。
