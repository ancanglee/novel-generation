# U7 Admin — 非功能设计计划

**Unit**：U7 Admin Frontend + API
**阶段**：NFR Design
**日期**：2026-04-30

---

## 上下文摘要
U7 NFR Design 聚焦：
- `@require_admin_role` 守卫实现与放置
- CloudWatch 聚合 TTLCache 缓存结构
- AuditEvent 不可篡改（IAM 拒绝 Update/Delete + S3 Object Lock）
- 模型配置 DDB conditional version 冲突处理
- Admin SPA 代码拆分与路由守卫
- 敏感字段脱敏管道

澄清面窄（4 问）。

---

## 第 1 部分 — 澄清问题（4 个）

### Question U7-D1 — Admin 路由挂载方式
`/admin/*` FastAPI router 的组织：

A) **单个 `admin/` package + 每个资源一个子 router（users/teams/model_configs/...）**，在 `main.py` 统一 include_router with `prefix='/admin'`✓
B) **平铺所有路由到 `services/api/routers/admin.py` 单文件**（代码膨胀）
C) 独立 sub-FastAPI app with `mount('/admin', app)`
D) 其他
[回答]：A

### Question U7-D2 — AuditEvent IAM 策略落地方式
禁止 Update/Delete 审计事件：

A) **ApiService Task Role 仅含 PutItem + Query；通过 IAM 显式拒绝 `UpdateItem` / `DeleteItem`**✓
B) **审计表专用 Task Role（与主表 Role 分离）**（强隔离但运维重）
C) DDB 表级 condition policy（DynamoDB 不支持该粒度）
D) 其他
[回答]：A

### Question U7-D3 — 监控聚合缓存键
`GET /admin/monitoring/summary?from=T1&to=T2` 的 TTLCache key：

A) **`(bucketed_from, bucketed_to)` 对齐到分钟**（同一 range 合并请求，命中率高）✓
B) **完整 `(from, to)` 作为 key**（精确但命中率低）
C) 不缓存，每次打 CloudWatch
D) 其他
[回答]：A

### Question U7-D4 — 敏感字段脱敏管道
admin 查看 `AuditEvent.details` 中含 PII 的字段：

A) **Admin API 响应时服务端脱敏（`email → u***@example.com`），展开详情按钮记二次审计**✓
B) **前端脱敏**（明文已在网络传输，弱）
C) 不脱敏（admin 有权看全）
D) 其他
[回答]：C

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U7D-1: 生成 `nfr-design-patterns.md`
- [x] Step U7D-2: 生成 `logical-components.md`
- [x] Step U7D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **D1=A** admin 子 package + 9 sub router（代码分治 + include_router 统一前缀）
- **D2=A** IAM 显式拒绝 Update/Delete（最小运维成本）
- **D3=A** 分钟桶对齐（命中率高 + 对 admin 监控精度足够）
- **D4=A** 服务端脱敏（避免明文落到浏览器内存 / devtools）
