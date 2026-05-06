# U7 Admin — 业务规则（Business Rules）

**Unit**：U7 Admin Frontend + API
**阶段**：Functional Design
**日期**：2026-04-30

---

## R1. 鉴权与 RBAC

### R1.1 管理员守卫
- `@require_admin_role` FastAPI 依赖检查 `principal.global_role == "admin"`，非管理员返回 **403**
- 前端 RootLayout 检查 `isAdmin()`；非管理员访问 `/admin/*` → 重定向至 `/` 并弹出 toast「无权访问」
- BFF 层不做额外的管理员鉴权（继续沿用 Cognito JWT 反代），守护点在 ApiService 端

### R1.2 登录流程
- 复用 U6 的 `/auth/login`（相同的 Cognito Hosted UI）
- 管理员身份通过 Cognito User Pool Group `Admins` 映射到 `custom:global_role = "admin"` claim
- 首次访问 `/admin` 时若 `principal == null` → BFF 302 到 Cognito；若已登录但非管理员 → 前端路由拦截并显示 403

---

## R2. 用户与团队管理（US-08-01）

### R2.1 用户列表
- 每页 50 条分页；过滤条件：邮箱子串 / team_id / status / global_role
- 管理员可：**禁用**（status=disabled，保留数据） / **重置密码邀请**（Cognito AdminResetUserPassword） / **提升为管理员**（二次确认 Modal） / **降级为普通用户**

### R2.2 团队列表
- 每行显示 member_count / novels_count / generations_count
- 管理员可：**禁用团队**（同时禁用所有成员） / **转让 owner**（从成员列表中选择） / **改名**

### R2.3 审计追溯
所有 R2 操作写入 `AuditEvent`：action 前缀为 `admin.user.*` / `admin.team.*`，actor 为当前管理员，resource_type 与 resource_id 必填，details 载荷包含 before/after diff。

---

## R3. 模型配置（US-08-02，F3=A 9 个阶段）

### R3.1 读取与显示
- `GET /admin/model-configs` 返回全部 9 个阶段的当前配置
- UI 展示为 9 行表格，列：阶段 / primary 模型 + maxTokens + temperature / fallback / updated_by / updated_at
- 双击某行进入编辑弹窗

### R3.2 编辑与生效
- 编辑弹窗表单：primary 模型下拉（4 个选项） + maxTokens（1-8192） + temperature（0-1） + fallback 可选
- 保存 → `PUT /admin/model-configs/{stage}` → 写 DDB `model_configs` 表 + 写 `AuditEvent` + **发布 SNS `model-config-changed`**
- Worker 侧（U3/U4/U5）订阅 SNS 即时刷新 SSM 缓存（沿用现有 SsmConfigCache 60 秒自然刷新也可接受）
- UI `useConfigDraftStore` 保留未保存草稿，防止刷新丢失

### R3.3 回滚
- 管理员可查看某阶段的历史版本（DDB 条件写入 + version N），选择某个版本「恢复为当前」（触发一次新的 PUT）

---

## R4. Analysis Schema 与 Outline 模板（US-08-03）

### R4.1 CRUD
- schemas / templates 均支持 list / create / update / delete
- 删除时检查引用：若存在 `Novel.schema_id == target` → 拒绝删除并提示迁移
- update 写入新版本条目，旧版本只读保留（便于溯源）

### R4.2 前端编辑器
- 表格化字段编辑器（添加字段 / 修改类型 / 配置枚举值）
- JSON 直出查看（高级 tab）

---

## R5. 全局监控（US-08-04，F4=B）

### R5.1 时间范围
- 预设范围：1h / 24h / 7d / 30d / custom
- `GET /admin/monitoring/summary?from=...&to=...` 返回 `MonitoringSummaryDto`
- 管理端 API 内部调用 CloudWatch `GetMetricData` 批量拉取 5 个关键 metric

### R5.2 图表
- 4 个 ECharts 卡片：
  1. **吞吐趋势**（每日 generations_started / succeeded / failed 的堆叠柱状图）
  2. **P95 延迟**（6 条线图：ingestion / analysis / chapter / critic / consistency / sse_ttft）
  3. **按阶段的 Token 用量**（9 个阶段的堆叠柱状图）
  4. **错误率**（折线图 + 5% 阈值参考线）

### R5.3 刷新策略
- 默认不自动刷新；用户点击「刷新」按钮重新拉取（避免成本浪费）
- 1h 预设范围下提供「自动刷新 30s」开关

---

## R6. 审计日志（F5=A）

### R6.1 查询
- 输入：dateFrom / dateTo / teamId / userId / actionContains（子串匹配）
- `GET /admin/audit?...&cursor=` 每页 50 条分页
- 按 timestamp 倒序排列
- 单击行展开 `details` 的 JSON 查看器

### R6.2 范围与保留
- 仅可查询最近 **365 天**；更早的数据在 S3 归档（由 U1 的 daily-audit-archiver Lambda 归档），V1 不支持读取归档

---

## R7. 告警规则（US-NFR-05 管理端）

### R7.1 管理
- `GET/POST/PUT/DELETE /admin/alerts` 完整 CRUD
- 表格显示：metric / threshold / window / severity / enabled 开关 / updated_by
- enabled 开关支持行内直接切换并保存

### R7.2 校验
- threshold 必须为数字；window_minutes 取值 1-60
- 删除「核心」规则（由环境变量标记 `core_rule=true`）时拒绝并提示

---

## R8. 并发配置（AD6=F 管理端）

### R8.1 可调项
- deep_read_default（默认 20，取值 1-64）
- deep_read_max（默认 32，取值 1-128）
- chapter_parallel_max（默认 1，取值 1-4）

### R8.2 生效
- 写入 DDB → Worker SSM 缓存每 60 秒自动拉新（复用现有机制，不新增通道）

---

## R9. 成本护栏（US-NFR-04）—— **推迟到 V2，本 Unit 不实现**（F6=C）

- UI 不呈现 Budget 页
- 管理端 API 不提供 `/admin/budgets` 路由
- U1 已有的 token CloudWatch Alarm 继续生效，不受 U7 影响
- 审计：未来启用时，将在 `apps/frontend-admin/src/pages/budgets/*` 与 `services/api/src/novelgen_api/routers/admin/budgets.py` 下新增

---

## R10. 错误呈现

- 403 / 401：前端弹 toast 并拦截到 ErrorFallback
- 表单错误：行内下方红字 + 兼容 axe A11y（`aria-describedby`）
- 远程 5xx：弹 toast「服务暂时不可用，请稍后重试」+ 可选「重试」按钮

---

## R11. 审计规范（横切）

所有管理端写操作（PUT/POST/DELETE）经 FastAPI 依赖 `AuditAuditor.write()` 在同事务内写入 audit_events 表；异常中断时不保留 AuditEvent —— 保证「要么都做，要么都不做」。
