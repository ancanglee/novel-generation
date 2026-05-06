# U7 基础设施设计（Infrastructure Design）

**Unit**：U7 Admin Frontend + API
**阶段**：Infrastructure Design
**日期**：2026-04-30

---

## 1. 总体原则

U7 基础设施增量极小。核心资源：
- `shared_constructs/u7_extensions.py`（I1=A）
- `/admin/*` S3 前缀（复用 `novels-raw-{env}` bucket）
- `/admin/*` CloudFront behavior（S3 origin path=/admin）
- IAM 策略扩展：对 `audit_events` 的 UpdateItem/DeleteItem 显式 Deny、CloudWatch GetMetricData、Cognito 管理员 API
- 3 条 CloudWatch Alarm

> **安全基线调整**（I2=C、I3=C）
> - **不启用 Audit S3 Object Lock**（I2=C）
> - **Cognito Admins Group 不强制 MFA**（I3=C，推迟到 V2）
>
> 这两项原本是 N5=C 单层 RBAC 的补偿措施，本 Unit **不实施**。当前管理员权限防线只依赖：
> 1. Cognito JWT `custom:global_role=admin` claim（Cognito KMS 签名保证不可伪造）
> 2. ApiService 的 `@require_admin_role` FastAPI 依赖（403 gate）
> 3. DDB `audit_events` 表的 IAM Deny UpdateItem/DeleteItem/BatchWriteItem（运行时不可篡改仍然保留）
>
> 推迟到 V2 的补强项：MFA 强制 + Object Lock + 3 层 RBAC 纵深防御。运维层面建议：管理员账户数量控制在 ≤5 个 + 定期轮换密码 + 通过 CloudTrail 监控管理员 IAM 权限变更。

---

## 2. CDK 组织

```
infra/cdk/shared_constructs/u7_extensions.py        （新增）
```

### 2.1 对外 helper

```python
def apply_u7_extensions(
    stack, cfg, *,
    novels_bucket: s3.Bucket,
    audit_events_table: dynamodb.ITable,
    api_service_role: iam.Role,
    cognito_user_pool: cognito.IUserPool,
    distribution: cloudfront.Distribution,
    alerts_topic: sns.Topic,
) -> None:
    extend_data_stack(stack, cfg, novels_bucket=novels_bucket)
    extend_identity_stack(stack, cfg,
        api_service_role=api_service_role,
        audit_events_table=audit_events_table,
        cognito_user_pool=cognito_user_pool,
    )
    extend_edge_stack(stack, cfg,
        distribution=distribution,
        novels_bucket=novels_bucket,
    )
    extend_observability_stack(stack, cfg, alerts_topic=alerts_topic)
```

---

## 3. S3 `/admin/` 前缀（I2=C 不启用 Object Lock）

```python
def extend_data_stack(stack, cfg, *, novels_bucket: s3.Bucket) -> None:
    # /admin/* 前缀的 lifecycle（与 U6 的 /frontend/ 相同）
    novels_bucket.add_lifecycle_rule(
        id="U7AdminRollback",
        prefix="admin/",
        noncurrent_version_expiration=cdk.Duration.days(90),
        noncurrent_versions_to_retain=3,
    )
    # 说明：带 Object Lock 的 audit 归档 bucket 推迟到 V2（I2=C）。
    # 当前 U1 的 daily-audit-archiver Lambda 继续写入已有归档桶，不启用 Object Lock。
```

---

## 4. IAM 策略扩展（最关键部分）

```python
def extend_identity_stack(
    stack, cfg, *,
    api_service_role: iam.Role,
    audit_events_table: dynamodb.ITable,
    cognito_user_pool: cognito.IUserPool,
) -> None:
    # 1. 对 audit_events 的 Update/Delete 显式 Deny（运行时不可篡改 — NFR-U7-3.3）
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.DENY,
            actions=[
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:BatchWriteItem",
            ],
            resources=[audit_events_table.table_arn],
        )
    )
    # 2. CloudWatch GetMetricData 用于监控聚合
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "cloudwatch:GetMetricData",
                "cloudwatch:ListMetrics",
            ],
            resources=["*"],
        )
    )
    # 3. Cognito 管理员 API（用户管理）
    api_service_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "cognito-idp:AdminDisableUser",
                "cognito-idp:AdminEnableUser",
                "cognito-idp:AdminResetUserPassword",
                "cognito-idp:AdminAddUserToGroup",
                "cognito-idp:AdminRemoveUserFromGroup",
                "cognito-idp:ListUsers",
                "cognito-idp:ListGroups",
            ],
            resources=[cognito_user_pool.user_pool_arn],
        )
    )
    # 说明：强制 MFA 的 Cognito Admin Group 推迟到 V2（I3=C）。
    # 现有 User Pool 配置保持不变；管理员账户与普通用户共享相同的 MFA 策略（可选）。
```

---

## 5. CloudFront `/admin/*` behavior

