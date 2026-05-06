# U7 部署架构（Deployment Architecture）

**Unit**：U7 Admin Frontend + API
**阶段**：Infrastructure Design
**日期**：2026-04-30

本文件包含 2 张架构图（I4=B 决策）：
1. **U7 增量部署图** — U7 相对 U1-U6 的资源增量（★ 标注）
2. **RBAC + 审计流图** — 请求如何经 Cognito → BFF → ApiService `@require_admin_role` → DDB（Deny Update/Delete）→ AuditEvent 写入

---

## 1. U7 增量部署图

```
                    ┌────────────────────────────────────────────────┐
                    │ AWS Account（Region ap-northeast-1）           │
                    │                                                │
                    │  ┌────────────────────────────────────────┐    │
                    │  │ CloudFront Distribution（U1+U6）       │    │
                    │  │  ★ +1 behavior（U7）：                 │    │
                    │  │     /admin/* → S3 origin path=/admin   │    │
                    │  │                                        │    │
                    │  │  已有 behavior（不变）：                │    │
                    │  │    /api/*/stream（U6）                 │    │
                    │  │    /api/*、/auth/*、/telemetry（U6）    │    │
                    │  │    /*  → S3 origin path=/frontend（U6）│    │
                    │  └──────┬───────────────┬────────────────┘    │
                    │         │               │                      │
                    │         ▼               ▼                      │
                    │   ┌─────────┐    ┌──────────┐                 │
                    │   │ S3      │    │ ALB（U1）│                 │
                    │   │ novels- │    │          │                 │
                    │   │ raw     │    │  bff-tg  │                 │
                    │   │         │    └────┬─────┘                 │
                    │   │ 前缀：  │         │                        │
                    │   │  /      │         ▼                        │
                    │   │    frontend/（U6）bff-user（U6）           │
                    │   │  ★ /admin/（U7）                            │
                    │   │                                             │
                    │   │ Lifecycle：                                 │
                    │   │  ★ admin/ 90 天                             │
                    │   │   （I2=C：不启用 Object Lock）              │
                    │   └─────────┘                                  │
                    │                                                 │
                    │   ┌────────────────────────────────┐           │
                    │   │ ECS Cluster                    │           │
                    │   │  api-service（U1+U4+U5+U6）    │           │
                    │   │   ★ 新镜像含 admin/ router      │           │
                    │   │     子 package                  │           │
                    │   └────────────────────────────────┘           │
                    │                                                 │
                    │   ┌────────────────────────────────┐           │
                    │   │ DynamoDB                       │           │
                    │   │  novelgen_tenancy（U1）        │           │
                    │   │   ★ 新增 SK 模式：              │           │
                    │   │     MODEL_CONFIG#{stage}       │           │
                    │   │     ANALYSIS_SCHEMA#{id}       │           │
                    │   │     OUTLINE_TEMPLATE#{id}      │           │
                    │   │     ALERT_RULE#{id}            │           │
                    │   │     CONCURRENCY                │           │
                    │   │                                │           │
                    │   │  novelgen_audit_events（U1）   │           │
                    │   │   ★ IAM：对 api-service Task   │           │
                    │   │     Role Deny Update/Delete    │           │
                    │   └────────────────────────────────┘           │
                    │                                                 │
                    │   ┌────────────────────────────────┐           │
                    │   │ Cognito User Pool（U1）        │           │
                    │   │   ★ IAM：允许 ApiService 调用   │           │
                    │   │     AdminDisableUser / 重置    │           │
                    │   │     密码 / Group 管理          │           │
                    │   │                                │           │
                    │   │   I3=C：Admin Group + MFA     │           │
                    │   │   强制 → 推迟到 V2             │           │
                    │   └────────────────────────────────┘           │
                    │                                                 │
                    │   ┌────────────────────────────────┐           │
                    │   │ CloudWatch                     │           │
                    │   │   ★ +3 Alarms（U7）：           │           │
                    │   │     AdminAuditWriteFailureHigh │           │
                    │   │     AdminRequestP95High        │           │
                    │   │     MonitoringAggregationSlow  │           │
                    │   │                                │           │
                    │   │   ★ LogGroup /novelgen/{env}/  │           │
                    │   │     admin/audit-view（90d）    │           │
                    │   └────────────────────────────────┘           │
                    │                                                 │
                    │   ┌────────────────────────────────┐           │
                    │   │ 审计归档（U1 Lambda）           │           │
                    │   │   I2=C：Object Lock 推迟到      │           │
                    │   │   V2。归档按原样写入现有        │           │
                    │   │   桶。                          │           │
                    │   └────────────────────────────────┘           │
                    │                                                 │
                    └────────────────────────────────────────────────┘

图例：★ = U7 新增或修改；其余继承自 U1/U6。
```

