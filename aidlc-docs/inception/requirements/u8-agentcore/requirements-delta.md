# U8 — AgentCore Full Integration Requirements Delta

本文件是对 `../requirements.md` 的**增量扩展**，不替换原文。所有 FR-8.x 条目升级为**硬性 MUST**，并明确 SDK 层面的契约。原文中所有"V1 placeholder / preview 占位 / 等 SDK GA"的表述全部作废。

> **关联原始条款**：FR-8 AgentCore 服务编排 / FR-10.4 Identity / FR-6.1 Memory / FR-1.2-1.3 Browser

---

## Intent Analysis

| 维度 | 取值 |
|---|---|
| **Type** | Brownfield 增量（Construction-level refactor） |
| **Scope** | 横切：`infra/cdk/` + `packages/memory-facade` + `packages/auth-adapter` + `packages/agentcore-browser-pool` + `services/worker-analysis` + `services/worker-ingestion` + `services/worker-generation` + `services/worker-critic` + `services/worker-consistency` + `services/worker-moderation` |
| **Risk** | 中高（替换 V1 的 NotImplementedError，会改变 runtime 行为；错误传播路径被打开） |
| **Depth** | Comprehensive（明确 SDK 调用、资源生命周期、失败语义） |
| **Impacted units** | U1 / U2 / U3 / U4 / U5 / U6（6/7）新增 U8-AgentCore 为独立跨单元 |

---

## FR-8 AgentCore 硬性接入要求（覆盖原 FR-8）

### FR-8.1 Runtime（硬性）
- **MUST** 在 CDK 部署阶段通过 `bedrock-agentcore-control.CreateAgentRuntime` 为以下 5 个 Agent 各自创建一个 `AgentRuntime`：
  - `novelgen-{env}-supervisor-understanding`（U3）
  - `novelgen-{env}-supervisor-generation`（U4）
  - `novelgen-{env}-critic`（U5）
  - `novelgen-{env}-consistency`（U5）
  - `novelgen-{env}-moderation`（U5，V2 激活）
- **MUST** 每个 Worker 容器在启动阶段调用 `bedrock-agentcore.InvokeAgentRuntime` 之前完成：
  1. 读取 SSM `/novelgen/{env}/agentcore/runtime/{name}-arn` 获取 ARN；
  2. 调用 `DescribeAgentRuntime` 确认 `STATUS=READY`；否则带退避重试 60s。
- **MUST** `agentcore_registration.py` 保留（用作"已注册状态"的本地幂等缓存 + metric），但自注册逻辑移除 NotImplementedError，改为"仅做 DDB 心跳 + 调 `DescribeAgentRuntime`"。
- **MAY** Supervisor 本地代码（`services/worker-analysis/.../supervisor.py`）保留当前 pytohn 实现，但其**工具调用必须通过 AgentCore Gateway**（见 FR-8.3）；Supervisor 的"agent 身份"通过 InvokeAgentRuntime 的 `runtimeSessionId` 与 `traceId` 标识。

### FR-8.2 Memory（硬性）
- **MUST** 在 CDK 部署阶段通过 `CreateMemory` 创建一个跨 env 的 Memory：`novelgen-{env}-memory`；策略：
  - `eventExpiryDays = 365`
  - `memoryStrategies = [SEMANTIC, SUMMARIZATION]`（分别对应"事实检索"和"章节摘要"）
- **MUST** 事实写入通过 `CreateEvent(memoryId, actorId=team_id:novel_id, sessionId=job_id, payload=[...])`；每条 Fact 映射为一个 event.payload.conversational 或 blob event（血统：Memory 以 event 为单位，Strategy 异步将 events 聚合成长期记忆）。
- **MUST** 读路径优先级：`RetrieveMemoryRecords(memoryId, namespace={team_id}/{novel_id}, searchCriteria.searchQuery=...)` → 仅当 Memory 返回 0 条时才 fallback 到 OpenSearch 向量检索。
- **MUST** 完全移除 `facade_impl.py:63-65` 中 `except NotImplementedError: log.warning(...skipping)` 的"静默容错"逻辑；AgentCore Memory 写失败**必须** raise `MemoryBackendError` 并导致该 Fact 进入 DLQ（不得静默成功）。
- **MUST** `{team_id}:{novel_id}` 多租户命名空间固化到 Memory 的 `namespace` 字段（由 strategy 配置驱动），不再在 client 层手工拼接。

