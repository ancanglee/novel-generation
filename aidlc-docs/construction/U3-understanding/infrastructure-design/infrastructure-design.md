# U3 基础设施设计（Infrastructure Design）

**Unit**：U3 Understanding Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28
**Stack 策略**: 扩展 U1（I1=A，`shared_constructs/u3_extensions.py`）
**AgentCore 注册**: Worker 启动时自注册（I2=C）
**Neptune 签名**: 自写 SigV4（I3=A）

---

## 1. U1 Stack 扩展清单

| U1 Stack | U3 扩展 |
|---|---|
| `MessagingStack` | 填充 `AnalysisStateMachine` 完整 ASL |
| `ComputeStack` | worker-analysis 镜像更新（不改 Service 定义）|
| `DataStack` | 5 SSM Parameters |
| `IdentityStack` | worker-analysis Role 扩展（Neptune/AOSS/AgentCore 补齐）|
| `ObservabilityStack` | 5 新 Alarm |
| `AgentCoreStack` | Memory namespace 模板（仅声明，实际 namespace 由 Worker 运行时创建）|

---

## 2. AnalysisStateMachine 完整 ASL（填充 U1 骨架）

```json
{
  "Comment": "U3 novel analysis workflow: supervisor-driven understanding",
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
      "Next": "LoadNovelMetadata"
    },

    "LoadNovelMetadata": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:${account}:function:novelgen-dev-load-novel-metadata",
      "ResultPath": "$.metadata",
      "Next": "InvokeSupervisor",
      "Retry": [{
        "ErrorEquals": ["Lambda.ServiceException", "Lambda.TooManyRequestsException"],
        "IntervalSeconds": 2, "BackoffRate": 2.0, "MaxAttempts": 3
      }]
    },

    "InvokeSupervisor": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage.waitForTaskToken",
      "Parameters": {
        "QueueUrl": "${AnalysisQueueUrl}",
        "MessageBody": {
          "kind": "analysis",
          "taskToken.$": "$$.Task.Token",
          "task": {
            "job_id.$": "$.job_id",
            "team_id.$": "$.team_id",
            "novel_id.$": "$.metadata.novel_id",
            "chapter_count.$": "$.metadata.chapter_count",
            "owner_user_id.$": "$.owner_user_id"
          }
        }
      },
      "TimeoutSeconds": 1200,
      "ResultPath": "$.supervisor_result",
      "Retry": [{
        "ErrorEquals": ["States.TaskFailed", "Bedrock.ThrottlingException"],
        "IntervalSeconds": 5, "BackoffRate": 2.0, "MaxAttempts": 2
      }],
      "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "JobFailed", "ResultPath": "$.error"}],
      "Next": "PublishAnalyzed"
    },

    "PublishAnalyzed": {
      "Type": "Task",
      "Resource": "arn:aws:states:::events:putEvents",
      "Parameters": {
        "Entries": [{
          "Source": "novelgen.analysis",
          "DetailType": "novel.analyzed",
          "Detail": {
            "team_id.$": "$.team_id",
            "novel_id.$": "$.metadata.novel_id",
            "job_id.$": "$.job_id"
          }
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
        "ExpressionAttributeValues": {
          ":r": {"S": "SUCCEEDED"},
          ":t.$": "$$.State.EnteredTime"
        }
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

## 3. `shared_constructs/u3_extensions.py` 接口

### 3.1 Helper 列表

```python
def extend_data_stack(stack, cfg) -> None:
    """Add 5 U3-specific SSM Parameters."""

def extend_identity_stack(stack, cfg, worker_analysis_role) -> None:
    """Augment worker-analysis Role with Neptune / AOSS / AgentCore / Bedrock Embeddings permissions."""

def extend_messaging_stack(stack, cfg, data, analysis_queue) -> sfn.StateMachine:
    """Replace U1 analysis-state-machine skeleton with U3 full ASL. Also add load_novel_metadata Lambda."""

