# 小说仿写生成应用（Novel Generation App）

一个小说仿写平台：采集参考小说，分析其风格与结构，并使用 AWS Bedrock Claude 系列模型与 AgentCore 生成一本新的小说。

---

## Monorepo 目录结构

| 路径 | 内容 |
|---|---|
| `apps/` | React SPA（U6 用户端、U7 管理端） + Node.js BFF |
| `services/` | Python FastAPI + 5 个 Worker（ingestion / analysis / generation / critic / consistency） |
| `packages/` | Python 与 TypeScript 共享库 |
| `infra/cdk/` | AWS CDK（Python）基础设施，共 8 个 stack |
| `lambdas/` | AWS Lambda 源码（pre-signup、daily-cost-aggregator、daily-audit-archiver 等） |
| `tests/` | 集成测试 / 安全测试 / 端到端测试 |
| `scripts/` | 部署脚本（bootstrap / deploy-dev / deploy-prod / check-code-quality） |
| `.github/workflows/` | CI 流水线 |
| `aidlc-docs/` | AI-DLC 设计文档（设计决策的唯一来源） |

## 工具链

- Python 3.12，通过 [`uv`](https://docs.astral.sh/uv/) workspace 管理
- Node 20.17+ 通过 `pnpm` 9.12+ workspace 管理
- AWS CDK v2（Python）
- Lint：`ruff`、`black`、`mypy --strict`（Python）；`biome`（TypeScript）
- 测试：`pytest`、`vitest`、`playwright`

---

## 前置要求

| 要求 | 说明 |
|---|---|
| AWS 账户 | 目标区域已开通 **Bedrock**（Claude Opus 4.7 / Sonnet 4.6/4.7 / Haiku 4.5）、**AgentCore**（Memory / Runtime / Gateway / Browser，preview）、**Neptune Serverless**、**OpenSearch Serverless** |
| AWS CLI | v2 配置好 `AWS_PROFILE` 与 `AWS_REGION`（默认 `us-east-1`） |
| 本地环境 | macOS 或 Linux；Docker 24+；`uv` 0.4+；`pnpm` 9.12+；Node 20.17+；Python 3.12+ |
| 可选 | Playwright 浏览器：`pnpm exec playwright install chromium webkit` |

> **可否纯本地运行？** 前端 / BFF 可以本地运行用于开发，但后端业务（Bedrock LLM 调用、AgentCore、SQS、Neptune、OpenSearch 等）**必须有真实 AWS 环境**。不需要 EC2 —— 生产运行在 ECS Fargate 上。详见下方「本地开发」与「部署流程」。

---

## 快速体验（编译验证）

仅确认代码与工具链可用，不部署到 AWS：

```bash
# 安装 Python 依赖
uv sync

# 安装 JS 依赖
pnpm install

# 全量 lint
uv run ruff check .
pnpm lint

# 运行测试（单元测试 + 集成测试中 moto 模拟的部分）
uv run pytest
pnpm test

# 合成 CDK（只产 CloudFormation 模板，不部署）
cd infra/cdk && uv run cdk synth
```

---

## 部署流程（完整）

### 第 1 步：AWS 凭证

```bash
export AWS_PROFILE=novelgen-dev
export AWS_REGION=us-east-1
aws sts get-caller-identity   # 验证凭证有效
```

### 第 2 步：填写环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填写：
#   AWS_REGION、AWS_PROFILE、ENV
#   COGNITO_USER_POOL_ID / COGNITO_APP_CLIENT_ID / COGNITO_JWKS_URL（首次部署后从 CDK 输出回填）
#   BEDROCK_REGION、BEDROCK_DEFAULT_MODEL
#   NEPTUNE_ENDPOINT、OPENSEARCH_ENDPOINT（同样首次部署后回填）
```

### 第 3 步：CDK Bootstrap（每个 AWS 账户仅需一次）

```bash
./scripts/bootstrap-cdk.sh
```

### 第 4 步：首次部署基础设施（创建 Cognito / Neptune / OpenSearch 等资源）

```bash
./scripts/deploy-dev.sh
# 预期 stack 顺序（由 CDK 依赖图自动编排）：
# NetworkStack → IdentityStack → DataStack → MessagingStack → EdgeStack
# → ObservabilityStack → ComputeStack → AgentCoreStack
```

**部署完成后**从 CloudFormation 输出中获取以下值回填到 `.env`：
- Cognito User Pool ID、App Client ID、JWKS URL
- Neptune endpoint
- OpenSearch endpoint
- CloudFront distribution domain
- ALB DNS

### 第 5 步：构建并推送容器镜像

> 当前 `compute_stack` 使用 Amazon Linux 占位镜像，首次部署后 ECS 任务不会真正工作。必须把真实镜像推到 ECR：

```bash
export ECR="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
export GIT_SHA=$(git rev-parse --short HEAD)

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR"

# 6 个 Python 服务
for svc in api worker-ingestion worker-analysis worker-generation \
           worker-critic worker-consistency; do
  docker build -f services/$svc/Dockerfile \
    -t "$ECR/novelgen-$svc:$GIT_SHA" \
    -t "$ECR/novelgen-$svc:latest" .
  docker push "$ECR/novelgen-$svc:$GIT_SHA"
  docker push "$ECR/novelgen-$svc:latest"
done

# Node BFF
docker build -f apps/bff-user/Dockerfile \
  -t "$ECR/novelgen-bff-user:$GIT_SHA" \
  -t "$ECR/novelgen-bff-user:latest" .
docker push "$ECR/novelgen-bff-user:$GIT_SHA"
docker push "$ECR/novelgen-bff-user:latest"

# 触发 ECS 滚动更新
aws ecs update-service --cluster novelgen-dev --service api-service --force-new-deployment
# 对每个 service 重复执行
```

### 第 6 步：构建并发布前端静态资源

```bash
# 用户端 SPA
pnpm --filter @novelgen/frontend-user build
aws s3 sync apps/frontend-user/dist/ s3://novels-raw-${ENV}/frontend/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"
aws s3 cp apps/frontend-user/dist/index.html \
  s3://novels-raw-${ENV}/frontend/index.html \
  --cache-control "no-cache, must-revalidate"

# 管理端 SPA
pnpm --filter @novelgen/frontend-admin build
aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-${ENV}/admin/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"
aws s3 cp apps/frontend-admin/dist/index.html \
  s3://novels-raw-${ENV}/admin/index.html \
  --cache-control "no-cache, must-revalidate"

# CloudFront 失效
export DIST_ID="<CDK 输出的 CloudFront distribution id>"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" \
  --paths "/index.html" "/admin/index.html"
```

### 第 7 步：配置 Cognito（一次性手动操作）

- 登录 AWS 控制台 → Cognito User Pool → 填入 Google / GitHub IdP 的真实 `client_id` / `client_secret`
- 如需管理员账户，手动把目标用户的 `custom:global_role` 设为 `admin`

### 第 8 步：验证

```bash
# 健康检查
curl "https://<CloudFront 域名>/api/v1/healthz"

# 端到端烟囱测试（需要前面的 stack 都已生效）
pnpm exec playwright test tests/e2e
```

### 生产部署

```bash
NOVELGEN_ENV=prod ./scripts/deploy-prod.sh
# 需键入 'DEPLOY-PROD' 确认
```

> **完整构建 / 测试 / 运维命令速查**：见 `aidlc-docs/construction/build-and-test/`（build-instructions、unit-test-instructions、integration-test-instructions、performance-test-instructions、build-and-test-summary）。

---

## 本地开发

### 推荐姿态：前端本地 + 后端接 staging AWS

1. **启动用户端 BFF**（连 staging ApiService + staging Cognito）
   ```bash
   # 在 apps/bff-user 下准备 .env，填好 staging 的 Cognito / ApiService URL
   pnpm --filter @novelgen/bff-user dev   # http://localhost:3000
   ```

2. **启动用户端 SPA**
   ```bash
   pnpm --filter @novelgen/frontend-user dev   # http://localhost:5173
   ```
   Vite dev server 会把 `/api`、`/auth`、`/telemetry` 代理到本地 BFF（`:3000`）。

3. **启动管理端 SPA**
   ```bash
   pnpm --filter @novelgen/frontend-admin dev   # http://localhost:5174
   ```

4. **本地启动 ApiService（可选，绕过 staging）**
   ```bash
   export AWS_REGION=us-east-1 AWS_PROFILE=novelgen-dev
   export TENANCY_TABLE=novelgen_tenancy_dev JOBS_TABLE=novelgen_jobs_dev
   export COGNITO_USER_POOL_ID=... COGNITO_APP_CLIENT_ID=...
   cd services/api && uv run uvicorn novelgen_api.main:app --reload   # :8000
   ```
   > 即使本地启动 ApiService，它仍会调真实 DynamoDB / S3 / Cognito；只是不用 AWS 上的容器。

### 可本地运行 / 不可本地运行

| 组件 | 本地可用 | 说明 |
|---|---|---|
| `apps/frontend-user`、`apps/frontend-admin` | ✅ | Vite dev server |
| `apps/bff-user`（Fastify BFF） | ✅ | 需要真实 Cognito 配置 |
| `services/api`（FastAPI） | ✅（有限） | 需要 AWS 凭证调 DynamoDB / S3 |
| `services/worker-*`（6 个 Worker） | ❌ | 依赖 SQS / Bedrock / Neptune / OpenSearch，不真连 AWS 无法工作 |
| Bedrock LLM 调用 | ❌ | 无本地 Claude 模型 |
| AgentCore（Memory / Runtime / Gateway / Browser） | ❌ | 仅在 AWS 上提供 |
| SSE 流式链路 | ❌ | 依赖 EventBridge + SQS fan-out |

### 本地单元测试（无需 AWS）

`pytest` 默认使用 `moto` 模拟 DynamoDB / S3 / SQS / Cognito：

```bash
uv run pytest packages services      # 单元测试
uv run pytest tests/integration      # 集成测试（moto 模拟）
pnpm -r test                         # TypeScript 单元测试
```

### 常见问题

| 症状 | 处理 |
|---|---|
| `cdk deploy` 报 AccessDenied | 检查 `AWS_PROFILE` / IAM 权限；首次部署需 admin 权限 |
| ECS 任务反复重启 | 占位镜像未替换为真实镜像，回到「部署流程第 5 步」 |
| 前端 404 | CloudFront 未 invalidate，或 S3 sync 未指定 `/frontend/` / `/admin/` 前缀 |
| Neptune 连接超时 | Neptune 仅在 VPC 私有子网内可访问；本地开发无法直连，需通过 staging ApiService 中转 |
| Bedrock 返回 ThrottlingException | 目标区域的模型配额不足；切换 fallback 模型或申请配额 |

---

## AI-DLC 状态

全部 7 个 Unit（U1–U7）的 Construction 阶段已完成（Functional Design / NFR Requirements / NFR Design / Infrastructure Design / Code Generation），Build-and-Test 指令文档已生成。详见 `aidlc-docs/aidlc-state.md`。

## 许可证

内部使用。
