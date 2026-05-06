# U1 Platform & Infrastructure — 完成总览

**状态**：代码生成已跨 8 个阶段（A–H）全部完成。

## 交付物

### Python 共享库（`packages/`）
- `shared-types-py` — Principal、Job、Fact、AuditEvent、ModelConfig、Novel
- `auth-adapter` — Cognito JWT verifier + Principal builder + FastAPI decorators
- `storage-adapter` — S3 + DynamoDB adapter，含租户作用域 guard（US-01-04 核心）
- `observability-adapter` — 结构化 logger + EMF metrics（US-NFR-05 核心）
- `memory-facade` — 抽象接口（U3 阶段补充具体实现）

### TypeScript 共享类型（`packages/shared-types-ts`）
- 镜像后端 Python 模型，供两个 React SPA 使用

### CDK 基础设施（`infra/cdk/`，共 8 个 stack）
1. `network_stack` — VPC、子网、NAT、11 个 VPC endpoint、5 个 Security Group
2. `data_stack` — 4 张 DynamoDB 表、4 个 S3 bucket、Neptune Serverless、OpenSearch Serverless、Secrets、SSM
3. `identity_stack` — Cognito User Pool + Google/GitHub IdP + 8 个 IAM Role + PreSignUp Lambda
4. `messaging_stack` — 10 个 SQS queue、EventBridge rule、5 个 Step Functions 骨架
5. `compute_stack` — 8 个 ECR repo、ECS cluster、ALB、8 个 Fargate service（worker 使用 Spot）
6. `edge_stack` — 2 个 CloudFront distribution + WAF
7. `observability_stack` — LogGroup、metric filter、5 条 alarm、SNS、每日聚合与归档 Lambda
8. `agentcore_stack` — AgentCore 服务的占位 stack

### Lambda（`lambdas/`）
- `pre-signup` — Cognito PreSignUp 触发器，创建个人 Team 与 User 记录
- `daily-cost-aggregator` — 按 team 汇总 Bedrock token 用量（NFR-D9=D）
- `daily-audit-archiver` — 将 90 天以上的审计数据归档至 S3 Glacier

### CI/CD（`.github/workflows/`、`scripts/`）
- `ci.yaml` — lint-python、test-python、lint-ts、cdk-synth、security-scan
- `dependabot.yml`
- `bootstrap-cdk.sh`、`deploy-dev.sh`、`deploy-prod.sh`、`check-code-quality.sh`

### 测试（`tests/`）
- `tests/security/test_cross_team_access.py` — US-NFR-03 跨团队渗透矩阵
- `tests/security/test_principal_enforcement.py` — Principal 角色校验
- `tests/integration/test_u1_smoke.py` — 类型与 adapter 冒烟测试

## 已覆盖的 Stories

| Story | 状态 | 位置 |
|---|---|---|
| US-01-04 多租户强隔离 | ✅ | `storage-adapter/guards.py` + 测试 |
| US-NFR-03 跨团队请求拒绝 | ✅ | `tests/security/` |
| US-NFR-05 全栈可观测 | ✅ | `observability-adapter/` + `observability_stack.py` |
| US-00-02 协作登录（Cognito） | ✅ | `identity_stack.py` |
| US-01-02/03 协作（租户数据） | ✅ | `data_stack.py` |
| US-02-02/03 协作（AgentCore Browser 基础设施） | ⚠️ 占位 | `agentcore_stack.py` |
| US-08-01~04 协作（admin 数据表） | ✅ | `data_stack.py` 的 config 表 |
| US-NFR-04 协作（token 峰值告警） | ✅ | `observability_stack.py` |

## 下一步

- **Review 代码**（首要请求）。
- 审核通过后 → 进入 **Build and Test** 阶段（针对真实 AWS 执行测试、运行 `cdk synth/deploy`）。
- U2–U7 将复用这些共享库，并扩展 5 个 Step Functions 骨架。

## 已知遗留事项

- AgentCore Stack 目前是占位；待 CFN 资源 GA 后替换为真实 construct，或通过 AwsCustomResource 接入（U3 阶段处理）。
- Cognito 的 GitHub IdP 在部署完成后需填入真实 issuer / client ID / secret。
- ALB 在 dev 环境仅启用 HTTP；生产环境需开启 TLS 终结。
- ECS 任务目前使用公开的 Amazon Linux 占位镜像；待 U2/U4 等完成首次 `docker build && docker push` 后替换。
