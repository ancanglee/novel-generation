# frontend-admin (U7)

React 18 + Vite + TanStack Query + Zustand admin SPA for NovelGen.

## Develop
```bash
pnpm --filter @novelgen/frontend-admin dev
# http://localhost:5174/admin
```
Vite proxies `/api`, `/auth`, `/telemetry` to `http://localhost:3000` (bff-user).

## Build & deploy
```bash
pnpm --filter @novelgen/frontend-admin build
aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-${ENV}/admin/ --delete
aws cloudfront create-invalidation --paths "/admin/index.html"
```

## Pages
- `/admin` Dashboard
- `/admin/users` User management (disable / reset password)
- `/admin/teams` Team list
- `/admin/model-configs` 9-stage model configuration with optimistic lock
- `/admin/schemas` Analysis schemas
- `/admin/templates` Outline templates
- `/admin/monitoring` ECharts throughput + latency (CloudWatch aggregated)
- `/admin/audit` Audit events with filters + detail drawer
- `/admin/alerts` Alert rules
- `/admin/concurrency` Concurrency config (AD6=F)

## Security (N5=C single-layer RBAC)
- RoleGate: `AdminRootLayout` checks `principal.globalRole === "admin"` and renders forbidden screen otherwise (frontend UX only; authoritative check lives in `services/api/routers/admin/_deps.py::require_admin_role`).
- No PII masking (D4=C — admin sees plaintext; viewer log emitted server-side).
- Deferred: MFA enforcement (I3=C), Object Lock for audit archive (I2=C), Budget page (F6=C).