### FR-8.3 Gateway（硬性）
- **MUST** 在 CDK 部署阶段通过 `CreateGateway(name=novelgen-{env}-gateway, protocolType=MCP)` 创建一个 MCP Gateway。
- **MUST** 注册以下 6 个 **GatewayTarget**（每个一个 Tool 族）：
  | Target | 工具名 | 后端 | 作用 |
  |---|---|---|---|
  | `memory-facade` | `remember / recall / get_character` | Lambda | U3 写事实、U4 读事实 |
  | `graph-ops` | `upsert_node / upsert_edge / neighbors` | Lambda（封装 `NeptuneSignedClient`） | 图检索 |
  | `vector-ops` | `index_vector / search_similar / hybrid_search` | Lambda（封装 `OpenSearchVectorClient`） | 向量检索 |
  | `ingestion-fetch` | `fetch_public_domain / fetch_url` | Lambda（worker-ingestion 的 HTTP fetcher） | 抓取 |
  | `ingestion-browser` | `render_with_browser` | Lambda（内部调 AgentCore Browser） | Tier2 抓取 |
  | `ddb-jobs` | `put_checkpoint / get_checkpoint / advance_scan_cursor` | Lambda（封装 `DynamoDBAdapter`） | 幂等 / 游标 |
- **MUST** 所有 Agent 调用**只通过 Gateway**（不直连 Neptune / AOSS / DynamoDB 业务数据）。例外：`CheckpointStore` 的底层 DDB 仍可直连（性能敏感，且不暴露给 LLM）。
- **MUST** Tool schema 使用 JSON Schema 2020-12 方言，字段 `extra=forbid`。

### FR-8.4 Browser（硬性）
- **MUST** `_render_with_agentcore(url, timeout_seconds)` 使用 `bedrock-agentcore.StartBrowserSession(browserIdentifier, sessionTimeoutSeconds, viewPort)` → 返回 `sessionId` + `streamEndpoint`（CDP wss URL）+ `liveViewUrl`。
- **MUST** 通过 CDP（Chrome DevTools Protocol）客户端（建议 `playwright` async / `pyppeteer`）连接 `streamEndpoint`、调用 `Page.goto(url, waitUntil='networkidle')` → `Page.content()` 拿 rendered HTML。
- **MUST** 无论成功失败、`finally` 块调用 `StopBrowserSession(sessionId)`。
- **MUST** 全局并发池 `BrowserPool` 保留（因为 AgentCore Browser 本身有 quota，pool 做 **客户端削峰 + 僵尸回收**），但 `max_count` 动态读取 SSM `/novelgen/{env}/config/browser-max-concurrency`，默认 10。

