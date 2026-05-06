# U1 Platform & Infrastructure — 代码生成计划（Code Generation Plan）

**Unit**：U1 Platform & Infrastructure
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-27
**项目类型**：新建项目

---

## 1. 项目结构检测结果

工作区扫描：
- 根目录 `/Users/guangjul/amazon_q-workspace/novel-generation/` 下**仅有 `aidlc-docs/`**（纯文档）
- **无现有代码** → 按 新建项目 创建标准结构

### 1.1 目标代码根（monorepo + uv workspace）

```
/Users/guangjul/amazon_q-workspace/novel-generation/
├── aidlc-docs/                     ← 仅文档（禁止放代码）
├── apps/                           ← 前端应用（U6/U7 预留）
├── services/                       ← 后端服务（U1/U2/U4/U7 的 api-service 在此）
├── packages/                       ← 共享库（U1 主要产出）
├── infra/
│   └── cdk/                        ← AWS CDK (Python) 基础设施代码（U1 主要产出）
├── lambdas/                        ← Lambda 源码（PreSignUp / DailyCostAggregator / DailyAuditArchiver）
├── tests/
│   ├── integration/
│   ├── security/                   ← US-NFR-03 渗透测试
│   └── e2e/
├── scripts/                        ← 部署脚本
├── .github/
│   └── workflows/                  ← GitHub Actions CI
├── pyproject.toml                  ← uv workspace root
├── package.json                    ← pnpm workspace root（前端用）
├── README.md
├── .gitignore
└── .env.example
```

### 1.2 代码放置路径校验
- ✅ 所有代码放在 `apps/ services/ packages/ infra/ lambdas/ tests/ scripts/ .github/`
- ❌ 禁止在 `aidlc-docs/` 下生成任何代码

---

## 2. Unit 上下文

### 2.1 本 Unit 交付物（U1 范围）

**CDK 基础设施（8 Stack）**：
- `infra/cdk/` 下 Python CDK 代码
- 每 Stack 一个模块：`network_stack.py`, `data_stack.py`, `identity_stack.py`, `messaging_stack.py`, `compute_stack.py`, `edge_stack.py`, `observability_stack.py`, `agentcore_stack.py`
- Entry: `infra/cdk/app.py`

**共享 Python 库（packages/）**：
- `packages/shared-types-py/`  — pydantic models（User/Team/Principal/Job/AuditEvent/Fact/ModelConfig/ConcurrencyConfig/AlertRule）
- `packages/auth-adapter/` — Cognito JWT 验证、AgentCore Identity 封装
- `packages/storage-adapter/` — S3Adapter, DynamoDBAdapter（团队守卫）
- `packages/observability-adapter/` — 结构化日志、EMF metric、trace 辅助
- `packages/memory-facade/` — 骨架（remember/recall/upsertGraph/searchSimilar 接口；U3 实现具体逻辑）

**共享 TypeScript 库（packages/）**：
- `packages/shared-types-ts/` — TS 类型镜像
- `packages/api-client-ts/` — 从 OpenAPI 生成（骨架，CI 自动更新）
- `packages/ui/` — 空壳 + package.json（U6/U7 填充）

**Lambda 源码（lambdas/）**：
- `lambdas/pre-signup/` — Cognito PreSignUp Trigger
- `lambdas/daily-cost-aggregator/` — 每日预聚合
- `lambdas/daily-audit-archiver/` — Audit 归档到 S3 Glacier

**CI/CD**：
- `.github/workflows/ci.yaml` — lint / test / build
- `scripts/deploy-dev.sh` / `scripts/deploy-prod.sh`

**测试**：
- `tests/security/test_cross_team_access.py` — US-NFR-03 渗透
- `tests/integration/test_u1_smoke.py` — 健康检查

**项目元信息**：
- `pyproject.toml`（uv workspace root）
- `package.json`（pnpm workspace root）
- `README.md`、`.gitignore`、`.env.example`

### 2.2 依赖与前置

