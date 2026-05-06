# U1 非功能设计模式（NFR Design Patterns）

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Design
**日期**：2026-04-27

---

## 1. 多租户隔离（Tenant Isolation）

### 1.1 应用层守卫（唯一防线，D2=B）
- **API 层**：FastAPI 装饰器 `@require_team_access` 校验 path/body/query 的 team_id 与 Principal.team_id 一致
- **Adapter 层**：`TeamScopeValidator` 在 StorageAdapter 每次调用前运行时断言 key/PK 前缀以 `teams/{team_id}` 或 `TEAM#{team_id}#` 开头
- **双层失败都走标准异常 `TeamScopeViolation` → 403 + cross_team_denied metric**

### 1.2 不做 IAM 层强化（D2=B 简化）
- ECS Task Role 为每个 service 通用授予必要 AWS 资源访问（不做 per-team 细粒度 IAM）
- **风险**：一旦应用层漏校验，直接暴露跨 team 数据
- **缓解**：
  - StorageAdapter 层的运行时断言即便应用漏守卫也会拦截
  - 自动化渗透测试（US-NFR-03）强制每次部署运行
  - PR 审查强制：任何直接操作 boto3 的代码必须经过 StorageAdapter

### 1.3 Key 前缀规范
| 资源 | 前缀规范 |
|---|---|
| S3 | `teams/{team_id}/novels/{novel_id}/...` |
| DynamoDB tenancy | `PK=TEAM#{team_id}`, `SK=USER#{user_id}` 或 `NOVEL#{novel_id}` |
| DynamoDB job | `PK=TEAM#{team_id}`, `SK=JOB#{job_id}` |
| Neptune | 所有节点/边必带 property `team_id` |
| OpenSearch | 每文档带字段 `team_id`，查询强制 filter |

---

## 2. 存储模式（按领域分表，D1=B）

### 2.1 四张 DynamoDB 表
| 表 | 用途 | 主键 |
|---|---|---|
| `novelgen_tenancy` | User / Team / Novel / Chapter 元数据 | PK=`TEAM#{team_id}`, SK=`<entity>#<id>` |
| `novelgen_jobs` | Job 记录、ConcurrencyState | PK=`TEAM#{team_id}`, SK=`JOB#{job_id}` 或 `CONCURRENCY#{job_id}` |
| `novelgen_audit` | AuditEvent（不可变）| PK=`DATE#YYYYMMDD`, SK=`{timestamp}#{audit_id}` |
| `novelgen_config` | ModelConfig / ConcurrencyConfig / AlertRule / AnalysisSchema | PK=`CONFIG`, SK=`<config_type>#<version>` |

### 2.2 GSI
- `novelgen_jobs.GSI-status`：`status` + `created_at` — Admin 查询活跃/失败 job
- `novelgen_jobs.GSI-user`：`owner_user_id` + `created_at` — 用户看自己的 Job
- `novelgen_audit.GSI-actor`：`actor_user_id` + `timestamp` — 按操作人查审计
- `novelgen_tenancy.GSI-email`：`email` — 用户邮箱查询

### 2.3 audit 表 IAM 锁定
- IAM 策略：只有 `AuditWriteRole` 能 PutItem 到 `novelgen_audit`
- Admin 查询：只能 Query，不能 UpdateItem / DeleteItem
- 实现：audit 表独立为自身带来的 IAM 粒度优势

---

## 3. ConcurrencyState 共享（D3=A）

### 3.1 模式
- 每个 Analysis Job 在 `novelgen_jobs` 表写一个 `SK=CONCURRENCY#{job_id}` 项
- 字段：`current_concurrency`, `deep_read_max`, `throttle_count`, `batch_count`, `updated_at`
- Worker 读取 → 批处理 → Conditional Update（基于 `updated_at` CAS）
- 冲突时重试（短等待），避免乐观锁风暴

### 3.2 TTL 清理
- `ttl` 字段：Job 完成后 24h TTL 自动清除

---

## 4. 优雅停止（D4=A）

