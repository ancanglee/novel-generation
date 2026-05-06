# U6 基础设施设计（Infrastructure Design）

**Unit**：U6 Frontend + BFF
**阶段**：Infrastructure Design
**日期**：2026-04-30

---

## 1. 总体原则

U6 几乎全部复用 U1 底座。增量资源通过 `shared_constructs/u6_extensions.py` 注入（对齐 U2-U5）。前端静态产物直接落到 U1 预建 `novels-raw` bucket 的 `/frontend/` 前缀（I2=A），CloudFront behaviors 指向该前缀。

- **I1=A**：`shared_constructs/u6_extensions.py::apply_u6_extensions`
- **I2=A**：复用 `novels-raw` bucket，新前缀 `frontend/` + 独立 CloudFront behavior + Cache-Control 策略区分
- **I3=A**：ECS Fargate Service `bff-user`（同 U1 ECS Cluster，新 Task Definition）

---

## 2. CDK 组织

```
infra/
└── shared_constructs/
    ├── u2_extensions.py
    ├── u3_extensions.py
    ├── u4_extensions.py
    ├── u5_extensions.py
    └── u6_extensions.py        # NEW
```

### 2.1 `u6_extensions.py` 对外 helper

```python
def apply_u6_extensions(
    stack, cfg, *,
    cluster: ecs.ICluster,
    alb: elbv2.ApplicationLoadBalancer,
    alb_listener: elbv2.ApplicationListener,
    novels_bucket: s3.IBucket,
    cloudfront_distribution: cloudfront.IDistribution,
    api_service_dns: str,
    cognito_user_pool_id: str,
    cognito_client_id: str,
) -> BffReference: ...
```

返回 `BffReference` 给 Compute/Observability stacks 继续扩展（如告警订阅）。

### 2.2 4 个 extend 子函数

| helper | 功能 |
|---|---|
| `extend_data_stack` | S3 bucket lifecycle 扩展 `frontend/` 前缀 + 静态资源 CORS |
| `extend_identity_stack` | BFF Task Role（读 Secret、写日志、可选 cognito refresh） |
| `extend_edge_stack` | CloudFront 3 new behaviors + cache policy + origin request policy |
| `extend_compute_stack` | bff-user ECS Service + Task Definition + ALB Target Group + 2 listener rules |
| `extend_observability_stack` | 4+1 CloudWatch Alarms |

---

## 3. 资源清单

### 3.1 S3 Bucket 扩展（I2=A）

复用 U1 `novels-raw` bucket，新增对象前缀 `frontend/`：

```
s3://novels-raw-{env}/
├── teams/{team_id}/...                 # U2 数据（保持 U1 lifecycle）
└── frontend/
    ├── index.html                       # Cache-Control: no-cache
    ├── assets/
    │   ├── main-{hash}.js               # Cache-Control: public,max-age=31536000,immutable
    │   ├── chunk-analysis-{hash}.js
    │   └── ...
    └── static/
```

**Lifecycle rule** 新增：
- 前缀 `frontend/` 保留 3 个旧版本（非当前版本 90d 后过期），便于快速回滚
- 其余前缀维持 U2 lifecycle

**Bucket Policy** 追加：允许 CloudFront OAC `cloudfront.amazonaws.com` 通过 AWS:SourceArn 条件读 `frontend/*`。

### 3.2 CloudFront Behaviors（新增 3 条）

基于 U1 已有 distribution 追加：

| 优先级 | Path Pattern | Origin | Cache Policy | Origin Request Policy |
|---|---|---|---|---|
| 10 | `/api/v1/generations/*/chapters/*/stream` | ALB | `CachingDisabled` | `AllViewerExceptHostHeader` |
| 20 | `/api/*`, `/auth/*`, `/telemetry` | ALB | `CachingDisabled` | `AllViewerExceptHostHeader` |
| 99 | `/*`（默认） | S3 `frontend/` | `CachingOptimized` | `CORS-S3Origin` |

**CachingDisabled** 确保 SSE / API 走穿；CloudFront 会把 `Cache-Control`、`Content-Type: text/event-stream` 透传。

