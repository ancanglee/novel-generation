# U7 Admin — 代码生成计划（Code Generation Plan）

**Unit**：U7 Admin Frontend + API
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-30

---

## 1. 代码放置

```
novel-generation/
├── apps/
│   └── frontend-admin/                      ← 新增 Admin SPA
│       ├── package.json / tsconfig.json / vite.config.ts / tailwind.config.ts
│       ├── postcss.config.js / index.html
│       └── src/
│           ├── main.tsx / router.tsx
│           ├── layouts/AdminRootLayout.tsx
│           ├── pages/
│           │   ├── AdminDashboard.tsx       (首屏，同步)
│           │   ├── users/                    (chunk-users)
│           │   ├── teams/
│           │   ├── model-configs/            (含 EditModelModal)
│           │   ├── schemas/ templates/
│           │   ├── monitoring/ charts/       (ECharts, chunk-monitoring)
│           │   ├── audit/ (含 EventDetailDrawer + audit-view 二次日志)
│           │   ├── alerts/ concurrency/
│           ├── components/
│           │   ├── AdminSidebar.tsx / AdminTopBar.tsx
│           │   ├── DataTable.tsx / JsonViewer.tsx / ConfirmDialog.tsx
│           ├── stores/ (4 Zustand)
│           ├── lib/ (api / adminQueryKeys / telemetry / csrf)
│           ├── hooks/ (useAdminAuth / useUsersQuery / useModelConfigsQuery / useMonitoringQuery)
│           ├── strings/admin.ts
│           └── styles/globals.css
│
├── services/
│   └── api/src/novelgen_api/routers/admin/  ← 新增 9 sub router + helper
│       ├── __init__.py (APIRouter prefix=/admin)
│       ├── _deps.py (require_admin_role + audit_write helper + paginator)
│       ├── _cache.py (TTLCache)
│       ├── users.py / teams.py
│       ├── model_configs.py (TransactWrite + 乐观锁 409)
│       ├── schemas.py / templates.py
│       ├── audit.py (GET /audit list + /audit/{id} + AdminAuditView log)
│       ├── monitoring.py (CloudWatch batch + 分钟桶)
│       ├── alerts.py / concurrency.py
│   └── src/novelgen_api/services/
│       ├── admin_user_repo.py / admin_team_repo.py
│       ├── model_config_repo.py / schema_repo.py / template_repo.py
│       ├── audit_repo.py / alert_repo.py / concurrency_repo.py
│       └── cloudwatch_aggregator.py
│
├── infra/cdk/
│   ├── shared_constructs/u7_extensions.py   ← 新增 4 helper + apply
│   └── U7_INTEGRATION.md                    ← per-stack wiring
│
└── tests/
    ├── integration/test_u7_admin.py          ← FastAPI TestClient + moto
    └── e2e/u7-admin-smoke.spec.ts            ← Playwright + axe-core
```

---

## 2. 覆盖 Stories

- **US-08-01** 用户/团队管理
- **US-08-02** 模型配置（9 stage，DDB conditional version）
- **US-08-03** Analysis Schema + Outline 模板
- **US-08-04** 全局监控（CloudWatch 聚合）
- **US-NFR-05 admin 可观测**（5 Metric + AuditView log + 3 Alarm）
- **Out of Scope**: US-09-01/02（U5 F4=D 已排除）/ US-NFR-04 成本护栏（F6=C V2）

---

## 3. 生成步骤

### 阶段 A — Admin API（后端）
- [x] **A1**：`routers/admin/__init__.py` + `_deps.py`（require_admin_role + make_audit_put_item + Paginator + now_iso helpers）+ `_cache.py`（minute-bucket TTLCache maxsize=32 ttl=60）
- [x] **A2**：`services/*_repo.py` × 8（admin_user Cognito admin API / admin_team / model_config TransactWrite + OptimisticLockError / schema / template / audit read-only / alert / concurrency）
- [x] **A3**：`services/cloudwatch_aggregator.py` — boto3 sync client + run_in_executor + 9 query batch（chapter/critic/consistency/ingestion/analysis p95 + sse_ttft p95 + gen started/succeeded/failed sum）+ error_rate 计算
- [x] **A4**：9 sub router
  - `users.py` 6 端点（list/disable/enable/reset-password/groups add/remove）
  - `teams.py` 4 端点（list/get/disable/rename）
  - `model_configs.py` 3 端点（list/get/put）含 TransactWrite + 乐观锁 409 + stage/model 白名单
  - `schemas.py` 3 端点 / `templates.py` 3 端点 / `alerts.py` 3 端点 / `concurrency.py` 2 端点
  - `audit.py` list 过滤（date_from/to + team_id + user_id + action_contains + cursor 分页） + detail GET **emit audit_view logger**（D4=C 查看行为审计）
  - `monitoring.py` summary（cache-first + 503 降级）
- [x] **A5**：`main.py` include_router(admin.router, prefix='/api/v1')
- [x] **A6**：`tests/integration/test_u7_admin.py` — 7 个测试（require_admin_role 403 / 200 / monitoring 分钟桶缓存命中 / audit put item shape + ConditionExpression / Paginator slice / model_config OptimisticLockError）
- [x] **A7**：`services/api/pyproject.toml` 追加 `cachetools>=5.5` + `boto3>=1.35`
- [x] **A8**：`packages/storage-adapter/ddb_adapter.py` 增补 `transact_write()` 方法（计划里未列出但为 A 阶段必需）

