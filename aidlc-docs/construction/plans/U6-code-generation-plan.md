# U6 Frontend + BFF — 代码生成计划（Code Generation Plan）

**Unit**：U6 Frontend + BFF
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-30

---

## 1. 代码放置

```
novel-generation/
├── apps/
│   ├── frontend-user/                    ← 新增 SPA
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── postcss.config.js
│   │   ├── biome.json              (root workspace 已有，可复用)
│   │   ├── index.html
│   │   ├── public/
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── router.tsx
│   │       ├── layouts/
│   │       │   ├── RootLayout.tsx
│   │       │   └── ChapterLayout.tsx
│   │       ├── pages/
│   │       │   ├── Dashboard.tsx
│   │       │   ├── novels/
│   │       │   ├── analysis/        (React Flow + ECharts 懒加载)
│   │       │   ├── outline/
│   │       │   ├── chapter/
│   │       │   ├── reader/
│   │       │   └── settings/
│   │       ├── components/
│   │       │   ├── TopBar.tsx
│   │       │   ├── TeamPicker.tsx
│   │       │   ├── JobPoller.tsx
│   │       │   ├── ErrorBoundary.tsx
│   │       │   └── Toast.tsx
│   │       ├── stores/
│   │       │   ├── sessionStore.ts
│   │       │   ├── chapterStreamStore.ts
│   │       │   ├── conflictPanelStore.ts
│   │       │   └── modalStore.ts
│   │       ├── lib/
│   │       │   ├── api.ts
│   │       │   ├── sse.ts
│   │       │   ├── telemetry.ts
│   │       │   ├── queryKeys.ts
│   │       │   └── csrf.ts
│   │       ├── hooks/
│   │       ├── strings/
│   │       └── styles/
│   │           └── globals.css
│   │
│   ├── bff-user/                         ← 新增 BFF
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── server.ts
│   │       ├── config.ts
│   │       ├── session/
│   │       │   ├── store.ts
│   │       │   ├── middleware.ts
│   │       │   └── cookies.ts
│   │       ├── routes/
│   │       │   ├── auth.ts
│   │       │   ├── telemetry.ts
│   │       │   ├── proxy.ts
│   │       │   └── health.ts
│   │       ├── proxy/
│   │       │   ├── standard.ts
│   │       │   └── sse.ts
│   │       ├── security/
│   │       │   ├── helmet.ts
│   │       │   ├── csrf.ts
│   │       │   └── rateLimit.ts
│   │       └── telemetry/
│   │           └── emf.ts
│   │
│   └── (frontend-admin 留给 U7)
│
├── packages/
│   ├── api-client-ts/                    ← 新增（骨架 + OpenAPI 生成脚本）
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── client.ts           (fetch wrapper + auth + CSRF)
│   │   │   └── generated/          (占位；由 openapi-typescript 生成)
│   │   │       └── .gitkeep
│   │   └── scripts/
│   │       └── generate.ts
│   │
│   ├── ui/                               ← 新增业务组件库
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── primitives/         (shadcn/ui wrappers)
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Dialog.tsx
│   │   │   │   └── Toast.tsx
│   │   │   ├── ConflictPanel.tsx
│   │   │   ├── StyleRadar.tsx
│   │   │   ├── CharacterGraph.tsx  (React Flow wrapper)
│   │   │   ├── ChapterReader.tsx   (markdown)
│   │   │   └── StreamingText.tsx   (逐 delta + cursor)
│   │   └── styles.css
│   │
│   └── shared-types-ts/                  ← 已存在，追加 critique/conflict 类型
│       └── src/
│           └── critique.ts         (mirror novelgen_types/critique.py)
│
├── infra/cdk/
│   └── shared_constructs/
│       └── u6_extensions.py              ← 新增（5 helper）
│
└── tests/
    └── e2e/
        ├── playwright.config.ts
        └── u6-smoke.spec.ts              ← 新增（登录 → 列表 → 章节流式 → Rewrite）
```

---

## 2. 覆盖 Stories

