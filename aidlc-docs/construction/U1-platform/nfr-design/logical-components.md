# U1 逻辑组件（Logical Components）

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Design
**日期**：2026-04-27

本文列出 U1 需要定义的**逻辑基础设施组件**。Infrastructure Design 阶段将把它们映射到具体 AWS 资源与 CDK 构造。

---

## 1. 网络层

### 1.1 VPC
- **名称**：`novelgen-vpc`
- **CIDR**：待 Infrastructure Design 确定（建议 `10.20.0.0/16`）
- **AZ 数**：2
- **NAT**：1 个（dev） / 1 个（prod 单 AZ）
- **DNS**：启用 `enableDnsHostnames` + `enableDnsSupport`

### 1.2 子网
| 名称 | 类型 | CIDR 建议 |
|---|---|---|
| `public-a` | Public（ALB 入口） | /24 |
| `private-a` | Private（ECS、Neptune、VPCE） | /22 |
| `isolated-a` | Isolated（预留，无 NAT） | /24 |

### 1.3 VPC Endpoints（减少 NAT 流量）
- S3 Gateway Endpoint
- DynamoDB Gateway Endpoint
- Interface Endpoints：Secrets Manager, SSM Parameter Store, CloudWatch Logs, Bedrock Runtime, STS, ECR API/DKR

### 1.4 Security Groups
| 名称 | 入站 | 出站 |
|---|---|---|
| `sg-alb` | 443 from 0.0.0.0/0 | ECS SG |
| `sg-ecs-api` | 8000 from sg-alb | All |
| `sg-ecs-worker` | 无入站 | All |
| `sg-neptune` | 8182 from sg-ecs-* | - |

---

## 2. 身份与认证

### 2.1 Cognito User Pool
- **名称**：`novelgen-users`
- **属性**：email (required, verified), custom:team_id (mutable=false after first set), custom:team_roles (mutable)
- **Groups**：`admin`, `content_moderator`（regular_user 为默认不入组）
- **IdP**：
  - Google OAuth
  - GitHub OAuth
- **Password Policy**：8+ 字符
- **MFA**：暂无
- **PreSignUp Lambda**：自动创建 Team

### 2.2 Cognito Identity Pool（可选）
- 仅当需要前端直接获取 AWS 临时凭证时启用；V1 不需要（BFF 代理）

### 2.3 AgentCore Identity
- Workload identity 配置，用于 Agent 调用下游工具

---

## 3. 存储层

### 3.1 S3 Buckets
| 名称 | 用途 | 版本化 | Lifecycle |
|---|---|---|---|
| `novelgen-novels-{env}` | 小说原文 + 生成稿 | Enabled | Intelligent-Tiering |
| `novelgen-exports-{env}` | 导出 TXT/EPUB | Disabled | Expiration 30d |
| `novelgen-audit-archive-{env}` | Audit 归档（Glacier）| Enabled | Glacier after 90d |
| `novelgen-logs-{env}` | CloudWatch Logs 导出 | Disabled | Expiration 90d |

**加密**：SSE-S3（`AES256`）
**Public Access**：全部 Block

### 3.2 DynamoDB Tables（D1=B 按领域分表）
| 表 | PK | SK | GSI | 额外 |
|---|---|---|---|---|
| `novelgen_tenancy` | `TEAM#{team_id}` | entity SK | `GSI-email` | PITR 启用 |
| `novelgen_jobs` | `TEAM#{team_id}` | `JOB#{job_id}` / `CONCURRENCY#{job_id}` | `GSI-status`, `GSI-user` | TTL 字段 |
| `novelgen_audit` | `DATE#YYYYMMDD` | `{timestamp}#{audit_id}` | `GSI-actor` | IAM 写锁 |
| `novelgen_config` | `CONFIG` | `{type}#{version}` | - | 版本化 |

**模式**：on-demand
**加密**：AWS managed KMS

### 3.3 Neptune Serverless
- **名称**：`novelgen-graph-{env}`
- **容量**：1-16 NCU（V1 范围）
- **加密**：存储加密启用
- **备份**：每日快照，保留 7 天
- **子网组**：private subnets only

### 3.4 OpenSearch Serverless Collection
- **名称**：`novelgen-vectors-{env}`
- **类型**：Vector Search
- **OCU**：2 search + 2 indexing（最低起）
- **索引**：`facts-{team_id}`（按 team 分索引，便于删除）

