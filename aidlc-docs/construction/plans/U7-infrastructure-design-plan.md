# U7 Admin — 基础设施设计计划

**Unit**：U7 Admin Frontend + API
**阶段**：Infrastructure Design
**日期**：2026-04-30

---

## 上下文摘要
U7 基础设施增量极小：
- 0 新 ECS Service（复用 api-service）
- 0 新 DDB 表（仅 SK 模式扩展）
- +1 CloudFront behavior（`/admin/*` → S3 origin path=/admin）
- +3 IAM statements（Deny on audit_events / CloudWatch GetMetricData / Cognito admin API）
- +3 CloudWatch Alarms
- +1 S3 prefix `/admin/` + Lifecycle
- +1 S3 bucket 启用 Object Lock（仅对 audit 归档 prefix）

---

## 第 1 部分 — 澄清问题（4 个）

### Question U7-I1 — CDK 组织
A) **`shared_constructs/u7_extensions.py`**（对齐 U2-U6 风格）✓
B) 改 U1 stacks
C) 独立 Stack
D) 其他
[回答]：A

### Question U7-I2 — Audit S3 Object Lock bucket
AuditEvent 归档的 S3 bucket 启用 Object Lock：

A) **新建专用 `novelgen-audit-archive-{env}` bucket with Object Lock governance 365d**（合规最佳实践）✓
B) **复用 U1 novels-raw bucket 新 prefix `audit-archive/` + Object Lock**（DynamoDB 归档和业务数据混同）
C) 不启用 Object Lock（合规风险）
D) 其他
[回答]：C

### Question U7-I3 — Cognito Admin Group MFA
admin 账户 MFA 强制方式：

A) **User Pool 创建 `Admins` Group + 组级 MFA required（MFA_SETUP challenge 强制）**✓
B) **所有用户 MFA optional**（弱，不满足 NFR-U7-3.4）
C) 不实现，V2
D) 其他
[回答]：C

### Question U7-I4 — 架构图数量
A) **1 张：U7 增量部署图**（资源少，1 张足够）✓
B) **2 张：增量部署 + RBAC/审计流**
C) 0 张（文字描述）
D) 其他
[回答]：B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U7I-1: 生成 `infrastructure-design.md`
- [x] Step U7I-2: 生成 `deployment-architecture.md`（2 张图，按 I4=B）
- [x] Step U7I-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **I1=A** `u7_extensions.py`（对齐 U2-U6）
- **I2=A** 专用 audit-archive bucket（职责清晰，合规友好）
- **I3=A** Admin Group + MFA required（NFR-U7-3.4 硬要求）
- **I4=A** 1 张图（U7 资源增量极少）
