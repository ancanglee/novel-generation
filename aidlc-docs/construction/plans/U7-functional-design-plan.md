# U7 Admin (Frontend + API) — 功能设计计划

**Unit**：U7 Admin Frontend + API
**阶段**：Functional Design
**日期**：2026-04-30

---

## 上下文摘要
U7 是 Admin 视角后台：管理用户/团队、每个任务阶段的 LLM 模型配置（Opus/Sonnet/Haiku 按 stage）、Analysis Schema / Outline 模板管理、全局监控（聚合 CloudWatch + AgentCore Observability）、审计日志查询、告警/成本护栏配置。

范围：
- **apps/frontend-admin** — 独立 React Admin SPA（与 U6 共用 `@novelgen/ui` 与 `@novelgen/api-client`）
- **services/api** 内扩展 `/admin/*` 路由（而非独立 api-admin 容器）
- `@require_admin_role` 守卫，非 admin 403
- 由 **apps/bff-user 复用**，新增域名或路径 `/admin/*` 同一 BFF 反代到 ApiService（admin API 路径同走 BFF 鉴权）

---

## 第 1 部分 — 澄清问题（6 个）

### Question U7-F1 — Admin SPA 部署路径
Admin SPA 如何对外暴露？

A) **独立域名 `admin.novelgen.example`**（清晰、可独立 CloudFront）
B) **子路径 `/admin` 挂在同 CloudFront 的同 S3 bucket**（`novels-raw/admin/` prefix，与 `frontend/` 对齐）✓
C) **合并进 frontend-user（动态加载 admin routes）**（bundle 膨胀且有越权泄漏风险）
D) 其他
[回答]：B

### Question U7-F2 — Admin API 的容器形态
`/admin/*` 路由放哪里？

A) **嵌入现有 `services/api`**（同一 FastAPI，追加 router + `@require_admin_role`）✓
B) **独立 `services/api-admin` 容器**（隔离好但运维成本↑）
C) 用 Lambda + API Gateway（与现有 SSE/REST 架构冲突）
D) 其他
[回答]：A

### Question U7-F3 — 模型配置粒度
admin 可为哪些任务阶段独立配置模型？

A) **9 阶段独立**（classification / character / map / style / outline / chapter / self_critique / critic / consistency）✓
B) **4 粗粒度阶段**（分析 / 大纲 / 生成 / 审核）
C) 固定配置，不允许 admin 改
D) 其他
[回答]：A

### Question U7-F4 — 全局监控面板数据源
Admin 监控仪表盘如何聚合？

A) **iframe 嵌入 CloudWatch Dashboard**（无代码，但样式跳脱）
B) **Admin API 聚合 CloudWatch Metrics 返回 JSON，ECharts 渲染**（统一风格）✓
C) 直接调 CloudWatch GetMetricStatistics from browser（IAM 暴露风险）
D) 其他
[回答]：B

### Question U7-F5 — 审计日志查询方式
AuditEvent（U1 已有表）查询：

A) **关键词 + 时间范围 + 用户/团队过滤，分页显示**（基础表格）✓
B) **全文搜索 OpenSearch**（复杂但强，需额外管道）
C) 仅下载 CSV（无交互）
D) 其他
[回答]：A

### Question U7-F6 — 成本护栏配置
US-NFR-04 admin 端成本护栏配置（按月 / 按 team / 按 stage）：

A) **按 team 月度预算，超过 90% 告警，超 100% 熔断**（硬上限）✓
B) **仅软告警，不熔断**（简单）
C) 不实现，保留为 V2
D) 其他
[回答]：C

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U7F-1: 生成 `domain-entities.md`（admin 管理的实体 + UI state）
- [x] Step U7F-2: 生成 `business-rules.md`（admin 业务规则：角色守卫 / 配置即时生效 / 审计追溯）
- [x] Step U7F-3: 生成 `business-logic-model.md`（登录+RBAC / 模型配置变更 / 监控聚合 3 个流程；成本护栏 V2）
- [ ] Step U7F-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **F1=B** 子路径 `/admin`（与 frontend-user 复用 CloudFront + BFF + Cognito，最低投入）
- **F2=A** 嵌入 `services/api`（共享 DDB / S3 / auth adapter，模块化 router）
- **F3=A** 9 阶段独立（已在 U1 Stories Q14=C 决策）
- **F4=B** Admin API 聚合 CloudWatch → ECharts（与 U6 统一技术栈）
- **F5=A** 表格 + 过滤 + 分页（V1 覆盖 95% 场景）
- **F6=A** 按 team 月预算 90%/100% 阈值（有硬护栏，保护成本失控）