---

## 4. 异步编排

### 4.1 Step Functions State Machines
| 状态机 | 用途 | 类型 | 所属 Unit |
|---|---|---|---|
| `IngestionStateMachine` | 公版书下载 + URL 抓取 | Standard | U1 定义骨架，U2 填充 |
| `AnalysisStateMachine` | 粗读 → 并行分析 → 细读 → Memory | Standard | U3 |
| `OutlineStateMachine` | 大纲生成 | Standard | U4 |
| `ChapterStateMachine` | 章节流式生成 + SelfCritique | Standard | U4 |
| `ConsistencyStateMachine` | 全局一致性校验 | Standard | U5 |

**U1 交付**：在 CDK 中定义 state machine 资源骨架 + IAM Role，具体 ASL 在对应 Unit 填充。

### 4.2 SQS 队列
| 队列 | 消费者 | DLQ |
|---|---|---|
| `analysis-queue` | analysis-worker | `analysis-dlq` |
| `generation-queue` | generation-worker | `generation-dlq` |
| `critic-queue` | critic-worker | `critic-dlq` |
| `consistency-queue` | consistency-worker | `consistency-dlq` |
| `moderation-queue` | moderation-worker | `moderation-dlq` |

**参数**：
- Visibility Timeout：360s（远大于最长单任务处理时间）
- Max Receive Count：3 → DLQ
- Message Retention：4 days

### 4.3 EventBridge
- **Default Bus**
- **Rules**：
  - `generation-chapter-completed-rule` → critic-queue, moderation-queue
  - `analysis-chapter-completed-rule` → consistency-queue trigger check
  - `sse-event-forwarder-rule` → ApiService SSE endpoint
- **EventBridge Scheduler**：
  - `daily-cost-aggregator`（02:00 触发每日成本预聚合）
  - `daily-audit-archiver`（03:00 归档 90+ 天 Audit 到 Glacier）

---

## 5. 计算层

### 5.1 ECS Cluster
- **名称**：`novelgen-cluster-{env}`
- **capacity providers**：FARGATE（API）+ FARGATE_SPOT（Worker）

### 5.2 ECS Services（U1 定义基础设施；业务 Unit 补充 TaskDefinition）
| Service | 副本数（V1）| CPU/Mem | 容量提供者 |
|---|---|---|---|
| `frontend-user` | 2 | 512/1024 | FARGATE |
| `frontend-admin` | 1 | 256/512 | FARGATE |
| `api-service` | 2 | 1024/2048 | FARGATE |
| `worker-analysis` | 1 | 2048/4096 | FARGATE_SPOT |
| `worker-generation` | 1 | 2048/4096 | FARGATE_SPOT |
| `worker-critic` | 1 | 1024/2048 | FARGATE_SPOT |
| `worker-consistency` | 1 | 1024/2048 | FARGATE_SPOT |
| `worker-moderation` | 1 | 1024/2048 | FARGATE_SPOT |

**Auto Scaling**：
- API：基于 RequestCountPerTarget (ALB) 50 扩容；min=2, max=10
- Worker：基于 SQS ApproximateNumberOfMessagesVisible > 10 扩容；min=1, max=5

### 5.3 ALB + Target Groups
- **ALB**：`novelgen-alb-{env}`（internet-facing）
- **Idle Timeout**：600s（SSE 长连需求）
- **Listener**：443 (HTTPS, ACM cert)
- **Target Groups + 路径路由**：
  - `/api/v1/admin/*` → frontend-admin TG (but admin 前端是独立域，见下)
  - `/api/v1/*` → api-service TG
  - `/admin/*` → frontend-admin TG（静态资源 + admin BFF）
  - `/*` → frontend-user TG（含 NodeBff）

### 5.4 CloudFront Distribution
- 2 distributions：`app.novelgen.example.com`（User）+ `admin.novelgen.example.com`（Admin）
- Origin：ALB 对应 Target Group
- Cache Policy：
  - 静态资源：Managed-CachingOptimized
  - `/api/*` 和 `/admin/api/*`：Managed-CachingDisabled
  - SSE 路径：特殊 Origin Request Policy（透传所有 header）
- WAF：AWS Managed Rules + Rate-based rule（每 IP 2000 RPS）

