# U8 Application Design Delta — AgentCore Real Integration

本文件在 `components.md` / `services.md` / `component-dependency.md` 的基础上追加。

---

## 新增组件

### C-18 AgentCoreRuntimeClient `[NEW]`
- **归属包**：`packages/agentcore-runtime-client/` `[NEW]`
- **职责**：包装 `bedrock-agentcore-control` 的 Runtime 生命周期 API + `bedrock-agentcore` 的 InvokeAgentRuntime。
- **关键方法**：
  - `ensure_runtime(name, image_uri, role_arn)` → idempotent create-or-update
  - `describe_ready(arn) -> bool`
  - `invoke(arn, session_id, trace_id, payload) -> stream`
- **被依赖方**：C-05 WorkerService / C-07 UnderstandingAgent / C-08 GenerationAgent / C-09-11 Critic/Consistency/Moderation
- **替代**：`services/worker-analysis/.../agentcore_registration.py` 的 NotImplementedError

### C-19 AgentCoreMemoryClient `[UPGRADE]`
- **归属包**：`services/worker-analysis/src/worker_analysis/memory/agentcore_memory.py`（就地升级）
- **职责**：包装 `bedrock-agentcore` 的 Memory data plane：`CreateEvent / RetrieveMemoryRecords / ListMemoryRecords`
- **关键方法**：
  - `put_event(memory_id, actor_id, session_id, payload)` 
  - `put_batch(memory_id, actor_id, session_id, items)`
  - `retrieve(memory_id, namespace, query, top_k) -> list[MemoryRecord]`
  - `list_events(memory_id, actor_id, session_id)`
- **被依赖方**：C-12 MemoryFacade

### C-20 AgentCoreGatewayClient `[NEW]`
- **归属包**：`packages/agentcore-gateway-client/` `[NEW]`
- **职责**：包装 Gateway control plane（CreateGateway / CreateGatewayTarget / ListGatewayTargets），并提供**MCP client** 供 Agent 侧通过 HTTPS 调用 Gateway（MCP over SSE）。
- **关键方法**：
  - `ensure_gateway(name, auth_config)` 
  - `ensure_target(gateway_id, name, lambda_arn, tool_schema)`
  - `invoke_tool(gateway_endpoint, token, tool_name, arguments) -> result`
- **被依赖方**：C-07 / C-08 / C-09 / C-10 / C-11

### C-21 AgentCoreBrowserClient `[UPGRADE]`
- **归属包**：`services/worker-ingestion/src/worker_ingestion/fetchers/tier2_browser.py`（就地升级）+ `packages/agentcore-browser-pool/` 保留
- **职责**：包装 `StartBrowserSession / StopBrowserSession`，用 CDP 连接 `streamEndpoint` 执行 Page.goto → Page.content。
- **关键方法**：
  - `render(url, timeout_seconds) -> html`
- **被依赖方**：C-06 IngestionModule；CDK Gateway target `ingestion-browser`

### C-22 AgentCoreIdentityClient `[UPGRADE]`
- **归属包**：`packages/auth-adapter/src/novelgen_auth/workload_identity.py`（就地升级）
- **职责**：包装 `GetWorkloadAccessToken / GetResourceOauth2Token` + 本地 LRU cache（5 分钟安全余量）。
- **关键方法**：
  - `get_token(resource: str, user_token: str | None = None) -> WorkloadToken`
  - `invalidate(resource)`
- **被依赖方**：C-15 AuthAdapter；所有通过 Gateway 调工具的组件

### C-23 AgentCoreObservabilityBootstrap `[NEW]`
- **归属包**：`packages/observability-adapter/src/novelgen_obs/otel_bootstrap.py` `[NEW]`
- **职责**：进程启动阶段初始化 OTEL SDK（TracerProvider / MeterProvider），注入 AWS X-Ray propagator，设置 OTLP exporter 指向 AgentCore Runtime sidecar。
- **关键方法**：
  - `init_observability(service_name, env)` — 幂等
- **被依赖方**：所有 worker-* 服务的 `main.py` 第一行调用

---

## 更新的组件（行为变更）

