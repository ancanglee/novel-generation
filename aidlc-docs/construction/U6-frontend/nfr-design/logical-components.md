# U6 Frontend + BFF — 逻辑组件（Logical Components）

**Unit**：U6 Frontend + BFF
**阶段**：NFR Design
**日期**：2026-04-30

---

## 1. SPA 组件结构（`apps/frontend-user`）

```
apps/frontend-user/
├── src/
│   ├── main.tsx                    # 入口；注入 QueryClient / Router / Error Boundary
│   ├── router.tsx                  # React Router v6 data router + lazy routes
│   ├── layouts/
│   │   ├── RootLayout.tsx          # TopBar + Sidebar + <Outlet>
│   │   └── ChapterLayout.tsx       # 双栏：Editor + ConflictPanel
│   ├── pages/
│   │   ├── Dashboard.tsx           # 首屏同步
│   │   ├── novels/                 # chunk-novels
│   │   │   ├── index.tsx           # /novels 列表
│   │   │   ├── NovelDetail.tsx
│   │   │   └── IngestForm.tsx
│   │   ├── analysis/               # chunk-analysis（含 React Flow）
│   │   │   ├── index.tsx
│   │   │   ├── CharacterGraph.tsx  # React Flow
│   │   │   ├── StyleRadar.tsx      # ECharts radar
│   │   │   └── GeoMap.tsx          # ECharts geo
│   │   ├── outline/
│   │   ├── chapter/                # 章节生成与审阅
│   │   │   ├── ChapterPage.tsx
│   │   │   ├── ChapterStream.tsx   # 逐 delta 渲染
│   │   │   ├── useChapterStream.ts
│   │   │   └── ConflictPanel.tsx
│   │   ├── reader/                 # chunk-reader
│   │   └── settings/
│   ├── components/
│   │   ├── ui/                     # shadcn/ui re-exports
│   │   ├── TopBar.tsx
│   │   ├── TeamPicker.tsx
│   │   ├── JobPoller.tsx
│   │   ├── ErrorBoundary.tsx
│   │   └── Toast.tsx
│   ├── stores/
│   │   ├── sessionStore.ts
│   │   ├── chapterStreamStore.ts
│   │   ├── conflictPanelStore.ts
│   │   └── modalStore.ts
│   ├── lib/
│   │   ├── api.ts                  # axios instance + 拦截器（401 redirect / 429 retry）
│   │   ├── sse.ts                  # openChapterStream()
│   │   ├── telemetry.ts            # emit() — D4=B 立即发送
│   │   ├── queryKeys.ts            # qk.*
│   │   └── csrf.ts                 # getCsrfToken() from cookie
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useNovels.ts            # TanStack Query wrapper
│   │   └── ...
│   ├── strings/                    # N5=A 中文文案集中
│   │   ├── common.ts
│   │   ├── chapter.ts
│   │   ├── conflict.ts
│   │   └── index.ts
│   └── styles/
│       └── globals.css             # Tailwind + base
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── tests/
```

---

## 2. BFF 组件结构（`apps/bff-user`）

```
apps/bff-user/
├── src/
│   ├── server.ts                   # Fastify app create + listen
│   ├── config.ts                   # env 读取 + 校验（zod）
│   ├── session/
│   │   ├── store.ts                # LRU cache (D1=A)
│   │   ├── middleware.ts           # 验签 + refresh token flow
│   │   └── cookies.ts              # HS256 sign/verify
│   ├── routes/
│   │   ├── auth.ts                 # /auth/login, /auth/callback, /auth/me, /auth/logout
│   │   ├── telemetry.ts            # /telemetry EMF 写入
│   │   └── proxy.ts                # /api/* 反向代理
│   ├── proxy/
│   │   ├── standard.ts             # proxyToApi()
│   │   └── sse.ts                  # proxySse()
│   ├── security/
│   │   ├── helmet.ts
│   │   ├── csrf.ts
│   │   └── rateLimit.ts
│   └── telemetry/
│       └── emf.ts
├── Dockerfile
├── package.json
├── tsconfig.json
└── tests/
```

---

## 3. Shared 包（`packages/*`）

| 包 | 作用 | 依赖 |
|---|---|---|
| `@novelgen/types` | TS 类型镜像后端 pydantic | 无 |
| `@novelgen/api-client` | OpenAPI → TS fetch client | `@novelgen/types` |
| `@novelgen/ui` | 业务组件（ConflictPanel / StyleRadar / ChapterReader / CharacterGraph） | React, shadcn/ui, react-flow, echarts |

