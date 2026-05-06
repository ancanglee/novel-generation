# U1 Platform & Infrastructure — 非功能需求（NFR Requirements）

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Requirements
**日期**：2026-04-27

---

## 1. 规模与容量

### NFR-1.1 用户规模（V1 目标）
- 活跃用户：**< 50**（内部试点）
- 并发分析任务：< 10
- 并发生成任务：< 20
- 总 Team 数：< 20
- 总 Novel 数：< 500
- 每月 Bedrock token 量：估算 ~5000 万 input + ~2000 万 output tokens

### NFR-1.2 增长预留
- 系统按支撑 **M:N 切换到中等规模**（100-500 用户）预留；V1 不预分配固定容量
- 所有存储组件选择 serverless/按需模式（Clarify 1 = B）

---

## 2. 可用性

### NFR-2.1 SLA 目标
- **99.5%**（月度，允许 ~3.6 小时不可用）
- 单 AWS 区域部署；依靠多 AZ 实现基础高可用

### NFR-2.2 灾备
- **不做 DR**（Clarify U1-N3 = A）
- 单区域故障 = 业务中断，UI 显示友好维护页
- 仅保留数据备份（DynamoDB PITR 默认启用，S3 版本化）

### NFR-2.3 Maintenance Window
- 计划内维护可在周末凌晨（Asia/Shanghai）；提前 24h 邮件通知

---

## 3. 性能

### NFR-3.1 API 延迟
| 端点类型 | p50 | p95 | p99 |
|---|---|---|---|
| 认证（AuthAdapter JWT 验证） | < 20ms | < 100ms | **< 200ms** |
| 读操作（GET /novels, /jobs 等） | < 100ms | < 300ms | < 800ms |
| 写操作（创建小说、Job） | < 200ms | < 500ms | < 1200ms |
| Admin 查询（聚合监控指标） | < 500ms | < 2s | < 5s |
| SSE 首字节 | < 200ms | < 800ms | < 2s |

### NFR-3.2 吞吐
- 峰值 API RPS：**100**（ApiService，跨所有用户与端点）
- Step Functions 同时在跑的 execution：**30**
- 每秒写 AuditEvent：< 5

### NFR-3.3 存储访问
- DynamoDB：on-demand 容量，无需预置
- S3：无吞吐限制
- Neptune Serverless：冷启动 < 5s，稳态查询 < 100ms p95
- OpenSearch Serverless：索引/查询 < 200ms p95

---

## 4. 安全

### NFR-4.1 认证
- Amazon Cognito User Pool + 社交登录（Google, GitHub）
- 所有 API 强制 JWT 验证
- JWT 过期：id_token 1h，refresh_token 30 天
- JWKs 本地缓存（15 分钟）

### NFR-4.2 授权
- 基于 Cognito Group 的全局角色：`regular_user` / `admin` / `content_moderator`
- Team 级角色通过 `custom:team_roles` claim 承载

### NFR-4.3 多租户隔离
- **硬性要求**（NFR-3 from requirements.md）
- 双层守卫：API 层装饰器 + Adapter 层运行时断言
- 跨 team 访问静默返回 403（Functional Design U1-F8=A）

### NFR-4.4 加密
- 静态加密：
  - S3：SSE-S3（AWS 默认）
  - DynamoDB：AWS managed key
  - Neptune：存储层加密（AWS managed KMS）
  - OpenSearch Serverless：存储层加密
  - Secrets Manager：KMS 托管
- 传输加密：TLS 1.2+（CloudFront / ALB / VPC 内部 service mesh 暂不做 mTLS，V2 再评估）

### NFR-4.5 PII 处理
- **无特殊合规要求**（无 GDPR/PIPL，U1-N7=A）
- email 与 display_name 允许常规存储
- 日志中 PII 允许明文（U1-N8=D）

### NFR-4.6 限流
- **不做 API 限流**（U1-N9=A 用户选择保留）
- **成本护栏 via metric**（Clarify 2 = B）：
  - 每 Job 的 token 消耗发射 CloudWatch metric
  - 配置 CloudWatch Alarm：单 Job token > 200k（阈值 admin 可调）→ SNS 通知 admin
  - 单 Team 每小时 token 累计 > 500k → SNS 通知 admin
  - 不阻止调用，仅通知

