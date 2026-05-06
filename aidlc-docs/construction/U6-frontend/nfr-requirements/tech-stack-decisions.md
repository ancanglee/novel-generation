# U6 Frontend + BFF — 技术栈决策（Tech Stack Decisions）

**Unit**：U6 Frontend + BFF
**阶段**：NFR Requirements
**日期**：2026-04-30

---

## 1. SPA（`apps/frontend-user`）

| 领域 | 选型 | 版本 | 理由 |
|---|---|---|---|
| 语言 | TypeScript | 5.6+ strict | 类型安全 + 与 OpenAPI 生成配合 |
| 框架 | React | 18.3+ | 并发特性 + useDeferredValue 对流式友好 |
| 构建工具 | Vite | 5.4+ | esbuild + rollup 组合，快 dev + code-split 默认 |
| 路由 | React Router | 6.26+ | 文件/配置混合；data router APIs |
| Server State | TanStack Query | 5.56+ | F7=A 决定 |
| Client State | Zustand | 4.5+ | F7=A 决定 |
| 样式 | Tailwind CSS | 3.4+ | 原子化 + JIT；shadcn/ui 配合 |
| 组件基础 | shadcn/ui | latest | Radix 原生 + 可复制即改 |
| 表单 | React Hook Form + zod | 7.53+ / 3.23+ | 表现 + 校验同步 |
| HTTP 客户端 | axios | 1.7+ | 拦截器 + 超时 + CSRF |
| SSE | 浏览器原生 EventSource | — | F2=A 透传；`@microsoft/fetch-event-source` 备选（若需自定义 headers） |
| 人物关系图 | React Flow (@xyflow/react) | 12+ | F5=A 决定 |
| 风格雷达 / 地图 | Apache ECharts (echarts/core + echarts-for-react) | 5.5+ / 3.0+ | F6=A 决定，按需引入 radar/geo 模块 |
| Markdown 渲染 | react-markdown + remark-gfm + rehype-sanitize | latest | 章节阅读器 + outline |
| DOMPurify | 3.1+ | — | 二次 sanitize（XSS 防御） |
| i18n | **无**（N5=A） | — | `apps/frontend-user/src/strings/` 集中维护 |
| 图标 | lucide-react | 0.441+ | 轻量 + tree-shakeable |
| 测试 | Vitest + @testing-library/react | 2.1+ | 单元 + 组件 |
| E2E | Playwright | 1.48+ | 跨浏览器 + axe 集成 |
| A11y 测试 | @axe-core/playwright | 4.10+ | N4=A 自动化 |

---

## 2. BFF（`apps/bff-user`）

| 领域 | 选型 | 版本 | 理由 |
|---|---|---|---|
| 运行时 | Node.js | 20 LTS | Fetch/Web Streams 原生；fetch SSE 优秀 |
| 框架 | Fastify | 4.28+ | 轻量高吞吐；插件体系适合鉴权/CORS/CSP |
| 会话签名 | `@fastify/secure-session` 或 `cookie-signature` | — | HS256 对称签名 |
| OIDC 流程 | `openid-client` | 5.7+ | 官方 IETF 实现 |
| HTTP 客户端（上游） | undici | 6.19+（Node 内置） | 原生 fetch，SSE stream 友好 |
| 日志 | pino | 9+ | 结构化 JSON，与 CloudWatch 配合 |
| 安全头 | `@fastify/helmet` | 11+ | CSP / HSTS |
| CORS | `@fastify/cors` | 10+ | 同源部署 + 严格 allowlist |
| 限流 | `@fastify/rate-limit` | 9+ | 防暴力登录 |
| 测试 | Vitest + supertest | 2.1+ | API 黑盒测试 |

BFF 不存业务状态，不使用 Redis / 数据库。

---

## 3. Shared Packages

| 包 | 作用 | 技术 |
|---|---|---|
| `@novelgen/types` | 与后端 pydantic 镜像的 TS 类型 | TypeScript 纯类型 |
| `@novelgen/api-client` | OpenAPI → TS 生成 | `openapi-typescript-codegen` 或 `openapi-fetch` |
| `@novelgen/ui` | 业务组件库（ConflictPanel / ChapterReader / StyleRadar 等） | React + Tailwind，与 shadcn/ui 协同 |

---

## 4. Docker / 部署

- **前端**：`apps/frontend-user` 构建产物走 `s3://novelgen-frontend-{env}` + CloudFront distribution（U1 预建）
- **BFF**：Docker `node:20-bookworm-slim`
  - 多阶段构建：builder（安装 + 编译） → runtime（仅保留 dist）
  - 目标镜像 ~ 120 MB
  - ECS Fargate：0.25 vCPU / 0.5 GB mem × 2 实例
- **CDN** 回源规则：
  - `/` → S3
  - `/api/*`、`/auth/*`、`/telemetry` → ALB → BFF
  - `/api/*/stream` → BFF（禁用 CloudFront 缓冲：origin request policy `AllViewerExceptHostHeader`）

---

## 5. CI/CD（继承 U1 GitHub Actions）

```
apps/frontend-user/
  - lint (biome)
  - typecheck (tsc --noEmit)
  - unit test (vitest run)
  - build (vite build --mode=prod)
  - bundle size check (bundlesize.json)
  - lighthouse (LHCI 3 runs median)

apps/bff-user/
  - lint + typecheck + vitest run
  - docker build (multi-arch linux/amd64)
  - push to ECR

tests/e2e/
  - playwright run (chromium / webkit / firefox)
  - axe-core assertions
```

---

## 6. 关键版本锁
`.nvmrc`: `v20.17`
`pnpm` engine: `9.12+`
`packageManager` field set in root `package.json`.

---

## 7. 排除的技术

| 不选 | 原因 |
|---|---|
| Next.js | 过重，BFF 独立便于部署拆分 |
| Redux Toolkit | F7=A 已决定用 TanStack Query + Zustand |
| Material UI | 与 shadcn/ui 重叠，且 bundle 大 |
| GraphQL | 后端为 REST + SSE，无 GQL 收益 |
| Service Worker / PWA V1 | 缓存 token 风险，先简化 |
| Sentry V1 | 先走 CloudWatch RUM 方案，未来可加 |