---

## 4. 路由与 Chunk 映射（D2=A）

| 路由 | Chunk 名 | 预估 gzipped |
|---|---|---|
| `/` Dashboard | 首屏 | 200 KB |
| `/novels`, `/novels/:id`, `/novels/:id/ingest` | `chunk-novels` | 40 KB |
| `/novels/:id/analysis` | `chunk-analysis` | 180 KB（React Flow + 按需 ECharts） |
| `/generations/:gid/outline` | `chunk-outline` | 30 KB |
| `/generations/:gid/chapters/:n` | `chunk-chapter` | 80 KB（含 markdown 编辑 + SSE hook） |
| `/read/:gid` | `chunk-reader` | 60 KB（markdown 渲染 + 主题） |
| `/settings` | `chunk-settings` | 20 KB |

首屏 gzip **200 KB** 可覆盖 React + TanStack Query + Zustand + Router + Tailwind runtime + shadcn/ui 核心 + Layout + 鉴权 + Dashboard。

---

## 5. Cookie 清单

| Cookie | HttpOnly | Secure | SameSite | Path | Max-Age | 作用 |
|---|---|---|---|---|---|---|
| `sid` | ✅ | ✅ | Lax | `/` | 86400 | HS256 签名 session id |
| `csrf` | ❌ | ✅ | Strict | `/` | 86400 | 双提交 CSRF token 明文 |
| `AWSALB` | ✅ | ✅ | None | `/` | 604800 | ALB sticky（U1 预置） |

---

## 6. CloudWatch Alarms（U6 新增 4 条）

| Alarm | Metric | 阈值 | Action |
|---|---|---|---|
| `U6-{env}-SseTtftHigh` | `novelgen/frontend::SseTtftMs` P95 | > 5_000 ms | SNS `ops-warn` |
| `U6-{env}-LighthouseRegressed` | LHCI nightly Performance | < 85 | SNS `ops-warn` |
| `U6-{env}-ClientErrorRateHigh` | `novelgen/frontend::ClientError` / 请求数 | > 2% | SNS `ops-critical` |
| `U6-{env}-BffLatencyHigh` | `novelgen/frontend::BffLatencyMs` P95 | > 500 ms | SNS `ops-warn` |

额外：
| `U6-{env}-TelemetryQpsAnomalous` | `/telemetry` 入口 QPS | > 3× baseline | warn（D4=B 额外监控） |

---

## 7. IAM 策略摘要（BFF Task Role）

- `logs:CreateLogStream / PutLogEvents` （EMF 写入 — 已由 U1 task execution role 具备）
- `secretsmanager:GetSecretValue` 读取 BFF session 签名密钥
- `cognito-idp:AdminInitiateAuth`（refresh token 流）

BFF 不直接读写 DynamoDB / S3；全部经 ApiService。

---

## 8. ALB 路由规则（在 U1 ALB 上追加）

| 优先级 | 匹配 | Target Group |
|---|---|---|
| 10 | `/api/*/stream` | `bff-user-tg`（禁用 idle timeout 缩短） |
| 20 | `/api/*`, `/auth/*`, `/telemetry` | `bff-user-tg` |
| 99 | `/*` | `s3-static-frontend-bucket`（通过 CloudFront） |

---

## 9. CloudFront Behaviors

| Path pattern | Origin | TTL | Query strings | Cookies |
|---|---|---|---|---|
| `/api/*`, `/auth/*`, `/telemetry` | ALB | 0 | 全部转发 | 全部转发 |
| `/*` (默认) | S3 | 默认 1d | 全部转发 | 无 |

SPA bundle 文件以 content hash 命名，`Cache-Control: public, max-age=31536000, immutable`。`index.html` 为 `no-cache`。

---

## 10. 资源增量总结

| 类别 | 新增 | 复用 | 备注 |
|---|---|---|---|
| ECS Fargate Service | 1（bff-user） | — | 2 task × 0.25 vCPU / 0.5 GB |
| ALB Target Group | 1 | U1 ALB | bff-user-tg |
| S3 Bucket | 1（frontend-static） | U1 CloudFront | 也可复用 U1 buckets |
| CloudFront Behavior | 3（新） | U1 distribution | |
| CloudWatch Alarms | 4 + 1 | — | 含 Telemetry Qps 监控 |
| Cookie 签名密钥 | 1 Secret | U1 Secrets Manager | 30d 轮换 |

U6 共 **~10 个新 AWS 资源** + 前端构建产物。
