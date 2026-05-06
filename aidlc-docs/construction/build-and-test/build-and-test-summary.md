# Build and Test 总览 — NovelGen

**日期**：2026-04-30
**状态**：U1-U7 全部 Unit 构造完成

---

## 1. 项目交付概览

| Unit | 文件规模 | 核心交付 |
|---|---|---|
| U1 Platform & Infrastructure | CDK + 共享库 + 6 个 lambdas | VPC / Cognito / ECS / DDB / S3 / Neptune / AOSS / SQS / EventBridge / AgentCore 基础 |
| U2 Ingestion Service | `services/worker-ingestion` + API `/novels` | 上传 / 公版书 / URL 抓取（HTTP→AgentCore Browser 两级） |
| U3 Understanding Agents | `services/worker-analysis` + MemoryFacade 完整实现 | 6 个 agent + Neptune + AOSS + Strands supervisor |
| U4 Generation Agents | `services/worker-generation` + `/generations` + SSE | Outline + Chapter stream + Self-Critique + OutlineReview + Cancel + Last-Event-ID 重放 |
| U5 Critic & Consistency | `services/worker-critic` + `services/worker-consistency` + 3 个 router | Layer-2 Opus 4.7 + Sonnet 4.6 扫描 + 6 种 ConflictType + 3 次 frozen 循环保护 |
| U6 Frontend + BFF | `apps/frontend-user` + `apps/bff-user` + `packages/ui` + `packages/api-client-ts` | React SPA 7 routes + Fastify 薄 BFF + SSE 透传 + Cognito + CSRF + RUM 遥测 |
| U7 Admin Frontend + API | `apps/frontend-admin` + `services/api/routers/admin/` | 10 routes + 9 个 sub router + TransactWrite 乐观锁 + audit_view 日志 + CloudWatch 聚合 60s 缓存 |

---

## 2. 关键架构决策记录（精选）

| 编号 | 决策 | 影响 |
|---|---|---|
| U1 | 严格自动化 AC 覆盖 + monorepo + 海外区域 + CloudFront | 全项目基调 |
| U3 | F4=A / F7=A 经济版 supervisor 模式 | 合规 NFR-1 单本分析成本 |
| U4 | F1=B Strands + Supervisor，F3=B outline review 异步 | TTFT ≤ 3s + cancel 响应性 |
| U5 | F4=D / F6=C 将 Moderation 推迟到 V2 | 收敛 Scope |
| U6 | F1=A 薄 BFF + F3=A 逐 delta + F5=A React Flow + F7=A TanStack Query+Zustand + D4=B 立即遥测 | 现代 SPA 交互体验 |
| U7 | F6=C Budget 推迟 V2 + N5=C 单层 RBAC + I2=C Object Lock 推迟 V2 + I3=C MFA 推迟 V2 + D4=C 不脱敏 | **V1 admin 防线仅 3 层（Cognito JWT + FastAPI 依赖 + DDB Deny UpdateItem），需运维层面补齐** |

---

## 3. 安全基线总览（V1）

### 已实施
- Cognito JWT 全链路鉴权（KMS 签名）
- CSRF 双提交（BFF 层）
- CSP 严格（helmet）
- TLS 1.2+（CloudFront + ALB）
- 多租户三层防御（API decorator + Adapter PK guard + Memory 命名空间）
- AuditEvent 运行时不可篡改（IAM Deny UpdateItem / DeleteItem / BatchWriteItem）

### V2 待补
- Admin MFA 强制（I3=C）
- S3 Object Lock 归档审计数据（I2=C）
- PII 脱敏中间件（D4=C）
- 3 层 RBAC 纵深（N5=C → B）
- Budget 熔断（F6=C）
- Moderation 审核闭环（U5 F4=D）

---

## 4. 构建与测试命令速查