- **外部依赖**：AWS 账号（含 Bedrock、AgentCore、Neptune、OpenSearch 权限）
- **前置**：IAM bootstrap（CDK 的 `cdk bootstrap`）
- **对下游 Unit 的接口**：
  - `auth_adapter.verify_principal` — U2/U4/U7 Api Service 使用
  - `storage_adapter.DynamoDBRepository[T]` — 所有 Unit 使用
  - `memory_facade.MemoryFacade`（接口骨架）— U3 填充
  - `observability_adapter.metric/log/trace` — 全部 Unit 使用
  - CDK Construct：`shared_constructs/` 导出供 U2-U7 Stack 继承

### 2.3 覆盖的 Stories

- **US-01-04**（多租户强隔离）→ `storage-adapter` + 测试
- **US-NFR-03**（跨租户反例）→ `tests/security/test_cross_team_access.py`
- **US-NFR-05**（全链路可观测）→ `observability-adapter`
- **Collab**: US-00-02（Cognito 配置）、US-01-02/03（Team 切换与可见性的数据层）、US-02-02/03（Browser 基础设施）、US-08-01~04（admin 表）、US-NFR-04（metric 告警基础设施）

---

## 3. 生成步骤（按顺序执行）

### 阶段 A — 项目骨架

- [x] **Step A1**：创建 monorepo 根文件
  - `pyproject.toml`（uv workspace root + 公共 dev 依赖）
  - `package.json`（pnpm workspace root）
  - `README.md`
  - `.gitignore`（Python/Node/AWS CDK）
  - `.env.example`

### 阶段 B — Shared Types（所有 Unit 的基础）

- [x] **Step B1**：`packages/shared-types-py/` 骨架
  - `pyproject.toml`
  - `src/novelgen_types/__init__.py`
  - `src/novelgen_types/identity.py` — Principal, User, Team, Role enums
  - `src/novelgen_types/job.py` — Job, JobStatus, JobType
  - `src/novelgen_types/audit.py` — AuditEvent
  - `src/novelgen_types/fact.py` — Fact
  - `src/novelgen_types/config.py` — ModelConfig, ConcurrencyConfig, AlertRule
  - `src/novelgen_types/novel.py` — Novel 骨架
  - `src/novelgen_types/errors.py` — 统一异常（TeamScopeViolation, InvalidJobTransition 等）
  - `tests/test_types.py`

- [x] **Step B2**：`packages/shared-types-ts/` 骨架
  - `package.json`（纯 types，无运行时）
  - `src/index.ts` — 按 Python 镜像

### 阶段 C — Core Adapters（Python 共享库）

- [x] **Step C1**：`packages/auth-adapter/`
  - Cognito JWT 验证（JWKs 缓存 15min）
  - Principal 构造
  - `verify_principal` FastAPI Depends
  - `require_team_access` 装饰器
  - `require_role` 装饰器
  - AgentCore Identity workload token 封装（占位）
  - `tests/test_auth_adapter.py`

- [x] **Step C2**：`packages/storage-adapter/`
  - `S3Adapter`（put/get/presign，强制 teams/{team_id}/ 前缀断言）
  - `DynamoDBAdapter`（泛型 Repository，强制 PK 前缀断言，raise TeamScopeViolation）
  - `TeamScopeValidator` helper
  - `tests/test_storage_adapter.py`（含跨 team 断言测试）

- [x] **Step C3**：`packages/observability-adapter/`
  - 结构化 JSON logger（aws-lambda-powertools）
  - `metric()` → EMF 格式写入 CloudWatch Logs
  - `trace_context` 管理器（仅注入 request_id，不引入 X-Ray）
  - `emit_cross_team_denied` helper
  - `tests/test_obs.py`

- [x] **Step C4**：`packages/memory-facade/` 骨架
  - `MemoryFacade` 抽象类定义 + NotImplementedError 占位
  - fact_key 生成函数（character/place/edge/event/style/rule）
  - `tests/test_fact_key.py`

### 阶段 D — CDK 基础设施（8 个 Stack）

- [ ] **Step D1**：`infra/cdk/` 项目骨架
  - `app.py` — CDK App entry，加载所有 Stack
  - `cdk.json`、`pyproject.toml`
  - `shared_constructs/__init__.py` — 导出供 U2-U7 使用的 L3 Construct
  - `config.py` — env config（region, account, domain, naming）

