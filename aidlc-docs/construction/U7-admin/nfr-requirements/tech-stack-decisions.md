# U7 Admin — 技术栈决策（Tech Stack Decisions）

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Requirements
**日期**：2026-04-30

---

## 1. 管理端 SPA（`apps/frontend-admin`）

完全复用 U6 的技术栈：React 18.3 / Vite 5.4 / TanStack Query 5.59 / Zustand 4.5 / React Router 6.26 / Tailwind + shadcn/ui（通过 `@novelgen/ui`）/ ECharts 5.5 / axios / react-hook-form + zod / lucide-react / Playwright + axe-core。

### 相对 U6 的差异
- **不含 React Flow**（管理端不需要人物关系图） —— Bundle 中不包含

---

## 2. 管理端 API（嵌入 `services/api`）

延续 U1/U4 的 FastAPI 栈：`fastapi 0.115` / `pydantic 2.8` / `aioboto3` / 现有 `novelgen-auth-adapter`（沿用 Cognito JWT 解析）/ 现有 `novelgen-storage-adapter`。

### 新增 router 模块
`services/api/src/novelgen_api/routers/admin/` 目录下：
- `users.py` / `teams.py` / `model_configs.py` / `schemas.py` / `templates.py` / `audit.py` / `monitoring.py` / `alerts.py` / `concurrency.py`

### 新增依赖
- **`cachetools 5.5`**（用于 monitoring 聚合的 TTLCache）
- 无其他新增包

---

## 3. RBAC（N5=C）

单层守卫：`@require_admin_role` FastAPI 依赖。

```python
def require_admin_role(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.global_role != GlobalRole.ADMIN:
        raise HTTPException(status_code=403, detail={...})
    return principal
```

挂在 `/admin/*` 所有路由上。

**补偿**：Cognito User Pool 的 Admins Group 强制 MFA + AuditEvent 不可篡改（IAM 层面 Deny `audit_events` 的 UpdateItem / DeleteItem）。

---

## 4. 前端部署

- `apps/frontend-admin/dist/` → `s3://novels-raw-{env}/admin/`（沿用 U6 的 I2=A 模式）
- CloudFront 默认 `/*` behavior 已指向 S3 origin；U7 追加 origin request policy 支持 `/admin/*` 回源（或沿用默认）
- `index.html` 设置 Cache-Control no-cache；带 hash 的资源设置 `public, max-age=31536000, immutable`

---

## 5. 监控聚合

- `cachetools.TTLCache(maxsize=32, ttl=60)`，按 `(from, to)` 缓存 MonitoringSummaryDto
- CloudWatch 使用 `boto3` 同步 client（而非 aioboto3）—— 聚合属于批处理操作，同步方式也能满足 P95 < 3s

---

## 6. 部署

- 前端通过 pnpm build → S3 sync + CloudFront 失效
- 后端（`/admin/*` 路由）随 `services/api` 镜像滚动部署
- **无需新增 ECS Service / Lambda / CDK Stack**

---

## 7. 排除选项

| 不选 | 原因 |
|---|---|
| 独立 `services/api-admin` 容器 | F2=A 决策 |
| SNS 主动推送模型配置变更 | N4=A 复用 SSM 60 秒回落 |
| Cognito Group + DDB 二次校验 | N5=C 决策（风险已记录，V2 补强） |
| React Flow | 管理端不使用人物关系图 |
| Redux / MUI / Next.js | 与 U6 的排除一致 |

---

## 8. 版本锁

与 U6 一致：Node 20.17 / pnpm 9.12 / Python 3.12。