### NFR-4.7 审计
- 仅 Admin 管理操作（U1-F4=A）
- AuditEvent 表不可修改、不可删除（IAM 策略强制）
- 保留 7 年（S3 Glacier 归档）

---

## 5. 可靠性

### NFR-5.1 错误处理
- 统一错误响应格式（Functional Design R10）
- 所有 5xx 错误包含 request_id 便于追溯
- 下游失败（Bedrock throttle / Neptune 不可达 / AgentCore 异常）→ 按 R2.3 重试，耗尽后转 FAILED

### NFR-5.2 降级策略
- Neptune 不可用 → MemoryFacade 退化到仅 AgentCore Memory + DynamoDB（牺牲图查询能力）
- OpenSearch 不可用 → 退化到 DynamoDB 顺序扫描（性能降级但业务继续）
- Bedrock 限流 → 指数退避 + fallback 到备用模型（ModelConfig 中 fallback 字段）

### NFR-5.3 幂等性
- Step Functions execution name = job_id 防止重复执行
- `POST /api/v1/novels/upload` 支持 `Idempotency-Key` header
- Fact 写入基于业务键 upsert

---

## 6. 可维护性

### NFR-6.1 代码标准
- Python：black + ruff + mypy --strict + pytest，目标覆盖率 > 70%
- TypeScript：biome + tsc --strict + vitest + playwright，目标覆盖率 > 70%
- PR 必须关联 Story ID，小粒度提交

### NFR-6.2 文档
- 每个 package 有 README
- OpenAPI 规范自动生成并发布为 npm package
- CDK 构造有 docstring

### NFR-6.3 CI/CD
- **手动部署**（U1-N10=A）
  - 开发者本地 `cdk deploy` 到 dev 账号
  - prod 部署由指定工程师手动执行 `cdk deploy --profile prod`
  - GitHub Actions 仅做 lint/test/build（不自动部署）
- **回滚**：CDK 通过 CloudFormation 自动回滚失败 stack

---

## 7. 可观测性

### NFR-7.1 监控堆栈
- **AgentCore Observability**：Agent 链路 tracing、token 消耗、Agent 延迟
- **CloudWatch**：基础设施指标（ECS、DynamoDB、S3、Neptune、OpenSearch）、应用日志、自定义 metric

### NFR-7.2 关键指标（必须发射）
| Metric | 来源 | 用途 |
|---|---|---|
| `http_requests_total{status, route}` | ApiService middleware | 请求统计 |
| `http_request_duration_ms{route}` | ApiService middleware | 延迟 |
| `bedrock_tokens_total{team, stage, model}` | ObservabilityAdapter | 成本跟踪 |
| `bedrock_throttle_rate` | WorkerService | 自适应并发 |
| `job_duration_ms{type}` | WorkerService | 性能基线 |
| `cross_team_denied_total{team}` | StorageAdapter | 安全监控 |
| `agent_span_duration_ms{agent, model}` | AgentCore Obs | Agent 性能 |

### NFR-7.3 默认告警（CloudWatch Alarm → SNS）
| Alarm | 条件 |
|---|---|
| BEDROCK_ERROR_RATE_HIGH | `error_rate > 2%` 持续 5 min |
| JOB_SINGLE_TOKEN_HIGH | 单 Job token > 200k |
| TEAM_HOURLY_TOKEN_HIGH | Team 每小时 token > 500k |
| API_5XX_HIGH | `5xx_rate > 1%` 持续 5 min |
| SERVICE_UNHEALTHY | ECS target unhealthy > 2 min |
| CROSS_TEAM_DENIED_HIGH | `denied_total > 10/5min` |

---

## 8. 数据管理

### NFR-8.1 保留策略（U1-N5=B 分级）

