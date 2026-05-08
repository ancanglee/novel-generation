# U8 NFR Requirements

| ID | Area | Requirement | Metric | Threshold |
|---|---|---|---|---|
| NFR-U8-1 | Latency | Memory `CreateEvent` 写入端到端 | p99 | ≤ 1000ms |
| NFR-U8-2 | Latency | Gateway tool invocation (agent→gateway→lambda→back) | p95 | ≤ 3s；timeout 硬限 30s |
| NFR-U8-3 | Reliability | Browser session TTL | max | ≤ 120s，超出强制 Stop |
| NFR-U8-4 | Cost | Workload token cache hit | 1h 滚动 | ≥ 95% |
| NFR-U8-5 | Reliability | OTEL export 失败率 | 24h 滚动 | ≤ 0.1%；失败 → stdout fallback，不阻塞业务 |
| NFR-U8-6 | Operability | AgentCore Control API 在 hot path 调用次数 | per request | = 0 |
| NFR-U8-7 | Compliance | Memory eventExpiryDuration | — | 365d；prod RemovalPolicy=RETAIN |
| NFR-U8-8 | Security | Agent→Gateway token 失效时禁止 IAM SigV4 fallback | — | 强制 |

## Tech stack decisions

- boto3 ≥ 1.34 (支持 `bedrock-agentcore` 和 `bedrock-agentcore-control`)
- aioboto3 对齐 boto3 版本
- playwright 1.49（CDP 连接 AgentCore Browser）
- opentelemetry-sdk ≥ 1.27，opentelemetry-exporter-otlp-proto-grpc，opentelemetry-propagator-aws-xray，aws-opentelemetry-distro
- tenacity（既有）用于 Memory / Gateway / Runtime 所有 Control API 重试
- cachetools（既有）用于 token LRU

## 跨单元影响

- U3 Worker 镜像需要 +playwright + 系统依赖 libnss3 等（chromium 本地不 launch，仅做 CDP client，所以其实只需 nodejs-less 的 playwright python wheel，镜像体积增量 ~60MB）
- U1 IAM Role 需扩展：`bedrock-agentcore:GetWorkloadAccessToken`, `bedrock-agentcore:InvokeAgentRuntime`, `bedrock-agentcore:CreateEvent`, `bedrock-agentcore:RetrieveMemoryRecords`, `bedrock-agentcore:StartBrowserSession`, `bedrock-agentcore:StopBrowserSession`。