### 5.5 Route 53 + ACM
- Hosted Zone：`novelgen.example.com`
- Records：A/AAAA alias 到 CloudFront
- ACM certs：通配符 `*.novelgen.example.com`

---

## 6. AgentCore 配置

### 6.1 Memory
- **Memory Namespace**：按 `team_id:novel_id` 分隔
- **Configuration**：通过 CDK 的 custom resource 调用 AgentCore API 创建

### 6.2 Gateway
- **Tools 注册**（U1 定义框架，业务 Unit 注册实际工具）：
  - 骨架：HTTP 工具、S3 读写工具、Bedrock 调用工具

### 6.3 Browser
- **Browser sessions**：按 job_id 隔离

### 6.4 Runtime
- **Agent 包**：通过 OCI image 推送到 AgentCore

### 6.5 Observability
- **Project Name**：`novelgen-{env}`
- 采集所有 Agent 调用链路

### 6.6 Identity
- **Workload Identities**：为 Browser、Gateway 外部调用配置

---

## 7. 可观测

### 7.1 CloudWatch Log Groups
| Log Group | 保留 | 用途 |
|---|---|---|
| `/aws/ecs/frontend-user` | 30d | BFF + 前端 access log |
| `/aws/ecs/frontend-admin` | 30d | Admin BFF |
| `/aws/ecs/api-service` | 30d | API 应用日志（结构化 JSON） |
| `/aws/ecs/worker-*` | 30d | Worker 应用日志 |
| `/aws/stepfunctions/*` | 90d | 状态机执行日志 |
| `/aws/lambda/pre-signup` | 30d | Cognito trigger |
| `/novelgen/metrics/emf` | 7d | EMF 格式的 metric 源日志 |

### 7.2 Metric Filters → Custom Metrics
从 `/novelgen/metrics/emf` Log Group 抽取：
- `NovelGen/BedrockTokens` (input/output by team/stage/model)
- `NovelGen/JobDuration` (by type/status)
- `NovelGen/CrossTeamDenied` (by team)
- `NovelGen/HttpRequests` (by route/status)
- `NovelGen/AgentSpan` (by agent/model)

### 7.3 CloudWatch Alarms（发送到 SNS Topic `novelgen-admin-alerts`）
| Alarm 名称 | Metric | 阈值 |
|---|---|---|
| `JobTokenSpike` | NovelGen/BedrockTokens (sum per job) | > 200,000 |
| `TeamHourlyTokenHigh` | NovelGen/BedrockTokens (sum per team per hour) | > 500,000 |
| `BedrockErrorRateHigh` | NovelGen/BedrockErrors / NovelGen/BedrockRequests | > 2% (5 min) |
| `CrossTeamDeniedHigh` | NovelGen/CrossTeamDenied | > 10 (5 min) |
| `Api5xxHigh` | ALB HTTPCode_ELB_5XX_Count / RequestCount | > 1% (5 min) |
| `EcsTargetUnhealthy` | UnHealthyHostCount | > 0 (2 min) |
| `SqsDlqNotEmpty` | SQS ApproximateNumberOfMessages (DLQ) | > 0 |
| `StepFunctionsFailures` | StatesExecutionsFailed | > 0 (5 min) |
| `NeptuneServerlessAlarm` | CPUUtilization | > 80% (10 min) |
| `DynamoDbThrottles` | ThrottledRequests | > 0 |

### 7.4 SNS Topic
- `novelgen-admin-alerts-{env}` → admin email subscriptions
- 可选：配置额外 OpsGenie / PagerDuty 订阅

### 7.5 Cost Anomaly Detection
- Monitor：`novelgen-cost-monitor`
- Subscription：邮件通知 admin，阈值 20% vs baseline

### 7.6 预聚合 Lambda
- `daily-cost-aggregator-lambda`
- 触发：EventBridge Scheduler 每天 02:00
- 输出：写入 `novelgen_config` 表的 `AGGREGATE#YYYYMMDD#{team_id}` 项

---

## 8. Secrets 与配置

### 8.1 Secrets Manager（敏感，D10=B）
| Secret 名称 | 用途 |
|---|---|
| `/novelgen/{env}/google-oauth` | Google IdP client secret |
| `/novelgen/{env}/github-oauth` | GitHub IdP client secret |
| `/novelgen/{env}/cognito-app-secret` | Cognito App Client Secret |
| `/novelgen/{env}/external-api/*` | 第三方 API Keys（如果有）|