### C-12 MemoryFacade `[UPDATE]`
- 原"三路并行写 + 最宽容降级"改为"**AgentCore Memory 权威 + Neptune/OpenSearch 增强**"：
  - `remember()`：先 await `agentcore.put_batch()`（失败 **必须 raise**）→ 再 best-effort gather(graph, vector)
  - `recall()`：先 `agentcore.retrieve()`（≥1 条）→ 否则 fallback 到 OpenSearch hybrid → 最后空
- 去掉 `except NotImplementedError: ... skipping` 分支
- `get_character()` 改为先调 `agentcore.retrieve(namespace=..., query="character_snapshot character_id={id}")`

### C-15 AuthAdapter `[UPDATE]`
- 注入 C-22 AgentCoreIdentityClient，对外暴露 `ensure_token(resource)` 把 Cognito JWT 转成 Workload token。

### C-17 ObservabilityAdapter `[UPDATE]`
- 原有 CloudWatch EMF metric 保留；**新增** OTEL span/metric 双写，底层透明由 C-23 注入。

### C-06 IngestionModule `[UPDATE]`
- Tier2 的 `_render_with_agentcore` 改为调用 C-21（不再 raise NotImplementedError）。

### C-13 WorkflowOrchestrator `[UPDATE]`
- Step Functions ASL 不变；**新增**在 `LoadNovelMetadata` 之后插入 `DescribeAgentRuntime` 健康检查（失败 → retry 3 × backoff 10s → goto `FailState`）。

---

## 新增 Service（逻辑层）

### S-08 AgentCoreControlPlane `[NEW]`
- **实现载体**：`infra/cdk/stacks/agentcore_stack.py`（重写）+ 一个 one-shot CDK Lambda `agentcore-bootstrap` 负责 "需要 SDK 调用而非 L1 CFN" 的部分（若所在 region 还不支持 L1）。
- **承担**：CreateMemory / CreateGateway / CreateGatewayTarget×6 / CreateAgentRuntime×5 / CreateWorkloadIdentity / CreateBrowser（若需要自定义 browserIdentifier；否则使用 AgentCore 默认 browser）。

### S-09 AgentCoreDataPlane（聚合视图）
- 无独立实现载体，是 C-19 / C-20 / C-21 / C-22 的聚合。部署/消费分离。

---

## 依赖图增量

```
C-07 UnderstandingAgent ──invoke──▶ C-18 AgentCoreRuntimeClient
                        ──tool ──▶ C-20 AgentCoreGatewayClient ──▶ Gateway → Lambda(memory-facade/graph/vector/ddb/browser)
                        ──mem ──▶ C-12 MemoryFacade ──▶ C-19 AgentCoreMemoryClient

C-08/09/10/11 同上

C-06 IngestionModule  ──browser──▶ C-21 AgentCoreBrowserClient ──▶ StartBrowserSession (CDP)

C-15 AuthAdapter       ──token──▶ C-22 AgentCoreIdentityClient

all worker-*          ──otel ──▶ C-23 AgentCoreObservabilityBootstrap (init at main())
```

---

## Unit-of-Work 增量

新增 **U8 AgentCore Full Integration**：
- **Owner**：Platform Team（与 U1 重叠）
- **依赖**：U1（stacks、IAM role）、U2（ingestion 接 browser）、U3（understanding 接 memory/runtime）、U4（generation 接 memory/runtime）、U5（critic/consistency/moderation 接 runtime）
- **不依赖**：U6 / U7（前端不直接接 AgentCore）
- **产出**：
  - 重写 `infra/cdk/stacks/agentcore_stack.py`
  - 新增 2 个 packages：`agentcore-runtime-client`、`agentcore-gateway-client`
  - 就地升级 3 个现有 client：`agentcore_memory.py` / `workload_identity.py` / `tier2_browser.py`
  - 新增 1 个 bootstrap：`novelgen_obs/otel_bootstrap.py`
  - 新增 6 个 Gateway target Lambda：`lambdas/gateway-{memory,graph,vector,ingestion-fetch,ingestion-browser,ddb-jobs}/`
  - 修改 `services/worker-*/src/*/main.py` 开头调用 `init_observability`
  - 修改 `facade_impl.py` 移除静默容错