### 4.1 ECS Task 生命周期
```
ECS 发送 SIGTERM
    ↓
  FastAPI uvicorn：调用 lifespan.on_shutdown
    - ALB target 标记 draining（停止接收新请求）
    - 在途请求等待完成（最多 30s）
    ↓
  Worker：
    - SQS 消费者停止拉取新消息
    - 当前消息处理完后退出
    - 在途 Bedrock 调用继续完成（Bedrock 无法中断）
    ↓
  30s 后若仍有进程 → SIGKILL
```

### 4.2 保护措施
- ALB idle timeout = 600s，服务端优雅窗口 = 30s
- Worker 长耗时任务（生成章节 60s）**不在 ECS Task 内完成**：任务状态持久化到 DynamoDB，替换的 Task 可恢复

---

## 5. 异步编排模式（D6=A）

### 5.1 Step Functions 错误处理
```yaml
Retry:
  - ErrorEquals: [States.TaskFailed, Bedrock.ThrottlingException]
    IntervalSeconds: 2
    BackoffRate: 2.0
    MaxAttempts: 3
  - ErrorEquals: [States.Timeout]
    IntervalSeconds: 5
    BackoffRate: 2.0
    MaxAttempts: 2
Catch:
  - ErrorEquals: [States.ALL]
    Next: UpdateJobFailed
    ResultPath: $.error
```

### 5.2 幂等性
- Step Functions execution name = `job_id`（重复 StartExecution 报 `ExecutionAlreadyExists`）
- `POST /api/v1/novels/upload` 支持 `Idempotency-Key` header
- Fact 写入基于业务键 upsert

### 5.3 Map state 并发
- AnalysisWorkflow 的细读阶段 Map state 使用 `MaxConcurrency = :dynamic`（从 ConcurrencyState 读取）
- 支持失败容忍：`ToleratedFailurePercentage = 5`

---

## 6. 流式推送（D7=B）

### 6.1 纯服务端推送 + 客户端心跳
- **服务端 SSE**：只推业务事件（text_delta / job.completed / critique_ready），不发心跳
- **客户端 ping**：浏览器侧每 15s 主动 `GET /api/v1/healthz` 保活（ALB idle timeout 600s，比心跳间隔远大，足够安全）
- **ALB idle timeout**：600s

### 6.2 重连
- SSE 天然支持通过 `Last-Event-ID` 头部恢复
- 后端从 EventBridge/DynamoDB 的事件流中回放 lastEventId 后的事件

### 6.3 权衡说明
选 D7=B（客户端 ping）而非 A（服务端心跳）：
- 浏览器层面多一次 HTTP 请求但实现简单
- 服务端 SSE 逻辑更纯粹，只发业务事件
- 代价：每用户每分钟 4 次 ping；V1 用户量小可接受

---

## 7. 重试与熔断

### 7.1 重试层次
| 层 | 模式 |
|---|---|
| Bedrock 调用 | Converse SDK + Strands Agents 内置（指数退避 + jitter）|
| Step Functions Task | Task 内置 Retry（见 §5.1） |
| DynamoDB | boto3 默认（transient error 重试）|
| HTTP 客户端 | httpx + tenacity（backoff + 最多 3 次） |

### 7.2 熔断（降级）
- **Neptune 不可用**：MemoryFacade 切换到 DynamoDB 存储模式；仅影响图查询能力
- **OpenSearch 不可用**：MemoryFacade 切换到 DynamoDB Query；性能降级
- **Bedrock 特定模型不可用**：使用 ModelConfig 中的 `fallback` 模型
- **Circuit Breaker 实现**：pybreaker 库；阈值：5 次失败 → 30s 熔断

---

## 8. 成本护栏（metric + SNS）

### 8.1 Metric 发射（D8=A EMF）
- 所有 ApiService / WorkerService 代码通过 `ObservabilityAdapter.metric()` 发射
- 底层写 EMF 格式到 CloudWatch Logs（0 额外 API 调用成本）
- Metric Filter 抽取到 Custom Metric：`NovelGen/*`

### 8.2 关键 metric
- `bedrock_tokens_input_total{team,stage,model}`
- `bedrock_tokens_output_total{team,stage,model}`
- `bedrock_errors_total{error_type,model}`
- `cross_team_denied_total{team}`
- `job_duration_ms{type,status}`
- `http_request_duration_ms{route}`