- **US-00-01** 首页 / **US-00-02** 注册登录（Cognito Hosted UI 回调）
- **US-01-01** 仪表盘 / **US-01-02 / 03** 团队协作（本 Unit 前端侧）
- **US-02-01~04** 采集页（上传 / 搜索 / URL / 列表）
- **US-03-02~05** 分析报告查看（类型 / 人物图 / 地图 / 风格雷达）
- **US-04-01~03** 生成配置
- **US-05-01 / 02** 大纲
- **US-06-01** 章节流式（含 F3=A 逐 delta + R7.2 Last-Event-ID）
- **US-06-04** 重写（含 U5 ConflictItem 触发链路）
- **US-07-01 / 02** 导出与阅读
- **NFR**：US-NFR-03 多租户（Team 切换清缓存）/ US-NFR-05 可观测（D4=B 立即遥测）

---

## 3. 生成步骤

### 阶段 A — Shared packages + 基础设施
- [x] **A1**：`packages/shared-types-ts/src/critique.ts` 镜像后端 Critique/Conflict 类型 + 6 ConflictType 枚举 + index.ts re-export
- [x] **A2**：`packages/api-client-ts/` 骨架：package.json + tsconfig + client.ts（fetch + 401 回调 / CSRF 自动附 / X-Team-Id / upstream header 暴露） + errors.ts（ApiClientError / ApiAuthError / ApiConflictFrozenError） + `scripts/generate.ts` 占位 + `src/generated/.gitkeep`
- [x] **A3**：`packages/ui/` 骨架：package.json + tsconfig + styles.css（Tailwind tokens light/dark）+ 5 primitives（Button / Dialog / Toast / Spinner / Badge）+ 5 业务组件（ConflictPanel 6 ConflictType 中文标签 + frozen 灰化 / StyleRadar ECharts radar 6 维 / CharacterGraph React Flow 懒加载 internal impl / ChapterReader 3 主题 markdown / StreamingText 光标闪烁 + aria-live）

### 阶段 B — BFF 服务（apps/bff-user）
- [x] **B1**：`package.json` + `tsconfig.json` + `tsconfig.build.json` + `Dockerfile`（node:20-bookworm-slim 多阶段 pnpm 9.12）+ vitest.config.ts
- [x] **B2**：`src/config.ts` zod env 校验（Cognito + session key + app base url 自动拼 redirect/logout）
- [x] **B3**：`session/{cookies,store,middleware}.ts` HS256 签名 + LRU cache + 5 分钟窗口刷新 Cognito token
- [x] **B4**：`routes/auth.ts` /auth/login（PKCE + state cookie）/ /auth/callback / /auth/me / /auth/logout + refreshTokensFactory
- [x] **B5**：`proxy/{standard,sse}.ts` undici 代理 + HOP_BY_HOP 过滤 + X-Upstream-Error header + SSE 专用（Cache-Control no-transform + X-Accel-Buffering no + client close 清理 upstream）
- [x] **B6**：`routes/{proxy,telemetry,health}.ts` — proxy 按路径匹配 SSE / telemetry zod 校验 / healthz 含 session count
- [x] **B7**：`security/{helmet,csrf,rateLimit}.ts`（CSP 严格 + 双提交 CSRF + 100 req/s/session onRoute 注入）+ `telemetry/emf.ts`（logger.info 结构化输出）
- [x] **B8**：`src/server.ts` 组装（Issuer.discover + oidcClient + hooks 加载 + 4 路由模块）+ SIGTERM graceful shutdown
- [x] **B9**：tests — `cookies.test.ts`（签名/篡改/不同 key）/ `session-store.test.ts`（LRU/TTL/evict）/ `csrf.test.ts`（GET 通过/POST exempt/mismatch 403/triple match 200）/ `emf.test.ts`（EMF shape + attrs dims）