def extend_observability_stack(stack, cfg, alerts_topic) -> None:
    """Add 5 U3 Alarms."""

def extend_agentcore_stack(stack, cfg) -> None:
    """Configure AgentCore Memory namespace template + Observability project."""
```

### 3.2 无 ECS Service 新增
U3 复用 U1 `worker-analysis` Service，仅需在镜像中加入 Strands + MemoryFacade 实现（Phase H 代码层面）。

---

## 4. Worker 启动时 AgentCore 自注册（I2=C）

### 4.1 Worker main.py 启动流程
```python
async def startup():
    # 1. Load config from SSM
    region = os.environ["AWS_REGION"]
    # 2. Register Strands Agent with AgentCore Runtime (idempotent)
    await agentcore_runtime.register_agent(
        agent_id=f"novelgen-understanding-{ENV}",
        agent_package_uri="ecr://.../worker-analysis:latest",
        tools=[...]  # @tool 装饰器发现
    )
    # 3. Ensure Memory namespace for this worker (lazy on first job)
    # 4. Start SQS consume loop
```

**幂等性**：register_agent 调用 `describe_agent` 先检查是否已注册；存在则跳过。

### 4.2 优点 vs 缺点
- ✅ 无需 CDK Custom Resource（减少部署复杂度）
- ✅ Agent 变更后 rolling update Worker 即自动更新注册
- ⚠️ Worker 启动慢 +3-5s（每 Task 都要检查 + 可能注册）
- ⚠️ 多 Worker 并发启动时首次注册需要 race-safe 设计（ConditionalCheck or DDB lock）

### 4.3 Race 保护
使用 DynamoDB `COUNTER` 模式（与 U2 BrowserPool 同思路）：
- pk=`AGENT_REG`, sk=`{agent_id}`
- 首次注册用 `attribute_not_exists` 条件写入
- 失败者跳过（说明已被其他 Worker 注册）

---

## 5. IAM 策略扩展（worker-analysis Task Role）

U1 已授予大部分，U3 补齐：

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream",
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
    "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes",
    "states:SendTaskSuccess", "states:SendTaskFailure",
    "events:PutEvents",
    "ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"
  ],
  "Resource": "*"
}
```

DynamoDB / S3 通过 `table.grant_read_write_data` 和 `bucket.grant_read_write` 授予。

---

## 6. Neptune SigV4 签名实现（I3=A 自写）

### 6.1 代码骨架
```python
import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import boto3


class NeptuneSignedClient:
    def __init__(self, endpoint: str, region: str = "us-east-1"):
        self._endpoint = endpoint.rstrip("/")
        self._region = region
        self._session = boto3.Session()

    async def execute_opencypher(self, query: str, parameters: dict) -> dict:
        url = f"{self._endpoint}/openCypher"
        body = {"query": query, "parameters": parameters}

        # Build AWSRequest and sign
        creds = self._session.get_credentials().get_frozen_credentials()
        request = AWSRequest(
            method="POST",
            url=url,
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(creds, "neptune-db", self._region).add_auth(request)

        # Execute via httpx (signed headers)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, content=request.body, headers=dict(request.headers))
            resp.raise_for_status()
            return resp.json()
```

### 6.2 连接池
`httpx.AsyncClient(limits=httpx.Limits(max_connections=10))` per-Worker；每 Bedrock Worker 有独立实例。

### 6.3 错误重试
通过 `tenacity` 对 5xx / timeout 做指数退避重试（max 3 次）。

---

## 7. OpenSearch 索引模板（Bootstrap）

### 7.1 模板定义
在 Worker 启动时对 AOSS 调用 `PUT _index_template/facts-template`：