- [ ] **Step D2**：`infra/cdk/stacks/network_stack.py` (01-NetworkStack)
  - VPC 10.20.0.0/16
  - 6 子网（public/private/isolated × 2 AZ）
  - 1 NAT Gateway
  - 9 VPC Endpoints
  - 5 Security Groups

- [ ] **Step D3**：`infra/cdk/stacks/data_stack.py` (02-DataStack)
  - 4 DynamoDB 表（tenancy / jobs / audit / config）
  - 4 S3 Buckets（novels / exports / audit-archive / logs）
  - Neptune Serverless Cluster
  - OpenSearch Serverless Collection（Vector Search）
  - 4 Secrets（Google OAuth / GitHub OAuth / Cognito App / external API placeholder）
  - 10+ SSM Parameters（region / model-mapping / feature-flags 等）

- [ ] **Step D4**：`infra/cdk/stacks/identity_stack.py` (03-IdentityStack)
  - Cognito User Pool + App Client（含 Google/GitHub IdP）
  - Cognito Groups（admin, content_moderator）
  - 8 IAM Roles（api-task / worker × 5 / audit-write / audit-read）
  - Step Functions Execution Role
  - Lambda Roles

- [ ] **Step D5**：`infra/cdk/stacks/messaging_stack.py` (04-MessagingStack)
  - 5 SQS 队列 + 5 DLQ
  - EventBridge default bus 上的 3 个 Rule
  - EventBridge Scheduler（daily-aggregator / daily-archiver）
  - 5 Step Functions State Machines（骨架 ASL，引用 infra/cdk/asl/*.json）

- [x] **Step D6**：`infra/cdk/stacks/compute_stack.py` (05-ComputeStack)
  - ECS Cluster
  - 8 ECR Repositories
  - 8 TaskDefinition + Service（FARGATE / FARGATE_SPOT 混合）
  - Auto Scaling 配置
  - ALB + Target Groups + Listener Rules
  - 优雅停止（stopTimeout=30，deregistrationDelay=30）

- [x] **Step D7**：`infra/cdk/stacks/edge_stack.py` (06-EdgeStack)
  - 2 CloudFront Distribution（user / admin，V1 默认域）
  - WAF WebACL + 关联

- [x] **Step D8**：`infra/cdk/stacks/observability_stack.py` (07-ObservabilityStack)
  - 10 Log Groups（保留期配置）
  - 5 Metric Filters
  - 10 CloudWatch Alarms
  - SNS Topic `novelgen-admin-alerts` + email subscription（从 SSM 读）
  - daily-cost-aggregator Lambda
  - daily-audit-archiver Lambda
  - Cost Anomaly Monitor + Subscription
  - Monthly Budget（$2000）

- [x] **Step D9**：`infra/cdk/stacks/agentcore_stack.py` (08-AgentCoreStack)
  - CDK Custom Resource 调用 AgentCore Control API（占位，因为不是所有 AgentCore 服务都已经有 CloudFormation resource type）
  - 创建 Memory namespace 骨架
  - 注册 Gateway 工具骨架
  - 配置 Identity workload
  - 启用 Observability project

### 阶段 E — Lambda 源码

- [x] **Step E1**：`lambdas/pre-signup/`
  - `handler.py` — Cognito PreSignUp trigger：创建 Team + 写 DynamoDB
  - `pyproject.toml`
  - `tests/test_handler.py`

- [x] **Step E2**：`lambdas/daily-cost-aggregator/`
  - `handler.py` — 查 CloudWatch GetMetricData + PutItem 到 DynamoDB `novelgen_config`
  - `tests/test_handler.py`

- [x] **Step E3**：`lambdas/daily-audit-archiver/`
  - `handler.py` — Query `novelgen_audit` 90 天前的项 + Put 到 S3 Glacier + Delete from DDB
  - `tests/test_handler.py`

### 阶段 F — CI/CD 与脚本

- [x] **Step F1**：`.github/workflows/ci.yaml`
  - Jobs：lint-python（ruff/black/mypy）/ lint-ts（biome）/ test-python / test-ts / cdk-synth / build-images

- [x] **Step F2**：`scripts/deploy-dev.sh`、`scripts/deploy-prod.sh`、`scripts/bootstrap-cdk.sh`

- [x] **Step F3**：`scripts/check-code-quality.sh`（汇总 lint+test+synth）

### 阶段 G — 测试

- [x] **Step G1**：`tests/security/test_cross_team_access.py`（US-NFR-03）
  - 构造两个 team 的 JWT
  - 遍历所有 API，尝试跨 team 访问
  - 断言所有尝试返回 403
  - 注：此处用 moto 或真实 AWS 环境均可（Markdown 中标注）

- [x] **Step G2**：`tests/integration/test_u1_smoke.py`
  - 调用 `/healthz`（假设本地 run）
  - 验证 AuthAdapter 装饰器 happy path + 跨 team 403

### Phase H — 文档

- [x] **Step H1**：`README.md` 根 + 每个 package 的 README

---

## 4. 估算

| Phase | 文件数 | 代码行（估算） |
|---|---|---|
| A 项目骨架 | ~6 | ~150 |
| B Shared Types | ~15 | ~600 |
| C Core Adapters | ~20 | ~1500 |
| D CDK Stacks | ~15 | ~3500 |
| E Lambdas | ~12 | ~800 |
| F CI/CD | ~5 | ~250 |
| G Tests | ~8 | ~600 |
| H 文档 | ~10 | ~400 |
| **合计** | **~91 个文件** | **~7800 LOC** |

U1 预计会话轮次：此次为单轮批量生成（但每个 Phase 较大），可能需要分 2-3 次交付。

---

## 5. 代码生成策略

- **严格按步骤生成**：Phase A → B → C → D → E → F → G → H
- **每个文件独立可运行**：单元测试随业务代码一起生成
- **CDK Stack 保持可 synth**：即便某些 AgentCore 资源是 Custom Resource，也要能 synth 通过
- **保持样板最小**：不引入不需要的框架/中间件
- **注释策略**：遵循 CLAUDE.md — 只在 why 非显而易见时加注释

---

## 6. 故事追溯

| Story | 实现位置 |
|---|---|
| US-01-04 多租户强隔离 | `packages/storage-adapter/` + `tests/security/` |
| US-NFR-03 跨租户反例 | `tests/security/test_cross_team_access.py` |
| US-NFR-05 全链路可观测 | `packages/observability-adapter/` + `infra/cdk/stacks/observability_stack.py` |
| US-00-02 Collab | `infra/cdk/stacks/identity_stack.py`（Cognito + IdP）|
| US-01-02/03 Collab | `infra/cdk/stacks/data_stack.py`（DynamoDB 表）|
| US-02-02/03 Collab | `infra/cdk/stacks/agentcore_stack.py`（Browser 配置）|
| US-08-01~04 Collab | `infra/cdk/stacks/data_stack.py`（config 表）+ Cognito admin group |
| US-NFR-04 Collab | `infra/cdk/stacks/observability_stack.py`（token spike alarm）|

---

## 7. 已知限制与权衡

- **AgentCore Stack** 需要 Custom Resource，CDK 不一定有原生 L1 Construct；实现时用 `AwsCustomResource` 调用 Control API（V1 可能有占位）
- **OpenSearch Serverless Encryption Policy** 有 AWS 账号级限制（每账号 100 policy），需注意
- **Neptune Serverless** 在 us-east-1 可用；但要求 IAM 认证（boto3 sigv4）
- **CDK L3 Constructs** 对 AgentCore 尚不成熟，部分资源可能需要 escape hatch（`CfnResource`）

---

## 8. 用户审批

请确认以下事项再进入 Part 2（代码生成）：

1. **代码路径**是否接受：`apps/ services/ packages/ infra/ lambdas/ tests/ scripts/ .github/`（monorepo 根）
2. **生成策略**：一次性按 Phase A→H 顺序批量生成，估计 ~91 个文件 / ~7800 LOC
3. **是否立即开始**：如果 OK，我会在下一轮直接按 Phase 顺序执行 Step A1、B1、B2、C1...

---

## Part 2 执行占位（批准后填充 checkbox 状态）

见上文 Phase A-H 各步骤 `- [ ]` checkbox。
