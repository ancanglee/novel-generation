# 服务列表（Services）— 小说仿写生成应用

**版本**：1.0
**日期**：2026-04-27

本文档描述服务层的编排模式、生命周期、跨服务协作。

---

## 服务边界

| 服务 | 运行时 | 承载组件 |
|---|---|---|
| **frontend-user** | Docker on ECS Fargate | C-01 WebFrontend (User) + C-03 NodeBff |
| **frontend-admin** | Docker on ECS Fargate | C-02 WebFrontend (Admin) |
| **api-service** | Docker on ECS Fargate | C-04 ApiService（含 C-06、C-14） |
| **worker-service** | Docker on ECS Fargate (多队列副本) | C-05 WorkerService（含 C-07~C-11） |
| **workflow-orchestrator** | AWS Step Functions | C-13 State Machines |
| **auth** | Managed（Cognito + AgentCore Identity） | C-15 AuthAdapter 作为 library |
| **agentcore-memory** | Managed（AgentCore Memory） | 被 C-12 MemoryFacade 调用 |
| **agentcore-gateway** | Managed（AgentCore Gateway） | 工具路由 |
| **agentcore-browser** | Managed（AgentCore Browser） | 公版书下载 + URL 抓取 |
| **agentcore-observability** | Managed（AgentCore Observability） | Agent 链路追踪 |
| **neptune** | Managed | 知识图谱 |
| **opensearch-serverless** | Managed | 向量检索 |
| **dynamodb** | Managed | 元数据 + 审计日志 |
| **s3** | Managed | 原文 + 生成稿 |
| **cloudfront** | Managed | CDN |

---

## 核心服务编排模式

### 1. 同步 REST（短请求）

**Pattern**: frontend → NodeBff → ApiService → DynamoDB/S3 → 返回

**适用**：小说列表、报告查看、admin 管理、章节编辑保存、导出 URL 预签名等。

```
Browser ──HTTPS──► NodeBff ──HTTP──► ApiService ──aws──► DynamoDB
                    │
                    └── cookie session + jwt forward
```

SLA: p95 < 300ms；失败重试 by HTTP 标准。

---

### 2. 异步长任务（Step Functions 编排）

**Pattern**: ApiService 启动 Step Functions 执行 → 立即返回 jobId；WorkerService 按队列消费 → 完成后发事件；前端通过 SSE 订阅状态。

```
Browser ──POST /analyses──► ApiService ──StartExecution──► Step Functions
                                │                            │
                                ├─ DynamoDB: 写 job 记录       ├─ 粗读 Task → SQS(analysis-queue)
                                └─ 返回 {job_id}               ├─ 并行(分类/人物/地图/风格)
                                                               ├─ 细读 Map state (动态并发, AD6=F)
                                                               └─ 写回 Memory + DynamoDB 状态

Browser ──GET /jobs/{id}/stream (SSE)──► ApiService ◄──EventBridge──◄ Worker
```

**状态机示例 — AnalysisWorkflow**（Step Functions Standard）：

```
RoughRead → Parallel [ClassifyTags, ExtractCharacters, ExtractMap, AnalyzeStyle]
  → DeepRead (Map state with dynamic MaxConcurrency)
  → WriteMemory → UpdateJobState(COMPLETED)
```

失败处理：
- 每个 Task 最多重试 3 次，指数退避
- 不可重试错误（例如文件损坏）→ Catch 节点 → UpdateJobState(FAILED)
- Map state 允许部分章节失败，失败率 > 5% 触发整体失败

---

### 3. 流式章节生成（SSE + Cancel）

**Pattern**: 前端订阅 SSE；后端一边调 Bedrock Converse Stream API 一边写 SQS 事件；前端可随时调用 cancel REST。

```
┌─────────┐  GET /jobs/{id}/stream   ┌────────────┐     SUBSCRIBE   ┌────────────┐
│ Browser │ ◄──────── SSE ───────── │ ApiService │ ◄──────────── │ EventBridge│
└────┬────┘                          └────────────┘                 └──────┬─────┘
     │ POST /jobs/{id}/cancel                                              │
     ▼                                                                     │ PUBLISH
┌────────────┐     SIGNAL             ┌────────────┐  STREAM TOKENS        │
│ ApiService │ ────────────────────► │Worker (gen)│ ──────────────────────┘
└────────────┘   DynamoDB: cancel=1   └─────┬──────┘
                                            │
                                            ▼
                                        Bedrock Converse Stream API
```

**取消语义**：
- Cancel 写入 DynamoDB `jobs[job_id].cancel_requested = true`
- Worker 在每次收到 Bedrock stream token 时检查该标志，为真则关闭流、标记 job 为 CANCELED
- 已消耗 token 记账到 admin 监控

**断线重连**：前端用 SSE lastEventId 机制恢复；Worker 通过 EventBridge 持久化事件流。

---

### 4. 事件驱动：章节完成 → Critic + Moderation

**Pattern**: ChapterWorkflow 完成后，发事件进入多个队列并发处理。

```
ChapterAgent done
    ├─► SelfCritique (inline) ─► 结果与章节一起写入
    ├─► SQS(critic-queue)  ─► CriticAgent ─► 写 DynamoDB + 发 SSE 事件
    └─► SQS(moderation-queue) ─► ModerationAgent ─► 写标记 + 入审核队列
```

**为什么分开**：Critic 与 Moderation 都需 LLM 调用，并行不阻塞主流程。

---

### 5. 周期性一致性校验

**Pattern**: 每生成 N 章由 ChapterWorkflow 发信号；定时器兜底。