| 数据类型 | 保留时长 | 动作 |
|---|---|---|
| 小说原文 (S3) | 永久 | - |
| 生成稿 (S3) | 永久 | - |
| Job 记录 (DynamoDB) | 90 天 | TTL → S3 Glacier 归档 |
| AuditEvent (DynamoDB) | 7 年 | 不删除 |
| CloudWatch Logs | 30 天 | 自动过期 |
| AgentCore Observability 数据 | 90 天 | 按服务策略 |
| Fact（Memory） | 与 Novel 生命周期同步 | Novel 删除时级联 |
| 向量索引（OpenSearch） | 与 Novel 生命周期同步 | Novel 删除时级联 |

### NFR-8.2 备份
- DynamoDB：PITR 启用（35 天回溯窗口）
- S3：版本化 + MFA Delete（prod 账号）
- Neptune：每日快照，保留 7 天
- OpenSearch：不主动备份（索引可从 Fact 重建）

---

## 9. 成本（U1-N12=D 不设上限 + Clarify 1 = B 按需）

### NFR-9.1 预算态度
- **不设硬预算上限**，但通过 CloudWatch Metric + Alarm 监控
- 成本责任在 Admin：订阅账单告警（AWS Cost Anomaly Detection）

### NFR-9.2 资源选型原则（B 全按需 serverless）
- DynamoDB：**on-demand** 容量
- S3：**Intelligent-Tiering**
- Neptune：**Neptune Serverless**（1-128 NCU 自动伸缩）
- OpenSearch：**Serverless**（最小 2 OCU 搜索 + 2 OCU 索引 ~$350/月）
- ECS：**Fargate + Fargate Spot 混合**（Worker 多用 Spot，API 全 Fargate）
- Bedrock：按调用付费（无预留）

### NFR-9.3 预估账单
| 项目 | 空闲（无活跃用户） | 活跃（日 10 小说分析） |
|---|---|---|
| DynamoDB on-demand | ~$10 | ~$50 |
| S3 | ~$5 | ~$30 |
| Neptune Serverless (min 1 NCU) | ~$150 | ~$400 |
| OpenSearch Serverless (2+2 OCU) | ~$350 | ~$450 |
| ECS Fargate (2 task * 0.5 vCPU) | ~$50 | ~$200 |
| CloudFront + ALB | ~$30 | ~$80 |
| Cognito | Free | Free（<50k MAU） |
| Bedrock Claude | - | ~$300-800 |
| CloudWatch | ~$20 | ~$80 |
| **合计** | **~$615/月** | **~$1590/月** |

### NFR-9.4 成本告警
- AWS Cost Anomaly Detection 启用
- 月度账单告警：$2000（超则 SNS 通知 admin）

---

## 10. 部署与运维

### NFR-10.1 部署
- 工具：AWS CDK (Python)
- 环境：单一 AWS 账号 / 两个 stage（dev、prod）
- 发布节奏：手动，按需

### NFR-10.2 IaC 覆盖
- 100% 资源用 CDK 定义（含 Cognito 配置）
- 禁止手动在 Console 修改资源（PR Review 强制）

### NFR-10.3 健康检查
- 每个 ECS Service 暴露 `/healthz`
- ALB 健康检查间隔 30s，阈值 3 次不健康即替换

---

## 11. 约束与假设

1. AWS 账户已具备 Bedrock、AgentCore（Memory/Gateway/Browser/Observability/Identity/Runtime）、Neptune、OpenSearch Serverless 的访问权限
2. 目标区域：us-east-1 或 us-west-2（待 Infrastructure Design 确认）
3. 所有其他 Unit（U2-U7）依赖 U1 定义的共享库与 CDK 构造
4. V1 为**内部试点**部署；不面向外部付费用户
5. V1 阶段**不做跨区域 DR**；接受单区故障即中断

---

## 12. 与 requirements.md 的 NFR 映射

| requirements.md NFR | U1 本文对应 |
|---|---|
| NFR-1 性能 | NFR-3 |
| NFR-2 可扩展性 | NFR-1.2 + NFR-9.2 |
| NFR-3 可靠性 | NFR-5 |
| NFR-4 安全 | NFR-4 |
| NFR-5 可观测 | NFR-7 |
| NFR-6 部署区域 | NFR-10 + §11.2 |
| NFR-7 合规免责 | NFR-4.5 |