**轮换**：支持轮换的 secret 启用 90 天自动轮换。

### 8.2 SSM Parameter Store（非敏感配置）
| Parameter | 用途 |
|---|---|
| `/novelgen/{env}/config/bedrock-region` | Bedrock 区域 |
| `/novelgen/{env}/config/model-mapping` | 默认模型映射 JSON |
| `/novelgen/{env}/config/concurrency-default` | 默认并发配置 |
| `/novelgen/{env}/config/feature-flags` | 功能开关 |
| `/novelgen/{env}/cognito/user-pool-id` | 非 secret 引用 |
| `/novelgen/{env}/cognito/user-pool-client-id` | 非 secret 引用 |

---

## 9. IAM 角色

### 9.1 ECS Task Roles
| Role | 授权 |
|---|---|
| `novelgen-api-task-role` | DynamoDB RW (所有 4 表) + S3 RW (novels bucket) + StepFunctions StartExecution + Bedrock Invoke + SSM/Secrets Read |
| `novelgen-worker-analysis-task-role` | DynamoDB RW + S3 RW + Bedrock Invoke + Neptune + OpenSearch + AgentCore |
| `novelgen-worker-generation-task-role` | 同上（可能多 EventBridge Put）|
| `novelgen-worker-critic/consistency/moderation-task-role` | 同上 |
| `novelgen-audit-write-role` | 仅 `novelgen_audit.PutItem`（独立 role）|
| `novelgen-audit-read-role` | `novelgen_audit.Query/GetItem` |
| `novelgen-frontend-task-role` | 仅 CloudWatch Logs + SSM Read |

### 9.2 Step Functions Execution Role
- `novelgen-sfn-execution-role`：sqs:SendMessage, lambda:Invoke, states:StartExecution（子状态机）

### 9.3 Lambda Roles
- `pre-signup-lambda-role`：DynamoDB PutItem to tenancy，logs

### 9.4 Service-linked roles
- AWSServiceRoleForECS
- AWSServiceRoleForApplicationAutoScaling

---

## 10. CI/CD 资源（手动部署，D5=A）

### 10.1 GitHub Actions
- workflow：`.github/workflows/ci.yaml`
  - jobs：lint, test-python, test-typescript, build-images, run-e2e
  - **不包含部署步骤**
- `dependabot.yaml`：每周检查依赖

### 10.2 ECR Repositories
| Repo | 用途 |
|---|---|
| `novelgen/frontend-user` | 用户 SPA + BFF 镜像 |
| `novelgen/frontend-admin` | Admin SPA 镜像 |
| `novelgen/api-service` | API 镜像 |
| `novelgen/worker-analysis` | Analysis Worker |
| `novelgen/worker-generation` | Generation Worker |
| `novelgen/worker-critic` | Critic Worker |
| `novelgen/worker-consistency` | Consistency Worker |
| `novelgen/worker-moderation` | Moderation Worker |

**镜像生命周期**：保留最近 20 个 tag + 最近 30 天的 untagged

### 10.3 手动部署脚本
- `scripts/deploy-dev.sh` / `scripts/deploy-prod.sh`
  - 步骤：build images → push ECR → cdk deploy
  - `scripts/deploy-prod.sh` 要求二次确认

---

## 11. 组件编号索引

- §1 网络：VPC / Subnets / VPCE / SG（4 类）
- §2 身份：Cognito User Pool / IdP / AgentCore Identity（3 类）
- §3 存储：S3 (4) / DynamoDB (4) / Neptune / OpenSearch（10 个资源）
- §4 编排：Step Functions (5) / SQS (5+5) / EventBridge Rules + Scheduler
- §5 计算：ECS Cluster / Services (8) / ALB / CloudFront (2) / Route 53 / ACM
- §6 AgentCore：6 服务配置
- §7 观测：Log Groups (6+) / Metric Filters (5) / Alarms (10) / SNS / Cost Anomaly / Aggregator Lambda
- §8 配置：Secrets (4+) / SSM Parameters (6+)
- §9 IAM：Task Roles (8+) / SFN / Lambda / Service-linked
- §10 CI/CD：GitHub Actions / ECR (8) / 部署脚本

**总计**：~80 个逻辑基础设施元素，将在 Infrastructure Design 阶段映射为具体的 CDK Construct。