---

## 2. RBAC + 审计流图

```
管理员浏览器（https://app.novelgen.example/admin）
    │
    │ 1）CloudFront /admin/* → S3 /admin/index.html
    │    （SPA 启动 + /auth/me 检查）
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 通过 BFF 调用 /auth/me                                        │
│                                                               │
│ BFF 读取 sid cookie → 返回 principal                          │
│ （若 Cognito claim 为 admin，则 principal.globalRole=="admin"）│
└───────┬───────────────────────────────────────────────────────┘
        │
        │ 2）SPA 路由到 /admin/users（懒加载 chunk 完成）
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ SPA 发起 GET /api/admin/users                                 │
│（credentials include + X-CSRF-Token header）                 │
└───────┬───────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ CloudFront /api/* behavior → ALB → bff-user-tg               │
│                                                               │
│ BFF 校验 sid + CSRF，设置 Authorization: Bearer idToken       │
│ → 反代到 ApiService                                          │
└───────┬───────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ ApiService FastAPI                                            │
│  routers/admin/users.py @AdminPrincipalDep                   │
│                                                               │
│   ┌───────────────────────────────────────────────┐          │
│   │ require_admin_role(principal)                 │          │
│   │   if principal.global_role != "admin":        │          │
│   │     raise HTTPException(403)                  │          │
│   └───────────────────────────────────────────────┘          │
│                                                               │
│  Layer 1（JWT claim）： 由 U1 CognitoJwtVerifier 校验          │
│  Layer 2（守卫）：       上面的 require_admin_role            │
│  Layer 3（DB）：         IAM 在 novelgen_audit_events 上       │
│                         Deny UpdateItem/DeleteItem            │
│                                                               │
│  （I3=C）MFA 推迟到 V2 — 管理员账户仅依赖密码。                 │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ 3）管理员动作：PUT /admin/model-configs/chapter
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ ApiService 执行 TransactWriteItems：                          │
│   Put model_configs 行（ConditionExpression version = :old）  │
│   Put audit_events 行（ConditionExpression attr_not_exists）  │
│   → 原子：业务 + 审计同时写入，要么都成，要么都不成             │
│                                                               │
│ 如果尝试对 audit_events 执行 UpdateItem？                     │
│  IAM Deny → AccessDenied 异常 → ApiService 返回 500           │
│  AdminAuditWriteFailure metric +1 → Alarm 触发                │
└───────┬───────────────────────────────────────────────────────┘
        │
        │ 4）管理员查看 /admin/audit/{event_id}
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ ApiService routers/admin/audit.py                             │
│  GetItem audit_events[...] → 按 D4=C 返回未脱敏的 PII          │
│  副作用：发出结构化日志                                       │
│    {actor_user_id, event_id, client_ip, ts}                  │
│    → CloudWatch /novelgen/{env}/admin/audit-view（90 天）    │
│ （审计审计者 — "谁看了哪条审计"）                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 部署风险与缓解

| 风险 | 缓解 |
|---|---|
| IAM Deny Update/Delete 误伤已有 Worker | 通过 audit_events 表 ARN 精确限定；Worker 原本就只做 PutItem |
| CloudFront `/admin/*` behavior 优先级冲突 | 新 behavior 的 priority 需高于默认 `/*`；CDK `add_behavior` 自动处理 |
| 管理员账号未启用 MFA 被钓鱼（I3=C） | CloudTrail 告警 `cognito-idp:AdminAddUserToGroup` + 管理员密码强度策略 + 账号数量 ≤ 5 |
| 审计归档 S3 对象被删（I2=C） | S3 bucket 层面 versioning + bucket policy Deny Delete（运维可选增补，不在 U7 Code 范围内） |

---

## 4. 部署顺序（回顾）

1. ECR push 新的 api-service 镜像
2. `cdk diff` → `cdk deploy`（dev → stage → prod）
3. `aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-{env}/admin/ --delete`
4. `aws cloudfront create-invalidation --paths "/admin/index.html"`
5. 在 Cognito 控制台手动把目标用户加入管理员角色（设置 `custom:global_role=admin`）

---

## 5. 架构图文本导出说明

两张图使用 ASCII 盒形；资源名与 `infrastructure-design.md` + `logical-components.md` 保持一致。导出 PDF 时建议使用 Menlo、JetBrains Mono 等等宽字体。