### 阶段 C — SPA 基础（apps/frontend-user）
- [x] **C1**：`package.json` + `tsconfig.json` + `vite.config.ts` (manualChunks + dev proxy) + `tailwind.config.ts` + `postcss.config.js` + `index.html`
- [x] **C2**：`src/main.tsx`（QueryClient + StrictMode）+ `router.tsx`（React Router 6 data router + 7 lazy routes + ErrorFallback 绑定）
- [x] **C3**：4 个 Zustand stores（sessionStore / chapterStreamStore 完整 phase 状态机 + reconnectCount / conflictPanelStore busyIds Set / modalStore kind 联合）
- [x] **C4**：`lib/{api,sse,telemetry,queryKeys,csrf}.ts`（api 创建全局 ApiClient / sse openChapterStream 封装 EventSource 5 事件 / telemetry 立即 emit + visibility gate + emitOnce dedupe / queryKeys qk.* 工厂）
- [x] **C5**：全局组件：`layouts/RootLayout`（useAuth + ready + 登录 fallback）/ `TopBar`（主导航 + admin 分支 + TeamPicker + logout form）/ `TeamPicker`（清缓存演示）/ `ErrorBoundary`（catch + emit UnhandledJsError）/ `ErrorFallback`（react-router 错误）/ `JobPoller`（refetchInterval 按 status 暂停）/ `Toast` + `ToastRegion`（Zustand 队列 + 自动 dismiss）
- [x] **C6**：`strings/{index,common,chapter,conflict}.ts` 中文词表
- [x] **C7**：`hooks/useAuth.ts`（TanStack /auth/me → setPrincipal + markReady）+ `hooks/useNovels.ts`（novels 列表 + 详情样板）
- [x] **C8**：`styles/globals.css`（@tailwind 三指令 + 导入 @novelgen/ui/styles.css + cursor-blink keyframes）+ `test-setup.ts`

### 阶段 D — SPA 业务页面
- [x] **D1**：`pages/Dashboard.tsx`（轮 2 中已完成首屏同步 + 3 Stat 卡 + 最近任务列表 + Badge 状态映射）
- [x] **D2**：`pages/novels/{index.tsx, IngestForm.tsx, NovelDetailPage.tsx}`（列表 + IngestForm 3 模式 tab（upload multipart / 公版书搜索 / URL 抓取）+ 详情页 Badge）
- [x] **D3**：`pages/analysis/{index.tsx, GeoMap.tsx}`（4 tab：overview / characters（React Flow via @novelgen/ui） / map（ECharts scatter 自定义坐标 lazy） / style（ECharts radar 6 维））
- [x] **D4**：`pages/outline/index.tsx`（章节 items inline title+summary 编辑 + AI advice 面板 + 批准按钮链式 approve-outline → start → navigate to chapter 1）
- [x] **D5**：`pages/chapter/{index.tsx, useChapterStream.ts, ConflictPanelContainer.tsx}`（双栏 Editor + ConflictPanel / useChapterStream hook 完整状态机：connect + rAF 合批 delta + 5 次指数退避重连 + 8s cancel 超时 + SseTtftMs 遥测 / ConflictPanelContainer ApiConflictFrozenError 专门 catch 显示中文 frozen toast + busyIds 防并发）
- [x] **D6**：`pages/reader/index.tsx`（markdown 渲染 + 3 主题 light/dark/sepia + font-size 滑杆 + 阅读位置 localStorage）
- [x] **D7**：`pages/settings/index.tsx`（个人资料 + 角色 Badge + 团队成员列表 + owner 邀请按钮条件显示）

### 阶段 E — CDK u6_extensions
- [x] **E1**：`infra/cdk/shared_constructs/u6_extensions.py` 5 helper（extend_data_stack frontend/ lifecycle / extend_identity_stack BFF Task Role + secret + cognito refresh / extend_compute_stack Fargate 2×0.25vCPU ARM64 + CircuitBreaker + auto-scale CPU 70% + TG stickiness 6h + 2 listener rules priority 90/100 / extend_edge_stack 3 CloudFront behaviors SSE/API/默认 + S3 origin path=/frontend / extend_observability_stack 5 Alarms SseTtftHigh/LighthouseRegressed/ClientErrorHigh/BffLatencyHigh/TelemetryQpsAnomalous）+ apply_u6_extensions 合成入口
- [x] **E2**：`infra/cdk/U6_INTEGRATION.md` — per-stack wiring snippets（data/identity/compute/edge/observability）+ ALB idle_timeout 60→900s 全局 attribute 调整说明 + 前端部署 sync + cloudfront invalidation 命令 + cdk diff 预期清单

