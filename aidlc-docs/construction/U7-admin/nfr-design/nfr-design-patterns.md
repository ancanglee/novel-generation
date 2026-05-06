# U7 Admin — NFR 设计模式（NFR Design Patterns）

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Design
**日期**：2026-04-30

---

## 1. `/admin/*` 路由挂载（D1=A）

```
services/api/src/novelgen_api/
├── main.py                       # include_router(admin.router, prefix="")
└── routers/
    ├── （已有的用户侧 router）
    └── admin/
        ├── __init__.py           # APIRouter(prefix="/admin", tags=["admin"])
        ├── _deps.py              # require_admin_role + 审计 helper + paginator
        ├── users.py              # /admin/users
        ├── teams.py              # /admin/teams
        ├── model_configs.py      # /admin/model-configs
        ├── schemas.py            # /admin/analysis-schemas
        ├── templates.py          # /admin/outline-templates
        ├── audit.py              # /admin/audit
        ├── monitoring.py         # /admin/monitoring/summary
        ├── alerts.py             # /admin/alerts
        └── concurrency.py        # /admin/concurrency
```

`admin/__init__.py`：
```python
from fastapi import APIRouter
from . import alerts, audit, concurrency, model_configs, monitoring, schemas, teams, templates, users

router = APIRouter(prefix="/admin", tags=["admin"])
for sub in (users, teams, model_configs, schemas, templates, audit, monitoring, alerts, concurrency):
    router.include_router(sub.router)
```

---

## 2. `require_admin_role` 守卫（N5=C 单层）

```python
# routers/admin/_deps.py
from fastapi import Depends, HTTPException, Request, status
from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import GlobalRole, Principal


def require_admin_role(principal: Principal = PrincipalDep) -> Principal:
    if principal.global_role != GlobalRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "需要 admin 权限",
                    "request_id": "",
                }
            },
        )
    return principal


AdminPrincipalDep = Depends(require_admin_role)
```

Sub router 示例：
```python
# routers/admin/users.py
from fastapi import APIRouter
from ._deps import AdminPrincipalDep

router = APIRouter()

@router.get("/users")
async def list_users(principal=AdminPrincipalDep, cursor: str | None = None):
    ...
```

### 2.1 补偿措施
- **MFA 强制**（Cognito Admins Group）
- **审计不可篡改**（§3）
- **JWT 信任链**：Cognito KMS 签名 + U1 `CognitoJwtVerifier` 已完成 issuer/audience/kid 校验
- V2 补强路径：在 `require_admin_role` 内加上 `await admin_repo.is_active_admin(principal.user_id)` DDB 二次校验（可增量引入，接口不变）

---

## 3. AuditEvent 不可篡改（D2=A）

### 3.1 IAM 显式 Deny
ApiService Task Role 对 `audit_events` 表的策略：
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:GetItem"],
  "Resource": "arn:aws:dynamodb:*:*:table/novelgen_audit_events"
},
{
  "Effect": "Deny",
  "Action": ["dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:BatchWriteItem"],
  "Resource": "arn:aws:dynamodb:*:*:table/novelgen_audit_events"
}
```

> 显式拒绝 `BatchWriteItem` 是因为它也可以用于删除；保留 PutItem 作为唯一的写入通道。

### 3.2 条件写入保证唯一性
```python
await ddb.put_item(
    Item={"pk": ..., "sk": f"AUDIT#{event_id}", ...},
    ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
)
```

### 3.3 S3 归档 Object Lock
U1 的 `daily-audit-archiver` Lambda 在归档时写入启用 Object Lock `governance` 模式的桶（最短保留 365 天）。

### 3.4 同事务保证
所有管理端写操作走统一 decorator：
```python
async def audit_write(*, action, resource_type, resource_id, details):
    # 业务副作用执行成功后调用此 helper；
    # 若 audit put_item 失败 → 抛异常让 FastAPI 返回 500；
    # 调用方需保证业务变更 + 审计在同一个 transact_write 中，或通过显式补偿
    # （model_configs / schemas / templates 使用 DDB TransactWriteItems）。
    ...