**Origin Path** 对 S3 origin 设为 `/frontend`，使 CloudFront URL `/index.html` 对应到 `s3://novels-raw-{env}/frontend/index.html`。

### 3.3 ALB Listener Rules（追加 2 条）

在 U1 HTTPS listener 上追加：

| 优先级 | 条件 | Action |
|---|---|---|
| 90 | Path `/api/v1/generations/*/chapters/*/stream` | forward → `bff-user-tg`（idle timeout 独立） |
| 100 | Path `/api/*` OR `/auth/*` OR `/telemetry` | forward → `bff-user-tg` |

（U1 已有的 `/api/v1/novels/*` 等直达 ApiService 的规则优先级设在 1000+，U6 的规则优先级低于那些更具体的 —— 实际拆分看 U1 ALB rule 真实配置，必要时 U6 拦截 /api/* 全部并由 BFF 再反代到 ApiService。本设计按此模型）

> **决策**：U6 BFF 作为所有 `/api/*` 流量的唯一入口。U1 ALB 上若有直接指向 ApiService 的 `/api/*` 规则，U6 部署时会调整优先级，使 BFF 规则先命中；ApiService 仅由 BFF 作为下游反代访问（内部 ALB 或 Service Discovery）。

### 3.4 ECS Fargate Service `bff-user`

```python
task_def = ecs.FargateTaskDefinition(
    stack, "U6BffTaskDef",
    cpu=256,               # 0.25 vCPU
    memory_limit_mib=512,
    task_role=bff_task_role,
    execution_role=execution_role,
    runtime_platform=ecs.RuntimePlatform(
        operating_system_family=ecs.OperatingSystemFamily.LINUX,
        cpu_architecture=ecs.CpuArchitecture.ARM64,
    ),
)
container = task_def.add_container(
    "bff",
    image=ecs.ContainerImage.from_ecr_repository(bff_ecr_repo, tag="u6-latest"),
    logging=ecs.LogDriver.aws_logs(
        stream_prefix="bff-user",
        log_retention=logs.RetentionDays.ONE_MONTH,
    ),
    environment={
        "NOVELGEN_ENV": cfg.env_name,
        "API_BASE_URL": api_service_dns,
        "COGNITO_USER_POOL_ID": cognito_user_pool_id,
        "COGNITO_APP_CLIENT_ID": cognito_client_id,
        "PORT": "3000",
    },
    secrets={
        "SESSION_SIGNING_KEY": ecs.Secret.from_secrets_manager(session_signing_secret),
    },
    port_mappings=[ecs.PortMapping(container_port=3000, protocol=ecs.Protocol.TCP)],
)

service = ecs.FargateService(
    stack, "U6BffService",
    cluster=cluster,
    task_definition=task_def,
    desired_count=2,
    circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
    enable_execute_command=True,
    assign_public_ip=False,
)
```

- **Auto Scaling**：CPU 70% 触发 +1 task，min=2 / max=6
- **Deployment Controller**: `ECS` rolling（不启用 Blue/Green 以简化）

### 3.5 ALB Target Group

```python
bff_tg = elbv2.ApplicationTargetGroup(
    stack, "U6BffTg",
    vpc=vpc, port=3000, protocol=elbv2.ApplicationProtocol.HTTP,
    target_type=elbv2.TargetType.IP,
    health_check=elbv2.HealthCheck(path="/healthz", interval=cdk.Duration.seconds(15)),
    deregistration_delay=cdk.Duration.seconds(15),
    stickiness_cookie_duration=cdk.Duration.hours(6),   # ALB sticky cookie AWSALB（D1=A 会话）
)
service.attach_to_application_target_group(bff_tg)
```

**Idle timeout** 对 `bff-user-tg` 设置 ALB 整体 idle timeout 延长到 900 秒（ALB-level，其它规则共用）—— 满足 SSE 长连接。实际由 ALB 全局 attribute `idle_timeout.timeout_seconds=900` 控制。U1 ALB 默认 60s，U6 把它调至 900s（向前兼容所有 U1-U5 rule）。

### 3.6 Secrets Manager Secret

`novelgen-{env}-bff-session-signing-key`：32-byte 随机值，30 天自动轮换（U1 轮换 Lambda 通用）。

### 3.7 CloudWatch Alarms（4 + 1，NFR Design §8.1 + §4.2）

| Alarm | Metric | 阈值 |
|---|---|---|
| `U6-{env}-SseTtftHigh` | `novelgen/frontend::SseTtftMs` P95 | > 5_000 ms |
| `U6-{env}-LighthouseRegressed` | `novelgen/frontend::LighthousePerf` (nightly) | < 85 |
| `U6-{env}-ClientErrorRateHigh` | `ClientError` / request count | > 2% |
| `U6-{env}-BffLatencyHigh` | ALB TargetResponseTime `bff-user-tg` P95 | > 500 ms |
| `U6-{env}-TelemetryQpsAnomalous` | `/telemetry` ALB req count | > 3× baseline |

所有 Alarm 发 SNS `ops-warn`，`ClientErrorRateHigh` 发 `ops-critical`。

---

## 4. IAM

### 4.1 BFF Task Role
```python
bff_task_role.add_to_policy(iam.PolicyStatement(
    actions=["secretsmanager:GetSecretValue"],
    resources=[session_signing_secret.secret_arn],
))
bff_task_role.add_to_policy(iam.PolicyStatement(
    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
    resources=["*"],
))
bff_task_role.add_to_policy(iam.PolicyStatement(
    actions=["cognito-idp:InitiateAuth", "cognito-idp:RespondToAuthChallenge"],
    resources=[f"arn:aws:cognito-idp:{region}:{account}:userpool/{user_pool_id}"],
))
```

> BFF **不直接**访问 DynamoDB / S3 / Bedrock —— 所有数据操作经 ApiService 鉴权后转发。

### 4.2 CloudFront OAC
CloudFront OAC 已由 U1 预建；U6 仅在 bucket policy 追加允许读 `frontend/*` 的语句。

---

## 5. Docker 镜像组织

```
novelgen-bff-user:u6-{git_sha}            # 基于 node:20-bookworm-slim
```

多阶段构建：
- **builder**：pnpm install + tsc + bundle
- **runtime**：仅拷贝 `dist/` + `node_modules`（--prod），非 root 用户

目标镜像约 120 MB。

---

## 6. 部署顺序

1. 发布 `novelgen-bff-user:u6-{sha}` 到 ECR
2. `cdk diff` 检查：预期 1 ECS Service + 1 Task Def + 1 TG + 2 listener rules + 3 CloudFront behaviors + 1 Secret + 5 Alarms + bucket policy patch
3. `cdk deploy` dev → stage → prod
4. 前端 `vite build` → `aws s3 sync dist/ s3://novels-raw-{env}/frontend/ --delete --cache-control ...`
5. `aws cloudfront create-invalidation --paths "/index.html"`（其他资源由 content-hash 保证 immutable）

---

## 7. 回滚策略

- **BFF 回滚**：ECR tag 回退 → ECS update-service；circuit-breaker=rollback 自动回退失败部署
- **前端回滚**：S3 bucket 版本化开启；`aws s3 sync` 时保留 3 个历史；紧急回滚：
  1. 从 S3 恢复旧版 `frontend/` objects
  2. `cloudfront create-invalidation /*`
- **CDK 回滚**：`cdk deploy --rollback true`；shared_constructs 变更仅影响 U6 scope

---

## 8. 与其他 Unit 依赖矩阵

| 依赖项 | 来源 | 变更 |
|---|---|---|
| Cognito User Pool | U1 | 无 |
| CloudFront Distribution | U1 | +3 behaviors |
| ALB | U1 | +2 rules + idle timeout 60s → 900s |
| ECS Cluster | U1 | +1 Service |
| `novels-raw` S3 bucket | U1 | +prefix policy + lifecycle |
| Secrets Manager | U1 | +1 secret |
| ApiService | U1/U2/U4/U5 | 0（BFF 作为下游消费） |
| VPC / Security Groups | U1 | 0（BFF 用 U1 私有 subnet + U1 通用 SG） |

---

## 9. 扩展规则合规摘要
extensions 目录为空，无需 enforcement。
