# U8 NFR Design Patterns

## 1. 重试策略（所有 AgentCore data plane 调用）
- `tenacity.AsyncRetrying(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4), retry=retry_if_exception_type(TransientError))`
- `TransientError` 白名单：`ThrottlingException`, `InternalServerException`, `ServiceUnavailableException`, `botocore.exceptions.ReadTimeoutError`。

## 2. 熔断
- Gateway tool 调用若 1 分钟内失败率 > 50% 且样本 ≥ 10，**本地进程级**熔断 30s（`pybreaker` 或手写 sliding window）。熔断期间：
  - Memory tool → fallback "only local AgentCore SDK direct call"（绕过 Gateway）
  - Browser tool → 升级为 Tier 3（human-in-the-loop ticket）

## 3. Workload Token 缓存
- `cachetools.TTLCache(maxsize=128, ttl=3000)` — 50 分钟 TTL（token 名义 1h，留 10min 余量）
- key = `(workloadName, resource, user_token_hash)`
- invalidation：`401 Unauthorized` from Gateway → 立即 invalidate 并重试一次

## 4. OTEL Export Fallback
- 主 exporter：OTLP gRPC → `OTEL_EXPORTER_OTLP_ENDPOINT`
- fallback：`ConsoleSpanExporter` + stdout JSON log（CloudWatch agent 捕获）
- BatchSpanProcessor `max_export_batch_size=512`, `schedule_delay_millis=5000`

## 5. Browser Session 生命周期
```
StartBrowserSession → connect CDP → Page.goto → Page.content → StopBrowserSession (finally)
                                                               ↑ 超 120s 由 AgentCore 强制回收
```
- 使用 `asyncio.wait_for(..., timeout=100)` 留 20s 缓冲在超时前我们主动 Stop，避免僵尸。

## 6. 幂等 CDK bootstrap Lambda
- CDK 通过 `AwsCustomResource` → Lambda（不是 Python SDK custom resource）：
  - `onCreate` → 查 `ListMemories` 是否已存在同名 → 否 → Create
  - `onUpdate` → UpdateMemory（仅可变字段）
  - `onDelete` → dev=DeleteMemory，prod=no-op（RETAIN）

## 7. 多租户 Memory Namespace 隔离
- 每 team 独立 `actorId`；IAM 通过 `bedrock-agentcore:RetrieveMemoryRecords` 的 `namespace` condition 限制（见 `agentcore-control` 最新 policy element）。

## 8. IAM 条件化
- Worker Role 允许的 `actorId` 前缀用 `aws:PrincipalTag/TeamId` 映射到 `{team_id}:*` 模式（通过 ECS task role tag 注入）。V1 先开放全 team，V2 收紧。