```

关键写操作（model_configs / schemas / templates / alerts）使用 `TransactWriteItems` 单事务写入业务记录 + AuditEvent：
```python
await ddb.transact_write_items(TransactItems=[
    {"Put": {"TableName": tenancy_table, "Item": new_model_config, ...}},
    {"Put": {"TableName": audit_events_table, "Item": audit_event, ConditionExpression: "attribute_not_exists(pk)"}},
])
```

---

## 4. 监控聚合（D3=A 分钟桶缓存）

### 4.1 缓存结构
```python
# routers/admin/monitoring.py
from cachetools import TTLCache
from datetime import datetime, timezone

_cache: TTLCache[tuple[int, int], dict] = TTLCache(maxsize=32, ttl=60)

def _bucket(dt: datetime) -> int:
    """对齐到 UTC 分钟的 epoch 值。"""
    return int(dt.replace(second=0, microsecond=0, tzinfo=timezone.utc).timestamp() // 60)


async def get_summary(from_: datetime, to: datetime) -> dict:
    key = (_bucket(from_), _bucket(to))
    cached = _cache.get(key)
    if cached is not None:
        return cached
    data = await _fetch_from_cloudwatch(from_, to)
    _cache[key] = data
    return data
```

### 4.2 CloudWatch 批量调用
```python
async def _fetch_from_cloudwatch(from_, to):
    queries = [
        {"Id": "chapter_p95", "MetricStat": {"Metric": {
            "Namespace": "novelgen/generation",
            "MetricName": "ChapterDurationMs",
        }, "Period": 300, "Stat": "p95"}},
        # ……5~10 个类似 query
    ]
    resp = cloudwatch.get_metric_data(
        MetricDataQueries=queries,
        StartTime=from_,
        EndTime=to,
    )
    return _aggregate(resp)
```

### 4.3 降级
- `get_metric_data` 抛 ThrottlingException / 5xx → 返回 `HTTPException(503, {"partial": true, "message": "监控聚合暂不可用"})`
- 前端显示上一次 `_cache` 中的历史值 + 降级警告条

### 4.4 成本控制
TTLCache 确保每个 `(from_minute, to_minute)` 组合每分钟最多 1 次 CloudWatch 调用；管理员频繁切换 preset 时也只会命中有限的桶数。

---

## 5. 模型配置变更

### 5.1 乐观锁写入
```python
# routers/admin/model_configs.py
async def put_model_config(stage: str, body: UpdateBody, principal = AdminPrincipalDep):
    current = await fetch_current(stage)
    if current and current.version != body.version:
        raise HTTPException(409, {...})  # 管理员需刷新后重试

    new_version = (current.version if current else 0) + 1
    new_item = {..., "version": new_version, "updated_by": str(principal.user_id), "updated_at": now_iso()}
    audit_item = _make_audit(principal, action="admin.model_config.update", details={
        "stage": stage, "before": current and current.dict() or None, "after": new_item,
    })

    await ddb.transact_write_items(TransactItems=[
        {"Put": {"Item": new_item,
                 "ConditionExpression": "attribute_not_exists(version) OR version = :current",
                 "ExpressionAttributeValues": {":current": current.version if current else 0}}},
        {"Put": {"Item": audit_item, "ConditionExpression": "attribute_not_exists(pk)"}},
    ])
    return {"version": new_version, "updated_at": new_item["updated_at"]}
```

### 5.2 Worker 生效
Workers 继续使用已部署的 `SsmConfigCache(ttl=60s)` 拉取新配置 —— 对应 N4=A 决策下的零新增通道。

---

## 6. PII 脱敏（D4=C 不脱敏）

### 6.1 决策与风险
**D4=C：管理员有权查看完整明文**，因此：
- `GET /admin/audit/{event_id}` 原样返回 `AuditEvent.details`，**不做字段级脱敏**
- 列表页（`GET /admin/audit?filters`）也返回原始 detail 摘要（仅把 summary 字段截断到 200 字以控制响应体积）

### 6.2 补偿安全措施
- **强制 TLS 1.2+**（CloudFront + ALB 证书）
- **严格 CSP**：阻止第三方脚本外发
- **CSRF 双提交**：防止 CSRF 引导查询
- **Admins Cognito Group 强制 MFA**（NFR-U7-3.4）
- **访问日志**：所有 `GET /admin/audit/*` 由 ApiService 写入 `AdminAuditView` 结构化日志到 CloudWatch（actor / event_id / timestamp / client_ip） —— 审计「谁看了哪条审计」
- **浏览器 DevTools 泄漏**：管理员电脑本身若被入侵无法防护，依赖管理员设备管理（MDM）承担

### 6.3 明确标注
nfr-requirements §3.7「敏感字段脱敏」变更为 **「管理员审计查看日志」** —— 不脱敏但记录查看行为。V2 可在发现 PII 泄露事件后增加字段级脱敏开关。

---

## 7. DDB 表结构

### 7.1 audit_events（U1 已有）
- pk = `TEAM#{team_id}`，跨团队管理事件则为 `GLOBAL`
- sk = `AUDIT#{timestamp_iso}#{event_id}`（时间有序，便于 Query）
- 属性：actor_user_id / actor_email / action / resource_type / resource_id / details / client_ip

### 7.2 model_configs（U1 已有）
- pk = `CONFIG`
- sk = `MODEL_CONFIG#{stage}`
- 属性：stage / primary / fallback / version / updated_by / updated_at

### 7.3 alert_rules（U1 已有）
- pk = `CONFIG`
- sk = `ALERT_RULE#{rule_id}`

---

## 8. 管理端 SPA 代码拆分

### 8.1 路由级 lazy 加载
```tsx
// apps/frontend-admin/src/router.tsx
export const router = createBrowserRouter([
  {
    path: "/admin",
    element: <AdminRootLayout />,
    children: [
      { index: true, element: <AdminDashboard /> },      // 同步
      { path: "users", lazy: () => import("./pages/users") },
      { path: "teams", lazy: () => import("./pages/teams") },
      { path: "model-configs", lazy: () => import("./pages/model-configs") },
      { path: "schemas", lazy: () => import("./pages/schemas") },
      { path: "templates", lazy: () => import("./pages/templates") },
      { path: "monitoring", lazy: () => import("./pages/monitoring") },
      { path: "audit", lazy: () => import("./pages/audit") },
      { path: "alerts", lazy: () => import("./pages/alerts") },
      { path: "concurrency", lazy: () => import("./pages/concurrency") },
    ],
  },
]);
```

### 8.2 Chunk 预算
| Chunk | gzipped 体积 |
|---|---|
| 首屏（React + Router + Query + Zustand + UI 壳 + Dashboard） | ≤ 220 KB |
| `chunk-monitoring`（ECharts 按需 bar+line） | ≤ 130 KB |
| `chunk-config`（model-configs + schemas + templates 合并） | ≤ 40 KB |
| `chunk-audit` | ≤ 30 KB |
| 其他 | < 20 KB 每个 |

### 8.3 前端 RBAC 拦截（体验层）
```tsx
function AdminRootLayout() {
  const p = useAdminSessionStore((s) => s.principal);
  if (!p) return <Navigate to="/auth/login" replace />;
  if (p.globalRole !== "admin") {
    // 体验：立即提示 + 跳回
    toast({ variant: "error", title: "无权访问" });
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
```

---

## 9. 可观测

### 9.1 管理端 Metric（命名空间 `novelgen/admin`）
- `AdminRequestCount` / `AdminRequestDurationMs`（按 route label 维度）
- `AdminModelConfigChange`（按 stage 求和）
- `AdminAuditWriteFailure`（计数）
- `AdminMonitoringCacheHit` / `AdminMonitoringCacheMiss`

### 9.2 AuditView 日志
结构化 JSON：
```json
{"actor_user_id": "...", "event_id": "...", "timestamp": "...", "client_ip": "..."}
```
写入 `/novelgen/{env}/admin/audit-view` log group，保留 90 天。

---

## 10. 错误与降级

| 场景 | 行为 |
|---|---|
| 403（非管理员） | ErrorBoundary 捕获 ApiClientError → 重定向到 `/` + toast |
| 409（乐观锁冲突） | Modal 提示 + 自动 refetch + 保留草稿让管理员合并 |
| 503（监控降级） | 顶部警告条 + 显示缓存数据 + 「重试」按钮 |
| 审计写失败（5xx） | 业务操作失败；管理员看到「操作未完成」+ 告警触发 |

---

## 11. 多租户（管理员视角）

- 管理员查看跨团队数据时 BFF 不拦截 `X-Team-Id`（管理员身份由 ApiService 识别）
- 管理端 API 在 Query `tenancy` 表时 **不注入 team filter**（单独提供 `admin_list_novels` 路径）
- 管理员切换「view as team X」模式：前端携带 `?team=X`，ApiService 按该团队过滤；此模式本身记录一条 AuditEvent（`admin.view_as_team`）