### 阶段 B — Admin SPA（前端）
- [x] **B1**：`apps/frontend-admin/` 工程：package.json / tsconfig / vite.config（base=/admin/, manualChunks, dev proxy）/ tailwind / postcss / index.html / main.tsx（QueryClient 4xx 不重试）/ router.tsx（10 lazy routes）
- [x] **B2**：4 Zustand stores（adminSession / configDraft 防刷新 / auditFilter / monitoringRange preset→window）+ lib (api + adminQueryKeys) + hooks (useAdminAuth / useUsersQuery / useModelConfigsQuery / useMonitoringQuery) + strings/admin.ts
- [x] **B3**：AdminRootLayout（useAdminAuth + isAdmin 拦截 + 无权访问页）+ AdminSidebar（10 导航项）+ AdminTopBar + DataTable 泛型表格 + JsonViewer + ConfirmDialog
- [x] **B4**：10 业务页面（AdminDashboard 6 入口卡片 / users 含 ConfirmDialog 重置+禁用 / teams / model-configs 含 EditModelModal（9 stage 表 + 模型白名单 + temperature 滑杆 + 409 文案）/ schemas（DataTable + JsonViewer 侧栏） / templates / monitoring（preset 1h/24h/7d/30d + 4 StatCard + Throughput 堆叠柱 + Latency bar 懒加载） / audit（5 过滤 + 分页 + EventDetailDrawer 含 details 原文） / alerts / concurrency（输入+保存））
- [x] **B5**：`styles/globals.css`（Tailwind + @novelgen/ui/styles.css 导入）—— 无需 test-setup（前端测试合并到 E2E）
- [x] **B6**：`apps/*` 通配已包含 frontend-admin，根 package.json 无需修改

### 阶段 C — CDK + E2E + 文档
- [x] **C1**：`infra/cdk/shared_constructs/u7_extensions.py` 4 helper（extend_data_stack admin/ lifecycle / extend_identity_stack IAM Deny+CloudWatch+Cognito admin / extend_edge_stack /admin/* CF behavior / extend_observability_stack 3 Alarms）+ apply_u7_extensions 入口 + **明确 DEFERRED TO V2** 注释（Object Lock / MFA / Budget / PII masking）
- [x] **C2**：`infra/cdk/U7_INTEGRATION.md` per-stack wiring 4 段 + cdk diff 预期 + 前端部署命令 + Cognito admin 手动绑定说明 + 安全基线摘要 + V1 运维建议（≤5 admin / 季度密码 / CloudTrail 告警）
- [x] **C3**：`tests/e2e/u7-admin-smoke.spec.ts` 3 个测试（非 admin 无权访问 / admin dashboard + 导航 + axe WCAG AA 0 serious / model-configs 9 stage 渲染），复用 U6 的 `playwright.config.ts`
- [x] **C4**：`apps/frontend-admin/README.md`

---

## 4. 估算

| Phase | 文件 | LOC |
|---|---|---|
| A Admin API | 22 | 2800 |
| B Admin SPA | 35 | 3200 |
| C CDK + 测试 + 文档 | 4 | 700 |
| **合计** | **~61 文件** | **~6700 LOC** |

### 分 2 轮交付

- **轮 1（Admin API）**：Phase A — **~22 文件 / ~2800 LOC**
- **轮 2（Admin SPA + CDK + 测试）**：Phase B + C — **~39 文件 / ~3900 LOC**

---

## 5. 假设

- `services/api` 已有 Principal 注入（U1 `novelgen_auth.principal`）
- `novelgen_storage.DynamoDBAdapter` 支持 TransactWriteItems（若未支持需增补 adapter 方法）
- Cognito User Pool Admin API 通过 boto3 sync client 直接调（admin 操作低频，不需 async）
- CloudWatch `boto3` sync client 在 FastAPI 中用 `run_in_executor` 封装（避免阻塞 event loop）
- 前端同 U6：pnpm 9.12 + React 18.3 + Vite 5.4 + `@novelgen/ui` + `@novelgen/api-client` 复用

---

## 6. Out of Scope（明确）

- US-09-01/02 Moderation 后台（U5 F4=D 决策）
- US-NFR-04 成本护栏 / Budget 页（U7 F6=C 决策）
- Cognito Admin Group + MFA 强制（U7 I3=C 决策）
- S3 Object Lock audit-archive（U7 I2=C 决策）
- PII 脱敏（U7 D4=C 决策）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| TransactWriteItems 失败导致业务与审计不一致 | 使用 condition check 保证全或无；失败返回 500 + Alarm |
| CloudWatch GetMetricData 配额耗尽 | TTLCache 60s + Alarm 提前预警 |
| DDB 乐观锁冲突 | 409 + 前端提示 refetch + 保留 draft |
| admin 列表大量用户性能 | 分页 50/页 + DDB Query + 键前缀索引 |
| 前端 Admin SPA Bundle 超预算 | monitoring/audit 懒加载 + 路由级拆分 |

---

## 8. 用户审批

请确认：
1. 2 轮交付划分（轮 1 Admin API / 轮 2 SPA+CDK+测试）
2. 代码路径（apps/frontend-admin 新增 / services/api/routers/admin/ 子 package / shared_constructs/u7_extensions.py）
3. Out of Scope 项全部坚持（Moderation / Budget / MFA / Object Lock / PII 脱敏）
4. DynamoDBAdapter 若缺 TransactWriteItems 方法允许轮 1 内增补

**请回复 `Approve Plan` 开始轮 1 生成。**