```json
{
  "index_patterns": ["facts-*"],
  "template": {
    "settings": {
      "index.knn": true,
      "index.knn.algo_param.ef_search": 100
    },
    "mappings": {
      "properties": {
        "team_id": {"type": "keyword"},
        "novel_id": {"type": "keyword"},
        "fact_key": {"type": "keyword"},
        "fact_type": {"type": "keyword"},
        "chapter": {"type": "integer"},
        "content_text": {"type": "text", "analyzer": "ik_max_word"},
        "embedding": {
          "type": "knn_vector",
          "dimension": 1024,
          "method": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "nmslib",
            "parameters": {"ef_construction": 512, "m": 16}
          }
        }
      }
    }
  }
}
```

### 7.2 Lazy 索引创建
Worker 首次为某 team 写向量时：
1. `HEAD /facts-{team_id}` → 404 时 create
2. `PUT /facts-{team_id}`（继承 template）

---

## 8. AgentCore Memory 配置

### 8.1 Memory 策略
U3 使用 AgentCore Memory 的 `SUMMARIZATION` + `USER_PREFERENCE` 策略（按 AgentCore 文档最佳实践）：
- Namespace：`{team_id}:{novel_id}`
- Short-term capacity：每 session 保持 20 条最近事实
- Long-term：所有 fact_key 永久存储

### 8.2 创建时机
- Namespace 在 Worker 处理 Job 时首次 `put_memory_item` 时 lazy 创建
- U1 AgentCoreStack 仅部署 IAM + Observability project 配置

---

## 9. SSM Parameters（U3 新增 5 条）

```
/novelgen/{env}/config/titan-embed-model = amazon.titan-embed-text-v2:0
/novelgen/{env}/config/titan-embed-dim = 1024
/novelgen/{env}/config/supervisor-max-steps = 50
/novelgen/{env}/config/chapter-retry-max = 3
/novelgen/{env}/config/memory-write-timeout-ms = 2000
```

---

## 10. CloudWatch Alarms（5 条）

| Alarm | Metric | 阈值 | 动作 |
|---|---|---|---|
| `U3AnalysisTimeoutP95` | `JobDurationMs{JobType=analysis}` P95 | > 900_000 ms (15min) | SNS |
| `U3SupervisorDrift` | `SupervisorStepCount` Max | > 40 | SNS |
| `U3MemoryWriteFailureHigh` | `MemoryWriteFailure` Sum | > 20 / 5min | SNS |
| `U3NeptuneSlowUpsert` | `NeptuneLatencyMs{op=upsert}` P95 | > 500 ms | SNS |
| `U3ChapterPartialRateHigh` | `ChapterProcessingMs` 与 partial flag 联合 | > 10% | SNS |

---

## 11. Lambda 函数（2 个）

### 11.1 `load-novel-metadata`
- Runtime: Python 3.12
- 被 AnalysisStateMachine 的 LoadNovelMetadata state 调用
- 职责：给定 team_id + novel_id，返回 chapter_count / word_count / chapters[]
- IAM：DynamoDB Query on novelgen_tenancy

### 11.2 （移除）AgentCore Registration Lambda
- 由于 I2=C 选择 Worker 启动时自注册，**不再需要** AgentCore Registration Lambda
- 节省 1 个 Lambda 资源

---

## 12. 未决项与降级路径

- AgentCore SDK Python 绑定仍不完整 → 部分 API 调用用 `boto3.client('bedrock-agentcore-control')` 或 `AwsCustomResource` 兜底
- Strands Agents 与 AgentCore Runtime 的集成：Code Generation 阶段实测
- Neptune openCypher 新版本参数：以 AWS 文档为准

---

## 13. 部署增量

基于 U1 + U2 已部署状态，U3 cdk deploy 增量：
- DataStack: +5 SSM（近零时间）
- IdentityStack: Role 扩展（近零时间）
- MessagingStack: 替换 analysis-state-machine 定义 + 新 Lambda（~2 min）
- ObservabilityStack: +5 Alarm（近零时间）
- ComputeStack: 不变（worker-analysis 镜像推送另行 docker push）

**估算增量部署时间：~4 分钟**（不含镜像推送）。
