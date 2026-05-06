# U3 逻辑组件（Logical Components）

**Unit**：U3 Understanding Agents
**阶段**：NFR Design
**日期**：2026-04-28

U3 绝大多数基础设施由 U1 预建。本文列出 U3 **新增 / 扩展** 的逻辑组件。

---

## 1. SQS 队列

扩展 U1 `MessagingStack`（实际上 U1 已预定义 `analysis-queue`）：

| 队列 | 消费者 | DLQ |
|---|---|---|
| `analysis-queue`（U1 预建） | worker-analysis | `analysis-dlq`（U1 预建） |

**参数（不变）**：Visibility Timeout 360s / maxReceive 3 / Retention 4 days

---

## 2. ECS Service

扩展 U1 `worker-analysis` Service（U1 已预定义）：
- U3 在镜像中加入 Strands + MemoryFacade 实现
- 新增 env 变量：`NEPTUNE_ENDPOINT`, `OPENSEARCH_ENDPOINT`, `TITAN_EMBED_MODEL`

无需新建 Service。

---

## 3. Step Functions 填充

填充 U1 `AnalysisStateMachine` 骨架：

```
UpdateJobRunning
    ↓
LoadNovelMetadata (Lambda: 拉 Chapter 列表)
    ↓
InvokeSupervisorViaSQS (WAIT_FOR_TASK_TOKEN)
    ↓ (taskToken returned by Worker after Supervisor completes)
PublishNovelAnalyzed (EventBridge novel.analyzed)
    ↓
UpdateJobSucceeded
```

Retry / Catch 沿用 U1 SFN 骨架规则。

---

## 4. DynamoDB 新增数据模式

### 4.1 CharacterProfile
- 表：`novelgen_tenancy`（复用）
- SK：`CHARACTER#{novel_id}#{character_id}`

### 4.2 CharacterSnapshot
- SK：`CHAR_SNAP#{novel_id}#{character_id}#{chapter:05d}`

### 4.3 Checkpoint
- 表：`novelgen_jobs`（复用）
- SK：`CHECKPOINT#{job_id}`，TTL 24h

### 4.4 AnalysisReport
- 正文存 S3 `teams/{team_id}/novels/{novel_id}/analysis-report.json`
- 元数据 row：SK=`REPORT#{novel_id}`

### 4.5 类型标签合并映射（admin 用）
- 表：`novelgen_config`
- SK：`TAG_MAPPING#v{version}`

---

## 5. S3 新增前缀

在 U1 `novelgen-novels-{env}` bucket 复用：

| 前缀 | 用途 | Lifecycle |
|---|---|---|
| `teams/{team_id}/novels/{novel_id}/analysis-report.json` | 分析报告 | 随 bucket 策略 |
| `teams/{team_id}/novels/{novel_id}/character-portraits/` | 预留：未来生成人物肖像图 | — |

---

## 6. Neptune 资源（U1 预建）

U1 `DataStack.neptune_cluster` 即 U3 使用的图数据库。U3 不新增 Neptune 资源，仅：
- 在 Worker 启动时读 SSM `/novelgen/{env}/config/neptune-endpoint`
- IAM Role 授予 `neptune-db:*` 权限（U1 已授予）

---

## 7. OpenSearch 资源（U1 预建）

U1 `DataStack.aoss_collection` 即 U3 使用的向量搜索。U3 新增：
- 索引模板（通过 Worker 启动时调用 OpenSearch API 创建）：`facts-*`
- 新索引 lazy 创建：首次写入该 team 时

---

## 8. AgentCore 扩展（扩展 U1 AgentCoreStack）

U1 AgentCoreStack 当前是 placeholder。U3 填充：

### 8.1 Memory 配置
- Memory namespace 模板：`{team_id}:{novel_id}`
- 策略：semantic + short-term 结合

### 8.2 Runtime 配置
- 注册 Agent 包（OCI image 推到 ECR `novelgen/worker-analysis`）
- Runtime 承担 Supervisor 执行（或 Worker 内部直接调用 Bedrock Converse，两种实现待 Infra Design 选）

### 8.3 Observability
- Project name：`novelgen-{env}`
- 采集范围：所有 Bedrock Converse 调用、每个 @tool 调用

### 8.4 Identity（暂不使用，U3 无外部工具调用）

---

## 9. IAM 策略扩展

`worker-analysis` Task Role 新增：
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream",
    "bedrock-agentcore:*",
    "neptune-db:ReadDataViaQuery",
    "neptune-db:WriteDataViaQuery",
    "aoss:APIAccessAll",
    "aoss:BatchGetCollection",
    "events:PutEvents",
    "dynamodb:Query", "dynamodb:PutItem", "dynamodb:UpdateItem",
    "s3:PutObject", "s3:GetObject"
  ],
  "Resource": "*"
}
```

（U1 已授予大部分，U3 确认补充）

---

## 10. SSM Parameters（U3 新增 5 条）

```
/novelgen/{env}/config/titan-embed-model = amazon.titan-embed-text-v2:0
/novelgen/{env}/config/titan-embed-dim = 1024
/novelgen/{env}/config/supervisor-max-steps = 50
/novelgen/{env}/config/chapter-retry-max = 3
/novelgen/{env}/config/memory-write-timeout-ms = 2000
```

---

## 11. 新增 CloudWatch Alarms（5 条）

加入 U1 `ObservabilityStack`：

| Alarm | Metric | 阈值 |
|---|---|---|
| `U3AnalysisTimeoutP95` | `JobDurationMs{JobType=analysis}` P95 | > 900000 ms (15 min) |
| `U3SupervisorDrift` | `SupervisorStepCount` | > 40（接近 50 上限警告） |
| `U3MemoryWriteFailureHigh` | `MemoryWriteFailure` | > 5%（5 min 窗口）|
| `U3NeptuneSlowUpsert` | `NeptuneLatencyMs{op=upsert}` P95 | > 500 ms |
| `U3ChapterPartialRateHigh` | `ChapterPartialRate` | > 10% |

---

## 12. 新增 Lambda（可选）

### 12.1 AgentCore Registration Lambda
启动时注册 Strands Agent 到 AgentCore Runtime（CDK CustomResource 驱动）。

### 12.2 Neptune Index Bootstrap Lambda
首次部署时创建 Neptune 节点约束（例如 `CREATE CONSTRAINT ON (p:Place) ASSERT p.place_id IS UNIQUE`）。

---

## 13. 资源总结

| 类别 | 新增 | 扩展 U1 | 合计 |
|---|---|---|---|
| SQS | 0 | 0（复用 analysis-queue）| 0 |
| ECS Service | 0 | 1（worker-analysis 镜像更新）| 0 |
| Step Functions | 0 | 1（填充 AnalysisStateMachine）| 0 |
| DynamoDB 新 SK 模式 | 4 | 复用现有表 | 4 |
| S3 新前缀 | 2 | 复用 novels bucket | 2 |
| Neptune / OpenSearch 资源 | 0 | 复用 U1 | 0 |
| AgentCore Memory namespaces | 每 job 1 个（动态）| U1 AgentCoreStack | — |
| IAM 策略语句 | 1 Task Role 扩充 | — | 1 |
| SSM Parameters | 5 | — | 5 |
| Alarms | 5 | — | 5 |
| Lambda | 2（可选）| — | 2 |

**U3 总体增量：~14 个基础设施/配置元素**（不含镜像内代码）。