```python
def extend_edge_stack(
    stack, cfg, *,
    distribution: cloudfront.Distribution,
    novels_bucket: s3.IBucket,
) -> None:
    admin_origin = cf_origins.S3Origin(novels_bucket, origin_path="/admin")
    distribution.add_behavior(
        "/admin/*",
        admin_origin,
        allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
        viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    )
```

### 5.1 ALB 规则不变
`/api/*`、`/auth/*` 已由 U6 指向 BFF；管理端前端调 `/api/admin/*` 时仍经 BFF 反代到 ApiService —— 不需要新增 ALB 规则。

---

## 6. CloudWatch Alarms（3 条）

```python
def extend_observability_stack(stack, cfg, *, alerts_topic: sns.Topic) -> None:
    audit_failure = cw.Metric(
        namespace="novelgen/admin",
        metric_name="AdminAuditWriteFailure",
        statistic="Sum",
        period=cdk.Duration.minutes(1),
        dimensions_map={"Env": cfg.env_name},
    )
    req_p95 = cw.Metric(
        namespace="novelgen/admin",
        metric_name="AdminRequestDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name},
    )
    mon_p95 = cw.Metric(
        namespace="novelgen/admin",
        metric_name="AdminRequestDurationMs",
        statistic="p95",
        period=cdk.Duration.minutes(5),
        dimensions_map={"Env": cfg.env_name, "Route": "/admin/monitoring/summary"},
    )

    for alarm in [
        cw.Alarm(stack, "U7AdminAuditWriteFailureHigh",
            alarm_name=f"{cfg.prefix}-admin-audit-write-failure-high",
            metric=audit_failure,
            threshold=0, evaluation_periods=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(stack, "U7AdminRequestP95High",
            alarm_name=f"{cfg.prefix}-admin-request-p95-high",
            metric=req_p95,
            threshold=2000, evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
        cw.Alarm(stack, "U7MonitoringAggregationSlow",
            alarm_name=f"{cfg.prefix}-monitoring-aggregation-slow",
            metric=mon_p95,
            threshold=5000, evaluation_periods=3,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        ),
    ]:
        alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))
```

---

## 7. 部署顺序

1. 发布新的 `services/api` 镜像（含 `routers/admin/` 子 package）→ ECR
2. `cdk diff` 检查（预期：+1 CloudFront behavior + 3 条 IAM statements + 3 条 Alarms + 1 条 S3 lifecycle）
3. `cdk deploy`：dev → stage → prod
4. 前端 `vite build` → `aws s3 sync apps/frontend-admin/dist/ s3://novels-raw-{env}/admin/ --delete`
5. `aws cloudfront create-invalidation --paths "/admin/index.html"`
6. 在 Cognito 控制台手动把目标用户提升为管理员（本 Unit 不创建 User Pool Group）

---

## 8. 回滚

- **前端回滚**：S3 版本化（继承 U6 保留 3 个版本 / 90 天）
- **后端回滚**：ECR tag 回退 → `ecs update-service`；CircuitBreaker 自动回滚
- **CDK 回滚**：`cdk deploy --rollback true`

---

## 9. 与其他 Unit 的依赖矩阵

| 依赖项 | 来源 | 变更 |
|---|---|---|
| api-service ECS | U1+U4+U5+U6 | 镜像更新（含 admin router） |
| novels-raw S3 | U1+U6 | 新增前缀 `admin/` + lifecycle |
| CloudFront | U1+U6 | +1 behavior |
| DDB tenancy + audit_events | U1 | 无结构变更；仅扩展 SK 模式 |
| Cognito User Pool | U1 | IAM 授权 ApiService 调用管理员 API；**不创建 Admin Group**（推迟 V2） |
| SNS alerts-topic | U1 | 订阅 +3 条 Alarm |

---

## 10. 安全基线明确声明（I2=C + I3=C 后果）

当前管理员防线：
- **Layer 1**：Cognito JWT 的 `custom:global_role` claim（AWS KMS 签名防伪）
- **Layer 2**：ApiService 的 `@require_admin_role` FastAPI 依赖（403 gate）
- **Layer 3（DDB）**：`audit_events` 表的 IAM Deny UpdateItem/DeleteItem（运行时不可篡改）

暂缺：
- **S3 归档不可篡改**（I2=C）：若管理员 token 被盗用，篡改 DDB 失败后再尝试改 S3 归档仍会成功；风险由 S3 bucket 级 IAM + CloudTrail 监控承担
- **MFA**（I3=C）：管理员账号密码被盗即可登录；依赖管理员密码强度 + Cognito User Pool 的高级安全特性（如 Adaptive Authentication）

**运维建议**：
- 管理员账户数量 ≤ 5
- 每季度轮换管理员密码
- CloudTrail 启用 `cognito-idp:AdminAddUserToGroup` 事件告警
- 尽快在 V2 补齐 MFA 与 Object Lock

---

## 11. 扩展规则合规摘要
`extensions/` 目录为空，无需 enforcement。
