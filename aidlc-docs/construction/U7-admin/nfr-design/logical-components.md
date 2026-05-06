# U7 Admin — 逻辑组件（Logical Components）

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Design
**日期**：2026-04-30

---

## 1. 管理端 SPA 组件结构（`apps/frontend-admin`）

```
apps/frontend-admin/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── index.html
└── src/
    ├── main.tsx
    ├── router.tsx                # /admin/* 共 10 个 lazy route
    ├── layouts/
    │   └── AdminRootLayout.tsx   # 鉴权拦截 + sidebar + topbar
    ├── pages/
    │   ├── AdminDashboard.tsx    # 首屏（同步）— 系统健康概览
    │   ├── users/
    │   │   ├── index.tsx
    │   │   └── UserDetailDrawer.tsx
    │   ├── teams/
    │   ├── model-configs/
    │   │   ├── index.tsx         # 9 个阶段的表格
    │   │   └── EditModelModal.tsx
    │   ├── schemas/
    │   ├── templates/
    │   ├── monitoring/
    │   │   ├── index.tsx
    │   │   └── charts/           # ECharts 子组件
    │   ├── audit/
    │   │   ├── index.tsx
    │   │   └── EventDetailDrawer.tsx
    │   ├── alerts/
    │   └── concurrency/
    ├── components/
    │   ├── AdminSidebar.tsx
    │   ├── AdminTopBar.tsx
    │   ├── DataTable.tsx         # 通用表格（排序 / 分页 / 过滤）
    │   ├── JsonViewer.tsx        # 展示 AuditEvent.details
    │   └── ConfirmDialog.tsx
    ├── stores/
    │   ├── adminSessionStore.ts
    │   ├── configDraftStore.ts
    │   ├── auditFilterStore.ts
    │   └── monitoringRangeStore.ts
    ├── lib/
    │   ├── api.ts                # 复用 @novelgen/api-client
    │   ├── adminQueryKeys.ts
    │   └── telemetry.ts          # 复用用户端 SPA 的 emit
    ├── hooks/
    │   ├── useAdminAuth.ts
    │   ├── useUsersQuery.ts
    │   ├── useModelConfigsQuery.ts
    │   └── useMonitoringQuery.ts
    ├── strings/
    │   └── admin.ts
    └── styles/
        └── globals.css
```

---

## 2. 管理端 API 组件（`services/api`）

```
services/api/src/novelgen_api/
└── routers/
    └── admin/
        ├── __init__.py
        ├── _deps.py              # require_admin_role + 审计 helper + paginator
        ├── _cache.py             # 用于 monitoring 的 TTLCache
        ├── users.py
        ├── teams.py
        ├── model_configs.py
        ├── schemas.py
        ├── templates.py
        ├── audit.py
        ├── monitoring.py         # CloudWatch 聚合
        ├── alerts.py
        └── concurrency.py
```

新增 service 层（位于 `novelgen_api/services/` 下）：
- `admin_user_repo.py` / `admin_team_repo.py` / `model_config_repo.py` / `schema_repo.py` / `template_repo.py` / `audit_repo.py` / `alert_repo.py` / `concurrency_repo.py`
- `cloudwatch_aggregator.py`（封装 `GetMetricData` 批量调用）

---

## 3. DDB 访问模式

| 用途 | pk | sk | 访问方式 |
|---|---|---|---|
| 用户列表 | `GLOBAL` 或 `TEAM#{id}` | `USER#{user_id}` | Query，begins_with `USER#` |
| 团队列表 | `GLOBAL` | `TEAM#{team_id}` | Query，begins_with `TEAM#` |
| 模型配置（9 阶段） | `CONFIG` | `MODEL_CONFIG#{stage}` | GetItem / Query |
| 分析 Schema | `CONFIG` | `ANALYSIS_SCHEMA#{schema_id}` | Query |
| Outline 模板 | `CONFIG` | `OUTLINE_TEMPLATE#{template_id}` | Query |
| 告警规则 | `CONFIG` | `ALERT_RULE#{rule_id}` | Query |
| 并发配置 | `CONFIG` | `CONCURRENCY` | GetItem |
| 审计事件 | `TEAM#{id}` 或 `GLOBAL` | `AUDIT#{timestamp_iso}#{event_id}` | Query，按 timestamp 倒序 |