### 阶段 F — 测试与文档
- [x] **F1**：`tests/e2e/{playwright.config.ts, u6-smoke.spec.ts}` Playwright + axe-core：3 个 test（登录未认证 fallback / Dashboard 渲染 + WCAG 2.1 AA 0 serious 断言 / ConflictPanel frozen chip + 重写按钮禁用），chromium + webkit matrix
- [x] **F2**：`apps/frontend-user/README.md` + `apps/bff-user/README.md`
- [x] **F3**：`packages/ui/README.md`

---

## 4. 估算

| Phase | 文件 | LOC |
|---|---|---|
| A Shared packages | 15 | 1200 |
| B BFF | 18 | 1800 |
| C SPA 基础 | 20 | 1500 |
| D SPA 页面 | 30 | 3500 |
| E CDK | 2 | 500 |
| F 测试+文档 | 5 | 400 |
| **合计** | **~90 文件** | **~8900 LOC** |

### 分 3 轮交付

- **轮 1（shared + BFF）**：Phase A + B，**~33 文件 / ~3000 LOC**
- **轮 2（SPA 基础 + Dashboard）**：Phase C，**~20 文件 / ~1500 LOC**
- **轮 3（SPA 业务页 + CDK + 测试）**：Phase D + E + F，**~37 文件 / ~4400 LOC**

---

## 5. 假设

- 现网 `packages/shared-types-ts` 已存在最小骨架（已确认）
- Cognito Hosted UI 的 callback URL / client_id / 签名算法由 U1 CDK 输出
- ApiService OpenAPI 规范可在本地通过 `/openapi.json` 获取（api-client 生成时用）
- pnpm 9.12+ 已在开发机具备；`.nvmrc` = v20.17
- React Flow 与 ECharts 通过 `import()` 懒加载，测试环境 Playwright 允许访问
- 集成 Cognito 流程采用 `openid-client`；Hosted UI 的 well-known endpoint 在 config.ts 中推导
- Playwright E2E 仅测 smoke，无需覆盖全 Story AC（留给 Build and Test 阶段补齐）

---

## 6. Out of Scope

- **Admin 后台（U7）**
- Sentry / PWA / Service Worker（NFR 排除）
- 完整英语翻译（N5=A 中文 only）
- 性能压测（Lighthouse 只跑 CI 基础通过）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Cognito Hosted UI 回调参数变动导致登录失败 | config.ts 从 env 读取；本地 E2E 用 mock idp 绕过 |
| React Flow + ECharts 同时加载使 analysis 页超预算 | 路由级 lazy + ECharts 按需 import（`echarts/core` + `radar` + `geo`） |
| SSE 代理在 BFF 断流（undici 默认行为）| 显式 `bodyTimeout: 0, headersTimeout: 10s` + 手动 pipe readable stream |
| D4=B 立即 POST 造成带宽风暴 | `useEmitOnce` hook + visibility 门 + BFF 限流 100 req/s/session |
| React 18 StrictMode 双渲染触发 SSE 多连接 | `useEffect` 使用 `AbortController` + effect cleanup 关闭前连接 |

---

## 8. 用户审批

请确认：
1. 3 轮交付划分（轮 1 shared+BFF / 轮 2 SPA 基础 / 轮 3 SPA 业务页+CDK+测试）
2. 代码路径（apps/frontend-user + apps/bff-user + 新 packages/api-client-ts + 新 packages/ui）
3. React Flow + ECharts 双图形库混合（F5=A + F6=A 决策坚持）
4. 中文 only（N5=A），文案走 `strings/` 集中
5. 轮 1 开始前不需要先拉 OpenAPI 真实规范（用占位骨架即可，生成代码留待 Build and Test 阶段）

**请回复 `Approve Plan` 开始轮 1 生成。**