```
ChapterWorkflow.ChapterCompleted
    └─ if (completed_count % N == 0) ─► StartExecution(ConsistencyWorkflow)

EventBridge Scheduler (每 30 分钟兜底)
    └─ 扫描活跃 generation jobs ─► 按需触发
```

---

### 6. Admin 模型配置生效

**Pattern**: 配置写入 DynamoDB + 版本号；WorkerService 启动时加载 + 定期刷新（30s）。

```
Admin UI ──PUT /admin/models──► ApiService ──put──► DynamoDB(ModelConfig v=3)

Worker polling:
  每 30s ──get──► DynamoDB(ModelConfig)
  比较版本号，变更则热替换
```

正在执行的任务**不中断**（冻结 v=2）；新任务使用 v=3。

---

### 7. 细读并发动态控制（AD6=F）

**Pattern**: 从 admin 配置读 `deep_read_max`（默认 20）；Worker 根据 Bedrock throttle 错误率在 [1, deep_read_max] 之间自适应。

算法（简化）：
```
current = min(4, deep_read_max)  # 起步
on every_batch_end:
    if throttle_rate < 1%: current = min(current + 2, deep_read_max)
    elif throttle_rate < 5%: keep
    else: current = max(1, current // 2)
```

状态保存在 Redis/DynamoDB 中，跨 Worker 共享。

---

### 8. 多租户强隔离

**Pattern**: 所有入口强制 teamId；存储前缀强制；IAM Session Tag 辅助。

- **API**：`AuthAdapter.verify_jwt` 解析 teamId；每个端点装饰器校验 path/body 中的 teamId 一致
- **S3**：对象 key 必须以 `teams/{team_id}/` 开头；ECS task role 带 Session Tag `team_id=xxx`，S3 bucket policy 仅允许 key 前缀匹配该 tag
- **DynamoDB**：PK 必须以 `TEAM#{team_id}#` 开头；代码层 runtime 断言 + DynamoDB condition expression
- **Neptune / OpenSearch**：每个 team 独立索引/图空间（或属性过滤 + row-level 安全）
- **测试**：自动化渗透测试脚本每次部署运行，验证跨 team 访问必返回 403

---

### 9. 敏感内容审核闭环

```
Chapter done ──► ModerationAgent ──► flagged segments 存 DynamoDB
                                       │
                                       ▼
ContentModerator 看审核队列（GET /api/v1/reviews/pending）
                                       │
                                       ▼
段落级打回 ──► 更新 Chapter 状态为 MODERATION_REJECTED
                                       │
                                       ▼
创建者收通知（SNS/邮件）──► 打开章节看到打回原因
                                       │
                                       ▼
创建者点"重写" ──► 入 generation-queue 重新生成该章
```

---

## 服务启动与关闭

### 冷启动顺序（CDK 部署）
1. VPC + ECR + Secrets Manager
2. Cognito User Pool + Identity Pool
3. DynamoDB 表 + S3 buckets + Neptune 集群 + OpenSearch collection
4. AgentCore 服务配置（Memory / Gateway / Browser / Observability / Identity / Runtime）
5. Step Functions 状态机
6. ECS Cluster + Task Definitions + Services（api-service, worker-service, frontend-user, frontend-admin）
7. ALB + CloudFront + WAF
8. CloudWatch Alarms + AgentCore Observability 告警

### 零停机部署
- ECS Rolling Update（min=100%, max=200%）
- 数据库 schema 变更走向后兼容 + 双写策略
- Step Functions 状态机新版本与旧版本并存，旧版本任务继续走旧版

---

## 服务级容错与限流

| 风险 | 服务 | 缓解 |
|---|---|---|
| Bedrock 限流 | WorkerService | AD6=F 动态并发 + 指数退避 + 切换到 fallback 模型 |
| SSE 连接漂移 | ApiService / NodeBff | lastEventId + 心跳 keepalive 每 15s |
| Step Functions 超时（1 年上限）| WorkflowOrchestrator | 分阶段启动新 execution，不使用单个超长 execution |
| Neptune 可用性下降 | MemoryFacade | 多级降级：先降级到仅 AgentCore Memory，再降级到 DynamoDB 缓存 |
| 并发写 Chapter 冲突 | ApiService | DynamoDB conditional write + 乐观锁 version |
| Admin 配置错误 | AdminService | schema 校验 + 预览/模拟模式（dry-run） |

---

## 跨服务数据流（摘要）

1. **采集流**：Browser → NodeBff → ApiService → (S3 原文 + DynamoDB 元数据) + (可选 Step Functions 爬虫)
2. **分析流**：ApiService → Step Functions → WorkerService(Understanding) → (MemoryFacade → AgentCore Memory + Neptune + OpenSearch) + DynamoDB 状态
3. **大纲流**：ApiService → Step Functions → WorkerService(Outline) → S3 大纲 + DynamoDB 状态 → SSE 通知
4. **章节流**：ApiService → Step Functions → WorkerService(Chapter) → Bedrock Stream → EventBridge → ApiService SSE → NodeBff → Browser
5. **审核流**：WorkerService(Moderation) → DynamoDB flagged → ContentModerator UI → ApiService → 状态更新
6. **Critic 流**：WorkerService(Chapter done) → SQS → WorkerService(Critic) → DynamoDB critique → SSE
7. **一致性流**：ChapterWorkflow 每 N 章触发 → ConsistencyWorkflow → WorkerService(Consistency) → DynamoDB report
8. **导出流**：ApiService → 组装 (S3 章节文件) → 生成 TXT/EPUB → S3 → presigned URL → Browser
