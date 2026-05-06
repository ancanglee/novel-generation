# U7 Admin (Frontend + API) — 非功能需求计划

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Requirements
**日期**：2026-04-30

---

## 上下文摘要
Admin 前端访问频率低（仅 admin 用户）、交互路径以配置与查询为主、对流式无要求。NFR 聚焦：审计查询延迟、CloudWatch 聚合成本、Bundle 预算、RBAC 安全、操作可审计性。继承 U1 平台 + U6 CloudFront/BFF/Cognito。

---

## 第 1 部分 — 澄清问题（5 个）

### Question U7-N1 — Admin SPA Bundle 预算
Admin 首屏（gzipped）：

A) **≤ 220 KB**（含 ECharts 监控 lazy；与 U6 一致）✓
B) **≤ 300 KB**（宽松）
C) **≤ 150 KB**（极激进）
D) 其他
[回答]：A

### Question U7-N2 — 列表查询延迟
`GET /admin/users`、`/admin/audit` 等主查询 P95：

A) **< 500 ms**（DDB Query + 50 行，常规）✓
B) **< 1000 ms**（宽松）
C) **< 250 ms**（激进）
D) 其他
[回答]：A

### Question U7-N3 — CloudWatch 聚合 API 延迟
`GET /admin/monitoring/summary` P95：

A) **< 3 秒**（CloudWatch GetMetricData 批量 + 60s TTLCache 保护）✓
B) **< 5 秒**（宽松）
C) **< 1 秒**（不现实）
D) 其他
[回答]：A

### Question U7-N4 — 模型配置生效延迟
admin 点保存 → Worker 下一次任务使用新模型：

A) **≤ 60 秒**（依赖现有 SsmConfigCache 60s refresh，简单）✓
B) **≤ 5 秒**（需 SNS 主动 invalidation，复杂度↑）
C) **≤ 5 分钟**（太慢）
D) 其他
[回答]：A

### Question U7-N5 — RBAC 纵深防御层数
Admin 权限校验：

A) **2 层：BFF 透传 JWT + ApiService `@require_admin_role` 依赖**（常规）
B) **3 层：Cognito Group 绑定 + ApiService 依赖 + DDB 二次读 admin 表校验**（最严）✓
C) **1 层：仅 ApiService 依赖**（最弱）
D) 其他
[回答]：C

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U7N-1: 生成 `nfr-requirements.md`
- [x] Step U7N-2: 生成 `tech-stack-decisions.md`
- [x] Step U7N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **N1=A** ≤ 220 KB（与 U6 对齐）
- **N2=A** P95 < 500 ms（DDB 查询常规）
- **N3=A** P95 < 3 秒（CloudWatch batch 典型响应 0.5-1.5s，留余量）
- **N4=A** ≤ 60 秒（复用现有机制，零复杂度）
- **N5=B** 3 层纵深（admin 权限泄漏后果严重，成本低回报高）
