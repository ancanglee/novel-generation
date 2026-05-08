# AgentCore SDK API 映射

以 `boto3 / aioboto3` 调用方式为准。两个服务名：
- **`bedrock-agentcore-control`**：Control plane（CRUD 资源）。
- **`bedrock-agentcore`**：Data plane（Invoke / Event / Token）。

## 1. Memory

| 操作 | 服务 | 方法 | 入参关键字段 | 我们的调用点 |
|---|---|---|---|---|
| 创建 | control | `create_memory` | `name`, `eventExpiryDuration=P365D`, `memoryStrategies=[{semanticOverride:{}},{summaryOverride:{}}]` | CDK AgentCoreStack bootstrap Lambda |
| 写事件 | data | `create_event` | `memoryId`, `actorId=f"{team}:{novel}"`, `sessionId=str(job_id)`, `payload=[{conversational:{role:USER,content:{text:json.dumps(fact)}}}]`, `eventTimestamp=utc-iso` | `AgentCoreMemoryClient.put_event` |
| 检索 | data | `retrieve_memory_records` | `memoryId`, `namespace=f"{team}/{novel}"`, `searchCriteria={searchQuery:str, topK:20}` | `AgentCoreMemoryClient.retrieve` |
| 列出 | data | `list_events` | `memoryId`, `actorId`, `sessionId`, `maxResults` | 诊断/回溯 |
| 删除 | control | `delete_memory` | `memoryId` | CDK destroy（RemovalPolicy=DESTROY for dev） |

## 2. Runtime

| 操作 | 服务 | 方法 | 入参关键字段 | 我们的调用点 |
|---|---|---|---|---|
| 创建 | control | `create_agent_runtime` | `agentRuntimeName`, `agentRuntimeArtifact={containerConfiguration:{containerUri}}`, `roleArn`, `networkConfiguration={networkMode:PUBLIC}`, `environmentVariables` | CDK bootstrap |
| 描述 | control | `get_agent_runtime` | `agentRuntimeId` | Worker 启动健康检查 |
| 调用 | data | `invoke_agent_runtime` | `agentRuntimeArn`, `runtimeSessionId`, `traceId`, `payload=bytes(json)` | 可选：`services/worker-analysis/supervisor.py` 走 Runtime 模式 |
| 更新 | control | `update_agent_runtime` | `agentRuntimeId`, `agentRuntimeArtifact` | 镜像 rollover |

> **当前模式**：Supervisor 本地运行（保留 `supervisor.py`），但进程被 AgentCore Runtime 管理（镜像部署给 Runtime，容器启动后 SDK 自动注入 env `AGENTCORE_SESSION_ID` 等）。Worker 内部对 LLM + Tool 的调用走 Gateway，不需要再调 `invoke_agent_runtime` 自己。

## 3. Gateway

| 操作 | 服务 | 方法 | 入参关键字段 | 我们的调用点 |
|---|---|---|---|---|
| 创建 Gateway | control | `create_gateway` | `name`, `protocolType=MCP`, `authorizerConfiguration={customJWTAuthorizer:{discoveryUrl,allowedAudience}}` 或 `{workloadIdentityAuthorizer:{}}`, `roleArn` | CDK bootstrap |
| 创建 Target | control | `create_gateway_target` | `gatewayIdentifier`, `name`, `targetConfiguration={mcp:{lambda:{lambdaArn,toolSchema:{inlinePayload}}}}` | 每个 Tool 一次（6 次） |
| 列出 Target | control | `list_gateway_targets` | `gatewayIdentifier` | 诊断 |
| 调用 Tool（client 侧） | — | 直接 HTTPS POST Gateway endpoint，MCP over SSE | `Authorization: Bearer <workloadToken>`, body=`{"jsonrpc":"2.0","method":"tools/call","params":{"name":...,"arguments":{...}}}` | Agent 侧 |

## 4. Browser

| 操作 | 服务 | 方法 | 入参关键字段 | 我们的调用点 |
|---|---|---|---|---|
| 启动 session | data | `start_browser_session` | `browserIdentifier=DEFAULT` 或自建, `sessionTimeoutSeconds=120`, `viewPort={width,height}` | `_render_with_agentcore` |
| 停止 session | data | `stop_browser_session` | `browserIdentifier`, `sessionId` | `finally` 块 |
| 取 live view | data | `get_browser_session` | `browserIdentifier`, `sessionId` | 诊断 / admin UI |
| 页面渲染 | — | 连接返回的 `streamEndpoint.automationStream.uri`（wss CDP）by `playwright.async_api.connect_over_cdp` → `browser.new_context().new_page().goto(url)` → `page.content()` | | `_render_with_agentcore` |

## 5. Identity

| 操作 | 服务 | 方法 | 入参关键字段 | 我们的调用点 |
|---|---|---|---|---|
| 创建 Workload | control | `create_workload_identity` | `name`, `allowedResourceOauth2ReturnUrls=[]` | CDK bootstrap |
| 取 token | data | `get_workload_access_token` | `workloadName`, `userToken?`（Cognito JWT） | `WorkloadIdentityClient.get_token` |
| 取 OAuth2 token | data | `get_resource_oauth2_token` | `workloadIdentityToken`, `resourceCredentialProviderName`, `scopes`, `oauth2Flow` | 未来扩展：接外部 OAuth2 工具 |

## 6. Observability

| 机制 | 实现 |
|---|---|
| Trace / Metric / Log 导出 | 容器环境变量 `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` 由 AgentCore Runtime sidecar 注入 |
| AWS X-Ray Propagator | `opentelemetry.propagators.aws.AwsXRayPropagator` |
| AWS Resource Detector | `opentelemetry.sdk.extension.aws.resource.AwsEcsResourceDetector` |
| 本地 bootstrap | `novelgen_obs.otel_bootstrap.init_observability(service_name, env)` |