### 8.3 Alarm → SNS
| Alarm | Metric + 阈值 | 动作 |
|---|---|---|
| JOB_TOKEN_SPIKE | 单 Job token_total > 200,000 | SNS email to admin |
| TEAM_TOKEN_HOURLY | Team 每小时 token_total > 500,000 | SNS email to admin |
| BEDROCK_ERROR_RATE | error_rate > 2%（5 min 窗口）| SNS |
| CROSS_TEAM_DENIED | denied_total > 10（5 min）| SNS |
| API_5XX_RATE | 5xx_rate > 1%（5 min）| SNS |
| BILL_ANOMALY | AWS Cost Anomaly Detection | SNS |

---

## 9. 可观测查询模式（D9=D 混合）

### 9.1 实时查询（前台 admin 面板）
- 使用 CloudWatch Metric Math + GetMetricData API
- 时间窗口：最近 1h / 24h / 7d
- 适合 admin 临时分析、告警触发后溯源

### 9.2 预聚合报表（历史成本报表）
- EventBridge Scheduler：每日 02:00 触发 Lambda / Step Functions
- 扫描前日 CloudWatch metric，按 team / 模型 / stage 聚合
- 写入 DynamoDB `novelgen_config` 表的 `AGGREGATE#{date}#{team}` 项
- Admin UI 按月查询时读此预聚合表（O(1) 延迟）

### 9.3 CloudWatch Logs Insights
- 用于深度溯源（按 request_id 查完整调用链）
- 不做日常查询入口（成本过高）

---

## 10. Secret 管理（D10=B 分层）

### 10.1 Secrets Manager（敏感）
- **Google OAuth client secret**
- **GitHub OAuth client secret**
- **第三方 API Key**（如果未来接入翻译、公版书 API）
- **数据库密码**（如果 V2 引入 RDS）
- 自动轮换：90 天（支持轮换的 secret 开启）

### 10.2 SSM Parameter Store（非敏感配置）
- Bedrock 模型 ID 映射
- 目标区域
- Feature flags
- Cognito User Pool ID、Client ID（非 secret）
- SecureString 用于中等敏感度（如内部 API token）

### 10.3 代码访问
- AuthAdapter 封装统一 `get_secret(name)` 与 `get_config(name)`
- 路径命名：`/novelgen/{env}/{category}/{name}`

---

## 11. 共享库（D5=A）

### 11.1 monorepo + uv workspace
```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = [
  "packages/*",
  "services/*",
]
```

### 11.2 服务消费
```toml
# services/api/pyproject.toml
[project]
dependencies = ["novelgen-auth-adapter", "novelgen-storage-adapter", ...]

[tool.uv.sources]
novelgen-auth-adapter = { workspace = true }
novelgen-storage-adapter = { workspace = true }
```

### 11.3 CI 保障
- PR 必须通过共享库的单元测试
- 任何 breaking change 触发所有 service 的集成测试

---

## 12. 架构模式总览

```
┌─────────────────────────────────────────────────────────────────┐
│  多租户双层守卫（API + StorageAdapter）                          │
│  ─────────────────────────────────────────────                 │
│  按领域分 4 张 DynamoDB 表（tenancy/jobs/audit/config）         │
│  ConcurrencyState 用 DynamoDB conditional update 共享          │
│  Step Functions Task-level Retry + Catch                       │
│  SSE 纯业务事件 + 客户端 15s ping                               │
│  SIGTERM 30s 优雅停止                                           │
│  EMF metric + CloudWatch Alarm + SNS                           │
│  实时 Metric Math + 每日预聚合 DynamoDB 报表                    │
│  敏感 secret → Secrets Manager；配置 → SSM Parameter Store     │
│  uv workspace 路径依赖                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. 与 Application Design 的模式映射

| Application Design §服务编排模式 | 本文对应 |
|---|---|
| §1 同步 REST | §2 DynamoDB + §4 优雅停止 |
| §2 异步长任务 | §5 Step Functions + §7 重试 |
| §3 流式生成 + Cancel | §6 SSE |
| §4 事件驱动 | §5.1 Catch → EventBridge |
| §6 Admin 配置热加载 | §11 workspace + polling |
| §7 动态并发 | §3 ConcurrencyState |
| §8 多租户强隔离 | §1 + §2.3 |