### FR-8.5 Observability（硬性）
- **MUST** CDK 部署阶段启用 AgentCore 内置 Observability（CloudWatch Logs + X-Ray trace），通过 `CreateAgentRuntime.logDestinationConfig` 指定 `/aws/bedrock-agentcore/runtimes/novelgen-{env}-*`。
- **MUST** Worker 代码引入 OpenTelemetry Python SDK + ADOT（AWS Distro）auto-instrument；OTLP endpoint 指向 AgentCore observability sidecar（env: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`，由 AgentCore Runtime 自动注入）。
- **MUST** `packages/observability-adapter/.../novelgen_obs` 内部做双写：本地 OTEL span + 原有 CloudWatch EMF metric（保证既有 Alarm 不失效）。
- **MUST** 删除 `docs/ARCHITECTURE.md § 12` 中"preview / placeholder"字样。

### FR-8.6 Identity（硬性）
- **MUST** 在 CDK 部署阶段通过 `CreateWorkloadIdentity(name=novelgen-{env}-agent-workload, allowedResourceOauth2ReturnUrls=[...])` 创建 Workload Identity；返回的 `workloadIdentityArn` 写入 SSM `/novelgen/{env}/agentcore/workload-identity-arn`。
- **MUST** `WorkloadIdentityClient.get_token(resource)` 使用 `bedrock-agentcore.GetWorkloadAccessToken(workloadName, userToken?)` 获取短期 token；token 有效期由 AgentCore 控制（默认 1h），本地 LRU 缓存 token 剩余 ≥ 5min 时复用。
- **MUST** Agent → Gateway 调用链**必须**在 HTTP Authorization header 携带该 token（Gateway 配置 `authorizerConfiguration.customJWTAuthorizer` 或 `workloadIdentityAuthorizer`）；失败时禁止 fallback 到 IAM SigV4。
- **MAY** Cognito 用户 token 作为 `userToken` 入参传入 `GetWorkloadAccessToken`，实现用户身份到 Workload 的流转（用于"按 user/team 维度审计 Agent 调用"）。

---

## NFR 追加（针对 U8）

| ID | 要求 |
|---|---|
| NFR-U8-1 | AgentCore Memory `CreateEvent` p99 延迟 ≤ 1000ms；超过 → alarm `U8MemoryWriteP99`。 |
| NFR-U8-2 | AgentCore Gateway tool invocation 单次 timeout ≤ 30s；超过 → agent 侧标记该 tool 为 `degraded`，本次 chapter 跳过并进 review。 |
| NFR-U8-3 | AgentCore Browser session TTL ≤ 120s；超过 → force `StopBrowserSession`。 |
| NFR-U8-4 | Workload token cache hit 率 ≥ 95%（运行 1h 后统计）。 |
| NFR-U8-5 | Observability OTEL export 失败率 ≤ 0.1%；失败走本地 fallback（stdout log），不阻塞业务。 |
| NFR-U8-6 | 所有 AgentCore Control API 调用在 CDK 部署阶段完成一次，**不在 hot path 调用**（避免 rate limit）。 |
| NFR-U8-7 | Region：仅使用 `us-west-2`；Memory / Gateway / Runtime / Browser 资源全部单 region 部署（双 region 留 V2）。 |

---

## 简化带来的"移除/降级"清单（Architecture Simplification）

启用 AgentCore 后，以下旧实现**必须移除或降级**：

| 旧实现 | 处理方式 | 替代 |
|---|---|---|
| `AgentCoreMemoryClient.put_item` 的 NotImplementedError | **移除**，真实 SDK 调用 | `bedrock-agentcore.CreateEvent` |
| `facade_impl.py` 中 `except NotImplementedError:` 静默容错 | **移除** | 失败即 raise |
| `facade_impl.recall()` 从 OpenSearch 反推 Fact | **降级为 fallback**，主路径走 Memory | `RetrieveMemoryRecords` |
| `agentcore_registration._call_agentcore_register` NotImplementedError | **移除** | `DescribeAgentRuntime` 心跳 |
| `tier2_browser._render_with_agentcore` NotImplementedError | **移除** | `StartBrowserSession` + CDP |
| `workload_identity.get_token` NotImplementedError | **移除** | `GetWorkloadAccessToken` |
| Worker 直连 `NeptuneSignedClient` / `OpenSearchVectorClient` | **保留用于 Lambda 内部**，Agent 侧改为通过 Gateway tool 调用 | Gateway tool → Lambda → 底层 client |
| `infra/cdk/stacks/agentcore_stack.py` 的 placeholder CustomResource | **移除** | 真实 6 类 AgentCore Control API 调用 |
| `docs/ARCHITECTURE.md § 12` "preview / 占位" 表述 | **改写** | 明确 6 服务均为 GA-equivalent SDK 接入 |

---

## 不变的部分（明确边界）

- **Cognito User Pool**（FR-10.1）继续负责终端用户登录，不被 AgentCore Identity 替代；二者通过 `GetWorkloadAccessToken(userToken=<cognito-jwt>)` 衔接。
- **Step Functions** 工作流（`asl/analysis_workflow.json`）继续承担"业务流程编排 + Checkpoint"；AgentCore Runtime 只承担"LLM Agent 内部工具编排"。两者不竞争。
- **DynamoDB 多租户 SK 格式** `TEAM#{team_id}` 不变；Memory 的 namespace `{team_id}:{novel_id}` 独立一条。
- **Bedrock 模型调用**（Converse API）在 Worker 内部仍直接调用 `bedrock-runtime`；AgentCore Runtime 不是 LLM 代理层，而是"Agent 生命周期管理 + 工具编排 + 观测"层。

---

## Acceptance Criteria（必须全部满足）

1. 全项目 `grep -rn "NotImplementedError" --include="*.py"` 应返回 **0 条** 与 AgentCore 相关的命中（business logic placeholder 如 `get_character Round 2` 可保留，但必须加 TODO 标签）。
2. `cdk synth` 对 `novelgen-{env}-agentcore` stack 应产出 ≥ 6 个 `AWS::CloudFormation::CustomResource`（Memory / Gateway / Browser / Runtime×5 / WorkloadIdentity / GatewayTarget×6）。
3. 集成测试 `tests/integration/test_agentcore_e2e.py` 应覆盖：
   - Memory write → read round-trip
   - Gateway tool list (`ListGatewayTargets`)
   - Browser session lifecycle
   - Runtime InvokeAgentRuntime smoke
   - Workload token acquire & cache
4. `docs/ARCHITECTURE.md § 12` 重写，列出每个服务的 SDK API、资源命名、IAM 权限。
