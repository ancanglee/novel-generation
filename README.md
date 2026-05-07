# 小说仿写生成应用（Novel Generation App）

输入一本完整小说，分析其类型 / 人物 / 地理 / 风格，然后用 AWS Bedrock Claude 系列 + AgentCore 生成一本全新的小说。

- 前端：React SPA（用户端 U6、管理端 U7） + Fastify BFF
- 后端：Python FastAPI + 5 个 Worker（ingestion / analysis / generation / critic / consistency）+ moderation
- 异步编排：SQS + EventBridge + Step Functions
- 数据：DynamoDB × 4、S3 × 4、Neptune Serverless、OpenSearch Serverless
- 模型：Bedrock Claude Opus 4.7 / Sonnet 4.6–4.7 / Haiku 4.5
- 代理：AgentCore Memory / Runtime / Gateway / Browser（preview）

> 完整架构图与业务流请读 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 目录

- [0. 你将经历的全貌](#0-你将经历的全貌)
- [1. 环境准备（本机工具）](#1-环境准备本机工具)
- [2. AWS 账号与配额准备](#2-aws-账号与配额准备)
- [3. 克隆仓库并安装依赖](#3-克隆仓库并安装依赖)
- [4. 本地验证（不部署到 AWS）](#4-本地验证不部署到-aws)
- [5. 配置 AWS 凭证与环境变量](#5-配置-aws-凭证与环境变量)
- [6. CDK Bootstrap（每账号每区域一次）](#6-cdk-bootstrap每账号每区域一次)
- [7. 首次部署基础设施](#7-首次部署基础设施)
- [8. 回填 CDK 输出到 `.env`](#8-回填-cdk-输出到-env)
- [9. 手动配置 Cognito（一次性）](#9-手动配置-cognito一次性)
- [10. 构建并推送容器镜像到 ECR](#10-构建并推送容器镜像到-ecr)
- [11. 触发 ECS 滚动更新](#11-触发-ecs-滚动更新)
- [12. 端到端验证](#12-端到端验证)
- [13. 本地开发工作流](#13-本地开发工作流)
- [14. 生产部署](#14-生产部署)
- [15. 回滚与销毁](#15-回滚与销毁)
- [16. 已知差距 / FAQ](#16-已知差距--faq)

---

## 0. 你将经历的全貌

```
┌───────────────────────┐
│ 1. 装工具              │  Python 3.12 / uv / Node 20+ / pnpm 9+ / Docker / aws-cli v2 / AWS CDK v2
├───────────────────────┤
│ 2. 开 AWS 账号 / 配额   │  开通 Bedrock Claude 模型访问 + 要用的区域（默认 us-east-1）
├───────────────────────┤
│ 3. 克隆 + 安装          │  uv sync / pnpm install
├───────────────────────┤
│ 4. 本地编译验证         │  lint / test / cdk synth  — 纯本地，不动 AWS
├───────────────────────┤
│ 5. 配 AWS 凭证 + .env   │  profile / region / 本机 .env
├───────────────────────┤
│ 6. cdk bootstrap        │  每个 account×region 只一次
├───────────────────────┤
│ 7. cdk deploy --all     │  创建 8 个 Stack：network/identity/data/messaging/
│                         │  compute/edge/observability/agentcore
├───────────────────────┤
│ 8. 回填 Cognito/Neptune/│  从 CloudFormation Output 抄到 .env 与各服务配置里
│    OpenSearch 端点      │
├───────────────────────┤
│ 9. 手动配 Cognito IdP   │  填 Google / GitHub 真实 client_id/secret；回调 URL
├───────────────────────┤
│10. 构建 + 推 10 个镜像   │  api × 1 / worker × 5 / bff(frontend-user) × 1 / frontend-admin × 1 等
├───────────────────────┤
│11. force-new-deployment │  让 ECS 用新镜像替换 amazonlinux 占位
├───────────────────────┤
│12. 冒烟 & E2E           │  /healthz + Playwright
└───────────────────────┘
```

以下逐步展开。**按顺序执行**；第 6 步之后任何一步失败，不要急着往下走，先按 [16. 已知差距 / FAQ](#16-已知差距--faq) 排查。

---

## 1. 环境准备（本机工具）

支持 macOS 和 Linux（本项目在 macOS 14 / Ubuntu 22.04 验证过）。Windows 请用 WSL 2。

| 工具 | 最低版本 | 安装方式 | 验证 |
|---|---|---|---|
| Python | 3.12 | `brew install python@3.12` 或 pyenv | `python3.12 --version` |
| `uv`（Python workspace 管理） | 0.4+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| Node.js | 20.17+ | nvm / `brew install node@20` | `node --version` |
| `pnpm` | 9.12+ | `corepack enable && corepack prepare pnpm@9.12.0 --activate` | `pnpm --version` |
| Docker | 24+ | Docker Desktop 或 colima | `docker info` |
| AWS CLI | v2 | [官方说明](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) | `aws --version` |
| AWS CDK | v2 | `npm install -g aws-cdk` | `cdk --version` |
| jq（辅助脚本） | 1.6+ | `brew install jq` | `jq --version` |
| git | — | — | `git --version` |

可选：

- Playwright 浏览器（跑 E2E 用）：`pnpm exec playwright install chromium webkit`
- buildx（如果要交叉构建 arm64 镜像）：Docker Desktop 默认带

---

## 2. AWS 账号与配额准备

**一次性动作，在 AWS 控制台完成。**

1. **开通目标区域**。推荐 `us-east-1`（本文默认）；如需 Tokyo (`ap-northeast-1`) 须自己把模型与 AgentCore 可用性再核实一遍。
2. **开通 Bedrock 模型访问**：
   - 控制台 → Bedrock → Model access → Manage model access
   - 勾选并申请：
     - Anthropic Claude Opus 4.7（`anthropic.claude-opus-4-7-v1:0`）
     - Anthropic Claude Sonnet 4.6（`anthropic.claude-sonnet-4-6-v1:0`）
     - Anthropic Claude Sonnet 4.7（`anthropic.claude-sonnet-4-7-v1:0`）
     - Anthropic Claude Haiku 4.5（`anthropic.claude-haiku-4-5-v1:0`）
   - 等到状态变成 **Access granted**（通常 1–10 分钟）再继续。
3. **申请 AgentCore preview**：
   - 控制台 → Bedrock AgentCore → 如果提示 preview allow-list，提交申请并等待白名单通过。
   - 要用到 Memory / Runtime / Gateway / Browser 4 个子服务。
4. **配额检查**（Service Quotas 控制台）：
   - Bedrock：目标模型的 `Tokens per minute` / `Requests per minute`（按预估流量申请）
   - VPC：每区域 Elastic IP（NAT Gateway 要 1 个）
   - ECS：Fargate vCPU 配额（默认 1000，足够 dev，但 prod 要上调到 3000+）
   - Neptune Serverless：NCU 配额
   - OpenSearch Serverless：OCU 配额（每区域默认上限低，必要时申请上调）
5. **创建一个用于部署的 IAM 主体**。首次 `cdk deploy` 需要较宽权限，建议 **AdministratorAccess**（部署完之后再收紧）。可以是 SSO 角色或长期 IAM User。

---

## 3. 克隆仓库并安装依赖

```bash
git clone <repo-url> novel-generation
cd novel-generation

# Python workspace（会装所有 packages/services/lambdas 的可编辑依赖）
uv sync

# JS workspace（frontend + bff + shared packages）
pnpm install --frozen-lockfile
```

预期：

- `uv sync` 产出 `.venv/`；`uv run python -V` 应该显示 3.12.x
- `pnpm install` 产出根目录 `node_modules/` 和各个 `apps/*/node_modules/`、`packages/*/node_modules/`

---

## 4. 本地验证（不部署到 AWS）

确认工具链没有坏掉，**不花任何 AWS 的钱**。

```bash
# Python lint + type check
uv run ruff check .
uv run mypy --strict packages services lambdas

# JS lint
pnpm lint

# 单元测试（moto 模拟 DynamoDB/S3/SQS/Cognito）
uv run pytest packages services                # Python 单元测试
uv run pytest tests/integration                 # 集成测试，也走 moto
pnpm -r test                                    # TypeScript 单元测试

# CDK synth：把 8 个 stack 合成成 CloudFormation 模板，不部署
cd infra/cdk
uv run cdk synth
cd ../..
```

全绿才往下走。

---

## 5. 配置 AWS 凭证与环境变量

### 5.1 AWS Profile

在 `~/.aws/credentials` 或 `~/.aws/config` 里准备一个可以访问目标账号的 profile。SSO 和长期 Key 都行。示例：

```ini
# ~/.aws/config
[profile novelgen-dev]
region = us-east-1
sso_start_url = https://your-sso.awsapps.com/start
sso_account_id = 123456789012
sso_role_name = AdministratorAccess
```

或长期 Key：

```ini
# ~/.aws/credentials
[novelgen-dev]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

导出并验证：

```bash
export AWS_PROFILE=novelgen-dev
export AWS_REGION=us-east-1
aws sts get-caller-identity           # 看到账号 ID、user/role，就是配对了
```

> profile 名字叫什么都行，但后面所有命令都假设 `AWS_PROFILE` 已经正确导出。

### 5.2 项目级 `.env`

```bash
cp .env.example .env
```

编辑 `.env`，至少填：

```bash
AWS_REGION=us-east-1
AWS_PROFILE=novelgen-dev
ENV=dev

# 这 5 项首次部署后才有值，先留空，第 8 步回填
COGNITO_USER_POOL_ID=
COGNITO_APP_CLIENT_ID=
COGNITO_JWKS_URL=
NEPTUNE_ENDPOINT=
OPENSEARCH_ENDPOINT=

BEDROCK_REGION=us-east-1
BEDROCK_DEFAULT_MODEL=anthropic.claude-sonnet-4-6-v1:0
LOG_LEVEL=INFO
```

---

## 6. CDK Bootstrap（每账号每区域一次）

```bash
./scripts/bootstrap-cdk.sh
```

脚本内部执行 `cdk bootstrap aws://<account>/<region>`。

预期输出里能看到 `✅ Environment aws://.../us-east-1 bootstrapped`。之后同一 account + region 不必再跑。

---

## 7. 首次部署基础设施

```bash
./scripts/deploy-dev.sh
```

脚本会 `cd infra/cdk && uv run cdk deploy --all --require-approval never`。

CDK 按依赖图自动排序，大约按以下顺序创建：

```
novelgen-dev-network
  ↓
novelgen-dev-data            novelgen-dev-messaging（依赖 data+identity）
  ↓                              ↑
novelgen-dev-identity ─────────┘
  ↓
novelgen-dev-compute（依赖 network+data+identity+messaging）
  ↓
novelgen-dev-edge（依赖 compute）
novelgen-dev-observability（依赖 data+compute）
novelgen-dev-agentcore（依赖 data+identity）
```

**典型耗时**：首次 30–50 分钟，主要卡在 Neptune 集群（15 分钟+）、OpenSearch Serverless collection、CloudFront 分发（5–15 分钟）。

### 部署失败常见原因

| 症状 | 原因 / 处理 |
|---|---|
| `AccessDenied` | Profile 权限不够，换 Administrator 或给缺的权限 |
| `Bedrock model is not accessible` | 第 2 步模型访问还没批下来，等 |
| `Neptune cluster creation failed` | 账号第一次建 Neptune，配额为 0；去 Service Quotas 申请 |
| `OpenSearch collection failed: encryption policy` | 区域里 OCU 配额耗尽 |
| `VPC limit exceeded` | 账号已经有 5 个 VPC（默认上限）；删旧的或申请提升 |

失败后：修好根因，再跑一次 `./scripts/deploy-dev.sh` 即可，CDK 是幂等的。

---

## 8. 回填 CDK 输出到 `.env`

查 CloudFormation 输出：

```bash
aws cloudformation describe-stacks \
  --stack-name novelgen-dev-identity \
  --query "Stacks[0].Outputs" --output table

aws cloudformation describe-stacks \
  --stack-name novelgen-dev-data \
  --query "Stacks[0].Outputs" --output table

aws cloudformation describe-stacks \
  --stack-name novelgen-dev-edge \
  --query "Stacks[0].Outputs" --output table

aws cloudformation describe-stacks \
  --stack-name novelgen-dev-compute \
  --query "Stacks[0].Outputs" --output table
```

把下列值填回 `.env` 和各服务的 `.env`：

| CFN Output | 来自 Stack | 填到哪 |
|---|---|---|
| `UserPoolId` | identity | `.env` 的 `COGNITO_USER_POOL_ID`；BFF 的 `COGNITO_USER_POOL_ID` |
| `AppClientId` | identity | `.env` 的 `COGNITO_APP_CLIENT_ID`；BFF 的 `COGNITO_APP_CLIENT_ID` |
| `NovelsBucketName` | data | 业务配置 |
| `AossCollectionEndpoint` | data | `.env` 的 `OPENSEARCH_ENDPOINT` |
| `UserCloudFrontUrl` / `AdminCloudFrontUrl` | edge | BFF 的 `APP_BASE_URL`；Cognito 回调 URL |
| `AlbDnsName` | compute | 健康检查 / 内部调试 |

Neptune 集群端点从 SSM 拿：

```bash
aws ssm get-parameter --name /novelgen/dev/config/neptune-endpoint \
  --query Parameter.Value --output text
# 塞进 .env 的 NEPTUNE_ENDPOINT
```

Cognito JWKS URL 规则：

```
https://cognito-idp.${AWS_REGION}.amazonaws.com/${COGNITO_USER_POOL_ID}/.well-known/jwks.json
```

---

## 9. 手动配置 Cognito（一次性）

CDK 里 Google / GitHub IdP 的 `client_id` 和 issuer URL 是占位符（见 `infra/cdk/stacks/identity_stack.py` 第 80–103 行），必须在控制台换成真实值：

1. **Google**：Google Cloud Console → OAuth consent + OAuth 2.0 Client ID → 拿到 `client_id` / `client_secret`。
2. **GitHub**：GitHub → Settings → Developer settings → OAuth Apps → New OAuth App。由于 GitHub 本身不是 OIDC，这里需要一个 OAuth→OIDC 代理（例如 github-oidc-bridge）或改用 Lambda 客户化流程；V1 里这条路径是占位，需要你自己落地。
3. **Cognito User Pool → Sign-in experience → Federated identity provider sign-in**：
   - 编辑 Google IdP，填入真实 `client_id`；`client_secret` 写到 `infra/cdk/stacks/data_stack.py` 创建的 Secret `/novelgen/dev/google-oauth` 里：
     ```bash
     aws secretsmanager put-secret-value \
       --secret-id /novelgen/dev/google-oauth \
       --secret-string 'GOCSPX-real-secret-here'
     ```
   - GitHub IdP 同理。
4. **Cognito App Client → Hosted UI → Callback URL / Sign-out URL**：
   - 把 CDK 里占位的 `https://example.cloudfront.net/callback` 改成第 8 步拿到的 `UserCloudFrontUrl + /callback`；sign-out 同理。
5. **把自己设成 admin**（可选，首个管理员）：
   ```bash
   aws cognito-idp admin-add-user-to-group \
     --user-pool-id $COGNITO_USER_POOL_ID \
     --username your@email.com \
     --group-name admin
   ```

---

## 10. 构建并推送容器镜像到 ECR

CDK 首次部署时，所有 ECS TaskDefinition 用的是占位镜像 `public.ecr.aws/amazonlinux/amazonlinux:2023`（见 `infra/cdk/stacks/compute_stack.py` 第 217、302 行）。Service 能拉起来但**不会跑业务**，必须替换。

### 10.1 登录 ECR

```bash
export AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export ECR=${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com
export GIT_SHA=$(git rev-parse --short HEAD)

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR"
```

### 10.2 构建并推送 6 个 Python 镜像

仓库名称前缀是 `novelgen/`（见 `compute_stack.py` 第 52 行）。

```bash
for svc in api worker-ingestion worker-analysis worker-generation worker-critic worker-consistency; do
  REPO="$ECR/novelgen/${svc/worker-/worker-}"
  # svc 到 ECR repo 名的映射（注意 api 对应 api-service）：
  case "$svc" in
    api) REPO="$ECR/novelgen/api-service" ;;
  esac

  docker build -f services/$svc/Dockerfile \
    -t "$REPO:$GIT_SHA" \
    -t "$REPO:latest" .
  docker push "$REPO:$GIT_SHA"
  docker push "$REPO:latest"
done
```

### 10.3 构建并推送 BFF 镜像（承担 `frontend-user` ECS 服务）

```bash
docker build -f apps/bff-user/Dockerfile \
  -t "$ECR/novelgen/frontend-user:$GIT_SHA" \
  -t "$ECR/novelgen/frontend-user:latest" .
docker push "$ECR/novelgen/frontend-user:$GIT_SHA"
docker push "$ECR/novelgen/frontend-user:latest"
```

> BFF 监听 3000 端口，与 ECS `frontend-user` 服务目标端口一致。

### 10.4 frontend-admin 与 worker-moderation 镜像

当前仓库**尚未提供** `apps/frontend-admin/Dockerfile` 和 `services/worker-moderation/Dockerfile`，但 CDK 里这两个 ECS 服务已经声明。处理方式二选一：

- **临时方案**：保留占位镜像，先不部署这两个服务的业务（`frontend-admin` 只是管理端 UI，不上线不影响用户侧；`worker-moderation` 的队列会堆积消息但 V1 不阻塞主链路）。
- **正式方案**：补上 Dockerfile，参考 `apps/bff-user/Dockerfile`（frontend-admin 用同样的 Node 多阶段构建）和 `services/worker-critic/Dockerfile`（worker-moderation 用同样的 Python 3.12 基础镜像）。

> 这个差距在 [16. 已知差距 / FAQ](#16-已知差距--faq) 里也单独列出来了。

---

## 11. 触发 ECS 滚动更新

镜像推完之后，告诉 ECS 用新镜像重新拉起：

```bash
CLUSTER=novelgen-dev-cluster

for svc in novelgen-dev-api-service \
           novelgen-dev-frontend-user \
           novelgen-dev-frontend-admin \
           novelgen-dev-worker-analysis \
           novelgen-dev-worker-generation \
           novelgen-dev-worker-critic \
           novelgen-dev-worker-consistency \
           novelgen-dev-worker-moderation; do
  aws ecs update-service --cluster "$CLUSTER" --service "$svc" --force-new-deployment
done
```

观察稳态：

```bash
aws ecs describe-services --cluster "$CLUSTER" \
  --services novelgen-dev-api-service \
  --query "services[0].{d:desiredCount,r:runningCount,pending:pendingCount,deployments:length(deployments)}"
```

`runningCount == desiredCount` 且 `length(deployments) == 1` 就代表滚动完了。

---

## 12. 端到端验证

### 12.1 健康检查

```bash
USER_URL=$(aws cloudformation describe-stacks --stack-name novelgen-dev-edge \
  --query "Stacks[0].Outputs[?OutputKey=='UserCloudFrontUrl'].OutputValue" --output text)

curl -fsSL "$USER_URL/api/v1/healthz"
# 预期：{"status":"ok"}
```

### 12.2 E2E 烟囱测试

```bash
pnpm exec playwright test tests/e2e
```

需要 `$USER_URL` 指向已部署的 CloudFront。

### 12.3 手动冒烟（可选）

1. 浏览器打开 `$USER_URL`
2. 注册一个测试账号
3. 上传一本 TXT 小说（`tests/fixtures/` 里有样本）→ 触发 ingestion 流
4. 等 analysis 完成 → 创建 generation → 批准大纲 → 生成第 1 章
5. CloudWatch 看 `/novelgen/dev/worker-*` 日志有无异常

---

## 13. 本地开发工作流

### 推荐姿态：前端本地 + 后端接 dev 的 AWS

```bash
# Terminal 1 — BFF
cd apps/bff-user
cp .env.example .env     # 编辑：COGNITO_*、API_BASE_URL=http(s)://ALB 或本地 FastAPI
pnpm dev                 # http://localhost:3000

# Terminal 2 — 用户端 SPA
pnpm --filter @novelgen/frontend-user dev   # http://localhost:5173

# Terminal 3 — 管理端 SPA
pnpm --filter @novelgen/frontend-admin dev  # http://localhost:5174

# Terminal 4（可选）— 本地 FastAPI，连真实 AWS
export AWS_PROFILE=novelgen-dev AWS_REGION=us-east-1
export TENANCY_TABLE=novelgen_dev_tenancy JOBS_TABLE=novelgen_dev_jobs
export COGNITO_USER_POOL_ID=... COGNITO_APP_CLIENT_ID=...
cd services/api && uv run uvicorn novelgen_api.main:app --reload     # :8000
```

Vite dev server 会把 `/api`、`/auth`、`/telemetry` 代理到本地 BFF（`:3000`）；BFF 再代理到 FastAPI。

### 什么可以本地跑、什么不行

| 组件 | 本地可用 | 说明 |
|---|---|---|
| `apps/frontend-user`、`apps/frontend-admin` | ✅ | Vite |
| `apps/bff-user` | ✅ | 需要真实 Cognito 配置 |
| `services/api` | ✅（有限） | 本地进程调真实 DynamoDB / S3 / Cognito |
| `services/worker-*` | ❌ | 依赖 SQS / Bedrock / Neptune / OpenSearch，必须真连 AWS |
| Bedrock LLM | ❌ | 本地没有 Claude |
| AgentCore | ❌ | 只在 AWS 上 |
| SSE 流式 | ❌ | 需要 EventBridge + SQS fan-out |

### 本地单元测试（不用 AWS）

```bash
uv run pytest packages services      # 单元
uv run pytest tests/integration      # 集成（moto 模拟）
pnpm -r test                         # TS 单元
```

---

## 14. 生产部署

```bash
NOVELGEN_ENV=prod AWS_PROFILE=novelgen-prod ./scripts/deploy-prod.sh
# 交互式确认：键入 'DEPLOY-PROD'
```

**区别 dev 的地方**：

- `removal_policy=RETAIN`：删 stack 不会带走 DynamoDB / S3（audit 总是 RETAIN）
- `cdk deploy --require-approval broadening`：权限扩大类变更要人工确认
- 建议上 ACM 证书 + Route 53 alias 记录（当前 CDK 的 ALB 跑 HTTP:80，生产要自己补 HTTPS listener）

---

## 15. 回滚与销毁

### 单 Stack 回滚（代码改错了）

```bash
cd infra/cdk
uv run cdk deploy <stack-name> --rollback --require-approval never
```

### ECS 服务回滚到上个镜像

```bash
# 假设上个 tag 是 $PREV_SHA，直接改 latest 指向它再 update-service
aws ecr put-image --repository-name novelgen/api-service \
  --image-tag latest --image-manifest "$(aws ecr batch-get-image \
    --repository-name novelgen/api-service --image-ids imageTag=$PREV_SHA \
    --query 'images[0].imageManifest' --output text)"
aws ecs update-service --cluster novelgen-dev-cluster \
  --service novelgen-dev-api-service --force-new-deployment
```

### 彻底销毁 dev 环境

```bash
cd infra/cdk
uv run cdk destroy --all
# 之后手动删除 RETAIN 的资源（audit 表、audit-archive 桶）
```

---

## 16. 已知差距 / FAQ

### 16.1 当前代码库与 CDK 的已知不一致

| 点 | 现状 | 应对 |
|---|---|---|
| `apps/frontend-admin/Dockerfile` 缺失 | CDK 声明了 `frontend-admin` ECS 服务和 ECR repo，但没有 Dockerfile | 用 `apps/bff-user/Dockerfile` 作模板补一个，或暂时让该 service 跑占位 |
| `services/worker-moderation/Dockerfile` 缺失 | CDK 声明了 worker-moderation 服务 | 用 `services/worker-critic/Dockerfile` 作模板补一个；不补的话该队列消息会堆积 |
| 旧 README 里 `s3://novels-raw-${ENV}/frontend/` | 当前 CDK 根本没有创建这个 bucket，CloudFront 的 origin 是 ALB 不是 S3 | 忽略旧指示；按本 README 第 10–11 步走 ECR 路径 |
| Cognito Google/GitHub IdP | CDK 里是 `placeholder-client-id` | 第 9 步手动改 |
| Cognito Callback URL | CDK 里写死 `https://example.cloudfront.net/callback` | 第 9 步手动改为真实 CloudFront 域 |

### 16.2 常见报错

| 症状 | 处理 |
|---|---|
| `cdk deploy` 报 AccessDenied | 检查 `AWS_PROFILE` 指向的角色权限；首次部署最好用 AdministratorAccess |
| ECS 任务反复重启 / task exit code 0 | 占位镜像未替换成真实镜像，回 [第 10 步](#10-构建并推送容器镜像到-ecr) |
| ECS 任务 `CannotPullContainerError` | ECR 权限或镜像 tag 不存在；`aws ecr describe-images` 确认 tag |
| 前端 404 / 空白页 | CloudFront 还在部署（首次 5–15 分钟）；或 `frontend-user` 服务容器没跑起来 |
| Neptune 连接超时 | Neptune 只在 VPC 私有子网内可达；本地无法直连，必须通过 dev ApiService 中转 |
| Bedrock 返回 `ThrottlingException` | 区域模型配额不够；在 Service Quotas 申请，或临时换 fallback 模型 |
| `sts get-caller-identity` 报 ExpiredToken | SSO 登录过期，`aws sso login --profile novelgen-dev` |
| `uv sync` 下载 wheel 慢 | 国内环境加 `UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` |
| Playwright 首次运行报 Browser not installed | `pnpm exec playwright install chromium webkit` |

### 16.3 更多参考

- 构建 / 测试命令速查：`aidlc-docs/construction/build-and-test/`
- 架构与业务流：[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- 每个 Unit 的设计决策：`aidlc-docs/construction/U[1-7]-*/`
- CDK 层 README：`infra/cdk/README.md`

---

## AI-DLC 状态

Inception（U1–U7）与 Construction（Functional Design / NFR / Infrastructure Design / Code Generation）+ Build-and-Test 指令文档全部完成。详见 `aidlc-docs/aidlc-state.md`。Operations 阶段（部署编排、监控告警、事件响应流程）留作 V2。

## 许可证

内部使用。
