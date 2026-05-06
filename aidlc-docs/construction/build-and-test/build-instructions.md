# 构建指令 — NovelGen 全项目

**日期**：2026-04-30
**范围**：U1-U7 所有 Unit 的构建流程

---

## 1. 前置要求

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | 3.12+ | Services / Lambdas |
| uv | 0.4+ | Python 包管理 |
| Node.js | 20.17+ | 前端 / BFF |
| pnpm | 9.12+ | TypeScript monorepo |
| AWS CDK | 2.160+ | 基础设施即代码（IaC） |
| Docker | 24+ | 镜像构建 |
| AWS CLI | 2.x | 部署 |
| Playwright | 1.48+ | 端到端测试（`pnpm playwright install chromium webkit`） |

AWS 账号前提：Bedrock（Opus/Sonnet/Haiku）可用、目标区域已开通 AgentCore Memory/Runtime/Gateway/Browser、Neptune Serverless、OpenSearch Serverless 访问权限。

---

## 2. Python 工作区

```bash
# 1) 安装所有 Python workspace packages + services + lambdas
uv pip install --system \
    -e packages/shared-types-py \
    -e packages/auth-adapter \
    -e packages/storage-adapter \
    -e packages/observability-adapter \
    -e packages/memory-facade \
    -e packages/agentcore-browser-pool \
    -e services/api \
    -e services/worker-ingestion \
    -e services/worker-analysis \
    -e services/worker-generation \
    -e services/worker-critic \
    -e services/worker-consistency \
    -e lambdas/load-generation-context \
    -e lambdas/load-novel-metadata \
    -e lambdas/pre-signup \
    -e lambdas/daily-audit-archiver \
    -e lambdas/daily-cost-aggregator

# 2) 类型检查 + lint
ruff check packages services lambdas
mypy packages services lambdas
```

---

## 3. TypeScript 工作区

```bash
# 1) 安装依赖
pnpm install --frozen-lockfile

# 2) 类型检查（所有 workspace）
pnpm typecheck

# 3) Lint
pnpm lint   # biome check .

# 4) 基于运行中的本地 api-service 生成 @novelgen/api-client 的 OpenAPI 类型
OPENAPI_URL=http://localhost:8000/openapi.json pnpm -F @novelgen/api-client generate
```

---

## 4. Docker 镜像构建（共 10 个镜像）

统一从 monorepo 根目录构建。镜像标签：`{service}:{git_sha}`。

```bash
export GIT_SHA=$(git rev-parse --short HEAD)
export ECR="123456789012.dkr.ecr.ap-northeast-1.amazonaws.com"

# 登录 ECR
aws ecr get-login-password --region ap-northeast-1 \
  | docker login --username AWS --password-stdin "$ECR"

# Python services
for svc in api worker-ingestion worker-analysis worker-generation \
           worker-critic worker-consistency; do
  docker build -f services/$svc/Dockerfile \
    -t "$ECR/novelgen-$svc:$GIT_SHA" \
    -t "$ECR/novelgen-$svc:latest" .
  docker push "$ECR/novelgen-$svc:$GIT_SHA"
  docker push "$ECR/novelgen-$svc:latest"
done

# Node.js BFF
docker build -f apps/bff-user/Dockerfile \
  -t "$ECR/novelgen-bff-user:$GIT_SHA" \
  -t "$ECR/novelgen-bff-user:latest" .
docker push "$ECR/novelgen-bff-user:$GIT_SHA"
docker push "$ECR/novelgen-bff-user:latest"
```

---

## 5. 前端构建（两个 SPA）

```bash
# 用户端 SPA
pnpm --filter @novelgen/frontend-user build
# 产物目录：apps/frontend-user/dist/

# 管理端 SPA
pnpm --filter @novelgen/frontend-admin build
# 产物目录：apps/frontend-admin/dist/
```

部署命令（每个 SPA 各一段）：

```bash
# U6 frontend-user → /frontend 前缀
aws s3 sync apps/frontend-user/dist/ s3://novels-raw-${ENV}/frontend/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"
aws s3 cp apps/frontend-user/dist/index.html \
  s3://novels-raw-${ENV}/frontend/index.html \
  --cache-control "no-cache, must-revalidate"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/index.html"

# U7 frontend-admin → /admin 前缀
aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-${ENV}/admin/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html"
aws s3 cp apps/frontend-admin/dist/index.html \
  s3://novels-raw-${ENV}/admin/index.html \
  --cache-control "no-cache, must-revalidate"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/admin/index.html"
```

---

## 6. CDK 部署

```bash
cd infra/cdk
uv pip install -r requirements.txt   # 或使用 --group infra
export NOVELGEN_ENV=dev     # dev / stage / prod
export AWS_REGION=ap-northeast-1

cdk synth
cdk diff
cdk deploy --all --require-approval never
```

部署顺序（在单次 `cdk deploy --all` 内由 CDK 依赖图自动处理）：
NetworkStack → IdentityStack → DataStack → MessagingStack → EdgeStack → ObservabilityStack → ComputeStack → AgentCoreStack

---

## 7. 常见故障排查

| 问题 | 建议 |
|---|---|
| ECR push 报 AccessDenied | 确认本地 `aws` 配置指向目标账户；确认 IAM 具备 `ecr:*` 权限 |
| `cdk diff` 提示删除 U1 资源 | **不要 apply** — 先核对 Stack 输出引用 |
| `cdk deploy` 在 CodeBuild 中失败 | 查看 CloudFormation 控制台，通常是 IAM 或配额问题（Bedrock model invocation quota） |
| 前端构建时 React Flow / ECharts 报错 | `pnpm install` 未完成；重新执行 `pnpm -F @novelgen/ui install` |
| `pnpm install` 速度慢 | 启用 pnpm store 共享：`pnpm config set store-dir ~/.pnpm-store` |

---

## 8. 构建矩阵总览

| 资产 | 构建产物 | 部署目标 |
|---|---|---|
| Python services（6 个） | ECR Docker 镜像 | ECS Fargate |
| BFF（1 个） | ECR Docker 镜像 | ECS Fargate |
| Lambdas（5 个） | CDK inline asset | AWS Lambda |
| frontend-user SPA | `dist/` 静态文件 | S3 `/frontend/` + CloudFront |
| frontend-admin SPA | `dist/` 静态文件 | S3 `/admin/` + CloudFront |
| CDK 基础设施 | CloudFormation | AWS |
| TypeScript 共享包（4 个） | workspace 内部引用 | — |