所有表沿用 U1 预建的 `novelgen_tenancy` + `novelgen_audit_events`（U1 已分开）。U7 只新增 SK 模式，不新建表。

---

## 4. IAM 策略

### 4.1 ApiService Task Role 增量
```python
# audit_events 表已有 PutItem + Query；显式 Deny Update/Delete/BatchWrite
stack.api_service_role.add_to_policy(
    iam.PolicyStatement(
        effect=iam.Effect.DENY,
        actions=[
            "dynamodb:UpdateItem",
            "dynamodb:DeleteItem",
            "dynamodb:BatchWriteItem",
        ],
        resources=[audit_events_table.table_arn],
    )
)
# cloudwatch:GetMetricData 用于监控聚合
stack.api_service_role.add_to_policy(
    iam.PolicyStatement(
        actions=["cloudwatch:GetMetricData", "cloudwatch:ListMetrics"],
        resources=["*"],
    )
)
# Cognito 管理员 API（重置密码等）
stack.api_service_role.add_to_policy(
    iam.PolicyStatement(
        actions=[
            "cognito-idp:AdminDisableUser",
            "cognito-idp:AdminEnableUser",
            "cognito-idp:AdminResetUserPassword",
            "cognito-idp:AdminAddUserToGroup",
            "cognito-idp:AdminRemoveUserFromGroup",
            "cognito-idp:ListUsers",
        ],
        resources=[user_pool.user_pool_arn],
    )
)
```

---

## 5. CloudWatch Alarms（3 条，对应 NFR-U7-4.2）

| Alarm | Metric | 阈值 | 动作 |
|---|---|---|---|
| `U7-{env}-AdminAuditWriteFailureHigh` | `novelgen/admin::AdminAuditWriteFailure` Sum 1min | > 0 | SNS ops-critical |
| `U7-{env}-AdminRequestP95High` | `novelgen/admin::AdminRequestDurationMs` P95 5min | > 2000 ms | SNS ops-warn |
| `U7-{env}-MonitoringAggregationSlow` | 同上，增加维度 `Route=/admin/monitoring/summary` 的 P95 | > 5000 ms | SNS ops-warn |

---

## 6. Cookie / 会话
继承 U6 完全一致（sid + csrf），无新增。

---

## 7. S3 前端静态资源

| 路径 | Bucket | 说明 |
|---|---|---|
| `s3://novels-raw-{env}/frontend/*` | U1 + U6 | 用户端 SPA |
| `s3://novels-raw-{env}/admin/*` | U1 + U7 ★ | 管理端 SPA |

CloudFront 默认 `/*` behavior（origin path=/frontend）由 U6 预建；U7 针对 `/admin/*` path pattern 追加独立 behavior：origin path=/admin，其余参数与默认相同。

---

## 8. 资源增量（U7）

| 类型 | 增量 | 备注 |
|---|---|---|
| ECS Service | 0 | 复用 api-service |
| CloudFront behavior | +1（`/admin/*` path，origin path=/admin） | |
| ALB 规则 | 0 | 复用 U6 的 `/api/*` 规则（管理端路径也经 BFF 反代） |
| DDB SK 模式 | +3 个新模式（USER#GLOBAL / ANALYSIS_SCHEMA# / OUTLINE_TEMPLATE# / ALERT_RULE# / CONCURRENCY / 审计复用 U1 表） | 无新表 |
| IAM 策略 | +3 条 statements（DDB Deny / CloudWatch GetMetricData / Cognito admin） | |
| Alarms | +3 | |
| S3 prefix | +1（`/admin/`）+ lifecycle | |
| ECR | 0（无新容器） | |

U7 共计 **约 8 项新增 AWS 资源或 policy 变更**。
