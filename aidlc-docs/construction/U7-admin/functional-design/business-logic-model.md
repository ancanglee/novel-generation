# U7 Admin — 业务流程模型（Business Logic Model）

**Unit**：U7 Admin Frontend + API
**阶段**：Functional Design
**日期**：2026-04-30

本文包含 3 个关键业务流程（F6=C 决策下不含预算熔断流程）。

---

## 流程 1 — 管理员登录 + RBAC

```
浏览器                  BFF                   Cognito            ApiService /admin/*
   │                    │                       │                      │
   │─ GET /admin ───────▶│                       │                      │
   │                    │ 无 sid cookie         │                      │
   │◀── 302 /auth/login │                       │                      │
   │─ GET /auth/login ──▶│─ 302 Cognito Hosted ─▶                       │
   │◀────────── Cognito Hosted UI ────────────────                      │
   │ [管理员输入凭证]                            │                      │
   │───── code 换 token ─────────────────────────▶                      │
   │                    │── POST /oauth2/token ─▶                       │
   │                    │◀── tokens（id_token 含 custom:global_role=admin）
   │◀── 302 /admin（sid httpOnly + csrf）                               │
   │                    │                       │                      │
   │─ GET /auth/me ─────▶│                       │                      │
   │                    │── 校验 sid ───────────▶                       │
   │◀── {principal.globalRole='admin', csrf}                            │
   │                    │                       │                      │
   │ [Zustand setPrincipal；isAdmin()=true]                              │
   │ RootLayout 检查通过 → 挂载 /admin 子路由                             │
   │                    │                       │                      │
   │─ GET /admin/users ─▶│─ 带 Bearer 反代 ─────▶│─── ApiService ──────▶│
   │                    │                       │  @require_admin_role │
   │◀── 200 {users}                             │  （principal.global  │
   │                    │                       │   _role==admin OK）  │
   │                                                                    │
  [非管理员路径]                                                         │
   │─ GET /admin/users ─▶│── 反代 ──────────────▶│ @require_admin_role  │
   │                    │                       │  403 Forbidden       │
   │◀── 403 FORBIDDEN                           │                      │
   │ [前端弹 toast「无权访问」+ 重定向到 /]                                │
```

---

## 流程 2 — 模型配置变更与即时生效

```
管理端浏览器               管理端 API               DDB model_configs    SNS topic           Workers（U3/U4/U5）
    │                          │                         │                    │                       │
    │ 打开 /admin/model-configs │                         │                    │                       │
    │─ GET /admin/model-configs▶                         │                    │                       │
    │                          │─ 查询全部 9 个 stage ──▶│                    │                       │
    │◀── 200 [9 个 ModelConfigDto]                       │                    │                       │
    │                          │                         │                    │                       │
    │ 双击 chapter 阶段 → 打开编辑 Modal                   │                    │                       │
    │ 选择 primary=claude-sonnet-4-7，maxTokens=6000，temp=0.7                 │                       │
    │ 点击「保存」                                                             │                       │
    │                          │                         │                    │                       │
    │─ PUT /admin/model-configs/chapter ─────────────────▶                    │                       │
    │ body={primary:{...}}     │                         │                    │                       │
    │                          │ @require_admin_role OK  │                    │                       │
    │                          │─ 开启事务               │                    │                       │
    │                          │   ConditionalUpdate     │                    │                       │
    │                          │   version=N+1 ──────────▶                    │                       │
    │                          │◀── ok                   │                    │                       │
    │                          │   写入 AuditEvent       │                    │                       │
    │                          │   action=admin.model    │                    │                       │
    │                          │   _config.update        │                    │                       │
    │                          │◀── ok                   │                    │                       │
    │                          │─ commit                 │                    │                       │
    │                          │                         │                    │                       │
    │                          │─ 发布 SNS ─────────────────────────────────▶│                       │
    │                          │   model-config-changed  │                    │─ 扇出 ──────────────▶│
    │                          │   {stage:'chapter',     │                    │                       │ 失效缓存
    │                          │    version:N+1}         │                    │                       │ 拉取新 DDB 行
    │                          │                         │                    │                       │ 下次任务使用新模型
    │                          │                         │                    │                       │
    │◀── 200 {version:N+1, updated_at}                   │                    │                       │
    │                          │                         │                    │                       │
    │ [toast「已保存」+ useConfigDraftStore.clearModelDraft('chapter')]         │                       │
    │ 表格行刷新显示新配置                                                    │                       │
```

**幂等性**：UI 重复点击保存由 DDB 条件更新 `version = currentVersion` 防御 —— 冲突时返回 409，管理员先刷新再改。

---

## 流程 3 — 全局监控聚合与渲染

```
管理端浏览器                     管理端 API                          CloudWatch
    │                              │                                    │
    │ 选择 preset='24h'             │                                    │
    │（Zustand useMonitoringRangeStore set）                              │
    │                              │                                    │
    │─ GET /admin/monitoring/summary?from=T-24h&to=T ─▶                  │
    │                              │ @require_admin_role                │
    │                              │─ GetMetricData 批量 ──────────────▶│
    │                              │   [                               │
    │                              │     ChapterDurationMs p95,        │
    │                              │     CriticDurationMs p95,         │
    │                              │     ConsistencyDurationMs p95,    │
    │                              │     SseTtftMs p95,                │
    │                              │     按 stage 的 TokenUsage × 9,   │
    │                              │     GenerationStarted count,      │
    │                              │     GenerationSucceeded count,    │
    │                              │     GenerationFailed count        │
    │                              │   ]                               │
    │                              │◀── 时间序列数组 ──────────────────│
    │                              │                                   │
    │                              │ 聚合 → MonitoringSummaryDto JSON  │
    │◀── 200 {totals, latency, tokens, sse_ttft_p95_ms, error_rate}    │
    │                                                                   │
    │ [ECharts 渲染 4 个卡片：吞吐 / 延迟 / Token / 错误率]                 │
    │                                                                   │
    │ 点击「刷新」→ 再发一次请求                                          │
    │（不自动轮询以控制 CloudWatch 成本）                                 │
```

**缓存**：管理端 API 对相同 range 的 summary 响应使用 60 秒内存 TTLCache，避免短时间内重复打 CloudWatch。

---

## 流程 4 —（已移除）成本护栏熔断

> **状态**：F6=C — 本 Unit 不实现；V2 将在此处补充流程图，涉及团队级 budget 计数器 + 99% 告警 + 100% 熔断拒绝 `POST /generations` 新任务。

---

## 附录：管理端 UI 路由

```
/admin                     （管理端概览 — 系统健康概览）
/admin/users               （用户管理）
/admin/teams               （团队管理）
/admin/model-configs       （9 个阶段的模型配置）
/admin/schemas             （Analysis Schema 管理）
/admin/templates           （Outline 模板管理）
/admin/monitoring          （全局监控面板）
/admin/audit               （审计日志查询）
/admin/alerts              （告警规则）
/admin/concurrency         （并发配置）
```

非管理员访问上述任一路径 → 303 See Other → `/` + 弹 toast「无权访问」