| 命令 | 用途 |
|---|---|
| `uv pip install --system -e packages/... -e services/...` | Python workspace 安装 |
| `pnpm install` | TypeScript workspace 安装 |
| `pnpm typecheck` + `pnpm lint` | TypeScript 静态检查 |
| `ruff check packages services lambdas` + `mypy ...` | Python 静态检查 |
| `pytest -q packages services` | Python 单元测试 |
| `pnpm -r test` | TypeScript 单元测试 |
| `pytest -q tests/integration` | 集成测试 |
| `pnpm exec playwright test tests/e2e` | 端到端测试 + axe-core |
| `docker build -f services/*/Dockerfile ...` | 10 个 ECR 镜像 |
| `cdk deploy --all` | 部署 AWS 资源 |
| `aws s3 sync apps/frontend-*/dist ...` | 前端发布 |
| `locust -f perf/chapter_stream.py` | 性能压测 |

---

## 5. CI/CD 流水线建议

```
feature 分支 → PR：
  lint（biome + ruff + mypy）
  typecheck（tsc --noEmit）
  unit tests（pytest + vitest）
  bundle size 检查
  lighthouse（本地 build）
  openapi diff（契约一致性）

合并到 main：
  构建 docker 镜像 → ECR
  cdk synth + diff
  cdk deploy 到 dev
  integration tests（pytest tests/integration）
  e2e tests（playwright）
  前端同步到 s3（dev）
  cloudfront 失效

定时（每夜）：
  staging 性能测试（locust + lighthouse）
  审计归档校验
  scripts/cleanup-staging.sh
```

---

## 6. 运维剧本入口（V1 最小集）

| 事件 | 响应 |
|---|---|
| `U5ConflictLoopDetected` 告警 | 进入 admin audit 查询 `admin.conflict.rewrite` 系列事件；手动解冻或让用户手写 |
| `U6-SseTtftHigh` 告警 | 检查 BFF 日志 + ApiService CloudWatch + Bedrock Throttle |
| `U7-AdminAuditWriteFailureHigh` 告警 | 立即检查 IAM 配置 + DDB 容量；零容忍 |
| Cognito admin 用户提权 | CloudTrail `AdminAddUserToGroup` 邮件告警 → 确认变更合法 |
| Bedrock 模型配额耗尽 | 切换到 fallback 模型（admin 调用 `/admin/model-configs/{stage}` PUT） |

---

## 7. 下一步路线图（V2）

### 安全补强（U7 推迟项）
1. Cognito Admin Group + MFA required
2. S3 audit-archive bucket + Object Lock governance 365d
3. `require_admin_role` 升级为 3 层（DDB admin_allowlist 二次校验）
4. PII 脱敏中间件

### 业务闭环
5. **Moderation Agent + Admin 审核队列**（U5 F4=D 解冻）
6. **Budget / Cost Guardrail**（U7 F6=C 解冻；按 team 月度预算 90%/100% 熔断）

### 观测与优化
7. SNS 主动广播模型配置变更（U7 N4=A 从 60s SSM cache 升级为实时）
8. OpenSearch 全文审计搜索（U7 F5 升级）
9. Service Worker / PWA 离线支持（U6 V1 排除）
10. Sentry 错误上报接入（U6 V1 排除）

### 国际化
11. 接入 react-i18next，补齐完整英语翻译（U6/U7 N5=A → 多语言）

---

## 8. 文档索引

所有 AI-DLC 产物位于 `aidlc-docs/`：

- **Inception**：`aidlc-docs/inception/{requirements, user-stories, application-design}/`
- **Construction per Unit**：`aidlc-docs/construction/{U1-platform, U2-ingestion, U3-understanding, U4-generation, U5-critic, U6-frontend, U7-admin}/`
- **Plans**：`aidlc-docs/construction/plans/U{N}-{stage}-plan.md`
- **State**：`aidlc-docs/aidlc-state.md`
- **Audit**：`aidlc-docs/audit.md`
- **Build & Test**：`aidlc-docs/construction/build-and-test/`（本目录）

---

## 9. 致谢与签名

**项目**：NovelGen 小说仿写生成应用
**AI-DLC 工作流**：Adaptive Software Development Workflow（AWS AIDLC）
**主要模型**：Claude Opus 4.7（主力）+ Claude Sonnet 4.6/4.7（流式 / 一致性）+ Claude Haiku 4.5（分类）
**构造轮次**：7 个 Unit 共约 50+ 次迭代会话
**文档日期**：2026-04-30
