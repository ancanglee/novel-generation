# U7 Admin — 非功能需求（NFR Requirements）

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Requirements
**日期**：2026-04-30

---

## 范围

管理后台（`apps/frontend-admin` + `services/api` 的 `/admin/*` 路由）属于低频、仅管理员访问的管理面。聚焦 **性能 / 可靠性 / 安全（尤其是 RBAC） / 可观测 / 可审计 / 可访问性**。

---

## 1. 性能

### NFR-U7-1.1 Lighthouse 性能分
- Lighthouse v11 Mobile 的 Performance ≥ 85（与 U6 同标准）

### NFR-U7-1.2 Bundle 预算
- **首屏 ≤ 220 KB gzipped**（N1=A）
  - React + TanStack Query + Zustand + Router ≈ 95 KB
  - `@novelgen/ui` primitives ≈ 30 KB
  - 管理端壳（Layout + 鉴权守卫 + 导航）≈ 40 KB
  - 首屏 Dashboard（健康概览）≈ 30 KB
  - 余量 25 KB
- 懒加载：
  - `chunk-monitoring` ≤ 130 KB（ECharts 按需 bar / line）
  - `chunk-config` ≤ 40 KB（模型配置表单）
  - `chunk-audit` ≤ 30 KB

### NFR-U7-1.3 列表查询 P95
- `GET /admin/users` / `/admin/teams` / `/admin/audit` 的 P95 **< 500 ms**（N2=A）
- 每页 50 行分页；DDB Query 配合适当的 GSI；必要时缓存

### NFR-U7-1.4 CloudWatch 聚合 P95
- `GET /admin/monitoring/summary` 的 P95 **< 3 秒**（N3=A）
- 实现：管理端 API 通过 `GetMetricData` 批量拉取 ≤ 500 个数据点，然后 **60 秒 TTLCache**（同 range 短时间内复用）

### NFR-U7-1.5 模型配置生效
- 管理员保存 → Worker 下一次任务使用新模型 **≤ 60 秒**（N4=A）
- 实现：写入 DDB `model_configs` + Worker `SsmConfigCache` 每 60 秒刷新的自然回落；**不引入 SNS 主动 invalidation**（与 U3/U5 现有模式一致）

### NFR-U7-1.6 路由切换
- 路由切换到首帧 P95 < 500 ms

---

## 2. 可靠性

### NFR-U7-2.1 DDB 冲突处理
- 模型配置 / Schema / Template 的 PUT 使用 DDB 条件更新（`version = :current`）；冲突 → 返回 409，前端提示管理员「已被他人修改，请刷新」

### NFR-U7-2.2 审计落盘
- 所有管理端写操作在同一 FastAPI 请求内同步写入 `audit_events` 表；写入失败 → 业务操作回滚（返回 5xx）—— **「无审计则无操作」**

### NFR-U7-2.3 监控聚合降级
- 若 CloudWatch `GetMetricData` 失败（Throttle / 5xx） → 管理端 API 返回 `503 + {"partial": true, "cached_until": ...}`，UI 显示上一次缓存 + 降级警告条

### NFR-U7-2.4 SPA 错误边界
- 复用 U6 的 `ErrorBoundary`（`@novelgen/ui`），管理端页面异常不影响用户端 SPA

---

## 3. 安全 — RBAC

### NFR-U7-3.1 权限校验（**N5=C 单层**）
**本 Unit 只在 ApiService 侧做单层 RBAC 守卫**（`@require_admin_role` FastAPI 依赖）。

具体实施：
- Cognito JWT 中 `custom:global_role` claim 为 `admin` 方可通过
- 任何 `/admin/*` 路由都依赖该守卫；非管理员返回 **403**
- BFF 层透传 JWT，不做额外判断
- 不额外做 DDB 二次读校验

**风险认知与记录**：
- 管理员权限泄漏后果严重（可重置任一用户密码、修改模型配置、查看所有审计记录）
- 单层校验意味着 JWT claim 被篡改或错误颁发时没有二次防线
- **V2 建议补强**：升级为 3 层（Cognito Group `Admins` + FastAPI 依赖 + DDB `user_id in admin_allowlist` 二次校验），以降低影响面

**补偿措施（本 Unit 内）**：
- JWT 签名由 Cognito 托管（AWS KMS），篡改不可行
- 所有管理端操作必写 `AuditEvent`（NFR-U7-2.2），事后可追溯
- Cognito User Pool 的管理员用户**必须强制 MFA**（NFR-U7-3.4）

### NFR-U7-3.2 前端 RBAC 拦截
- 管理端 SPA 的 RootLayout 检查 `principal.globalRole == "admin"`；否则 303 → `/` + toast
- 前端拦截属于**体验优化**，**不是安全边界**（安全由后端的单层守卫承担）

### NFR-U7-3.3 审计不可篡改
- `audit_events` 表使用 DDB 条件写入 `attribute_not_exists(event_id)`
- 禁止 `DeleteItem` / `UpdateItem`（IAM 层面 Deny），仅允许 `PutItem`
- 按日归档到 S3（U1 daily-audit-archiver Lambda），归档对象启用 Object Lock governance mode

### NFR-U7-3.4 管理员用户 MFA
- Cognito User Pool Group `Admins` 配置 MFA required（TOTP / SMS 备份）
- 管理员账户初始化时强制绑定 MFA 才可登录

### NFR-U7-3.5 CSRF
- 继承 U6 BFF 的双提交 CSRF 机制（Header + Cookie + 服务端 session 三方比对）

### NFR-U7-3.6 CSP
- 与 U6 一致，针对管理端 SPA 无额外放宽（不允许 eval，不允许外源 iframe）

### NFR-U7-3.7 敏感字段脱敏
- 管理员查看 `AuditEvent.details` 时，如包含 `user.email` / `phone` 等 PII：列表页仅显示前缀 + 掩码；详情页通过展开按钮查看（记录二次审计）

---

## 4. 可观测

### NFR-U7-4.1 管理端专属 Metric（命名空间 `novelgen/admin`）
| Metric | 用途 |
|---|---|
| `AdminRequestCount` | 按 route + status 维度 |
| `AdminRequestDurationMs` | 查询延迟 |
| `AdminModelConfigChange` | 模型配置变更次数 |
| `AdminAuditWriteFailure` | 审计写入失败（零容忍） |
| `AdminMonitoringCacheHit` | TTLCache 命中率 |

### NFR-U7-4.2 Alarms（3 条）
| Alarm | 阈值 |
|---|---|
| `U7-{env}-AdminAuditWriteFailureHigh` | `AdminAuditWriteFailure > 0`（立即告警） |
| `U7-{env}-AdminRequestP95High` | `AdminRequestDurationMs` P95 > 2000 ms |
| `U7-{env}-MonitoringAggregationSlow` | `/admin/monitoring/summary` 的 duration P95 > 5 s |

### NFR-U7-4.3 管理员操作日志
所有写操作记录到 `/novelgen/{env}/admin` CloudWatch Log Group，字段：actor / action / resource / before/after diff / client_ip。保留 90 天。

---

## 5. 可访问性

### NFR-U7-5.1 WCAG 2.1 AA
- 复用 U6 的 A11y 基线（axe-core + Playwright）
- 表格 + 键盘导航（Tab 切换列，Enter 展开）
- 表单控件必须绑定 `<label>`

---

## 6. 成本

### NFR-U7-6.1 CloudWatch 聚合成本
- `GetMetricData` 按请求计费（$0.01 / 1000 metrics requested）
- 限制：相同 range 60 秒内仅 1 次真实拉取（TTLCache），单管理员会话持续停留监控页面每分钟最多 1 次 = 60 次请求/小时
- 预计管理员日常使用：5 个管理员 × 100 个 metric × 20 次请求/天 = 10k metrics/天 ≈ $0.10/天

### NFR-U7-6.2 无其他显著成本
管理端 API 复用现有 FastAPI 容器 + DDB（按量），无额外基础设施成本

---

## 7. 兼容性

### NFR-U7-7.1 浏览器
- 与 U6 同：Chrome/Edge 115+ / Safari 16+ / Firefox 115+

### NFR-U7-7.2 设备
- 桌面优先（1440×900+）；管理端不把移动端作为首选场景

---

## 8. 国际化

- V1 仅中文（与 U6 一致）
- 词表集中存放在 `apps/frontend-admin/src/strings/`

---

## 9. 部署与 CI/CD

### NFR-U7-9.1 前端
- `vite build` → `aws s3 sync dist/ s3://novels-raw-{env}/admin/`
- CloudFront 失效 `/admin/index.html`

### NFR-U7-9.2 后端
- 复用 `services/api` 镜像，U7 变更即随 API service 滚动更新
- Rolling deploy P95 < 4 分钟

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| **N5=C 单层 RBAC 漏洞** | MFA 强制 + 审计不可篡改 + 未来 V2 补充 DDB 二次校验；JWT 签名由 AWS KMS 保障 |
| CloudWatch 配额耗尽 | TTLCache 60 秒 + 告警 `MonitoringAggregationSlow`；必要时切换到 S3 Embedded Metrics 回看 |
| 管理员并发编辑冲突 | DDB 条件 version + UI 冲突提示 |
| 审计 DDB 写失败 | 业务操作同事务回滚；失败告警立即触发 |
| 非管理员绕过前端检查直接访问 `/admin/*` | FastAPI 依赖守卫 + 403；CloudFront → ALB → BFF → ApiService 整条路径无捷径 |

---

## 11. 覆盖 Stories

- **US-08-01** 用户 / 团队管理（性能对应 NFR-U7-1.3）
- **US-08-02** 模型配置（生效延迟对应 NFR-U7-1.5）
- **US-08-03** Schema / Template 管理
- **US-08-04** 全局监控（聚合延迟对应 NFR-U7-1.4）
- **US-NFR-03** 多租户（管理员跨团队视角 + 审计追溯）
- **US-NFR-04 成本护栏**：**V2 实现**（F6=C 决策保留）
- **US-NFR-05** 全链路可观测（管理端专属 metric / log / alarm）
