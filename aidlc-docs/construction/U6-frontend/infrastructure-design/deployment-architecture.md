# U6 部署架构（Deployment Architecture）

**Unit**：U6 Frontend + BFF
**阶段**：Infrastructure Design
**日期**：2026-04-30

本文件包含 3 张架构图（I4=B 决策）：
1. **前后端数据流图** —— 用户 → CloudFront → (S3 / ALB → BFF → ApiService / SSE)
2. **部署拓扑图** —— U6 相对 U1-U5 的增量（★）
3. **CloudFront / ALB 路由流图** —— 请求如何按 path pattern 分派

---

## 1. 前后端数据流图

```
                     Browser (React SPA + Service Layer)
                              │
                              │ HTTPS
                              ▼
          ┌────────────────────────────────────────────────┐
          │          CloudFront Distribution                │
          │  (U1 pre-built, +3 behaviors in U6)             │
          │                                                  │
          │  Path matching:                                  │
          │  ├─ /api/v1/generations/*/chapters/*/stream ─▶ ALB
          │  ├─ /api/*, /auth/*, /telemetry ────────────▶ ALB
          │  └─ /* ────────────────────────────────────▶ S3
          └──────────┬─────────────────────┬────────────────┘
                     │                     │
             static  │                     │  API + SSE
                     ▼                     ▼
      ┌──────────────────────┐    ┌────────────────────────────┐
      │ S3 novels-raw bucket │    │ ALB (U1)                   │
      │ (U1, +frontend/      │    │  +2 listener rules         │
      │  prefix in U6)       │    │  +idle timeout 900s        │
      │  ┌────────────────┐  │    │                            │
      │  │ frontend/      │  │    │   TargetGroup:             │
      │  │  ├─ index.html │  │    │   ★ bff-user-tg            │
      │  │  └─ assets/    │  │    │                            │
      │  └────────────────┘  │    └──────────┬─────────────────┘
      │    OAC = CloudFront  │               │
      └──────────────────────┘               ▼
                                   ┌────────────────────────┐
                                   │ ★ ECS Fargate Service  │
                                   │   bff-user (2 tasks)   │
                                   │   Node 20 + Fastify    │
                                   │                        │
                                   │  Session store (LRU)   │
                                   │  Proxy standard / SSE  │
                                   │  CSRF middleware       │
                                   │  Telemetry EMF writer  │
                                   └──────────┬─────────────┘
                                              │
                                              │ internal HTTPS
                                              │ (Authorization: Bearer)
                                              ▼
                                   ┌────────────────────────┐
                                   │   ApiService (U1+U4+U5)│
                                   │   Internal ALB or      │
                                   │   Service Discovery    │
                                   └────────┬───────────────┘
                                            │
                          ┌─────────────────┴────────────────┐
                          ▼                                  ▼
                   DynamoDB / S3 / EventBridge      Bedrock / AgentCore
                   (U1 via adapters)                (U3/U4/U5 agents)

Secrets Manager (U1)
  └─ novelgen-{env}-bff-session-signing-key  ─▶ BFF Task via secrets injection

Cognito User Pool (U1)
  ◀── BFF refresh token flow ───────────────────────  BFF session middleware
```

---

## 2. 部署拓扑图（U6 增量 ★）

```
                    ┌─────────────────────────────────────────────┐
                    │ AWS Account (Region ap-northeast-1)         │
                    │                                             │
                    │  ┌────────────────────────────────────────┐ │
                    │  │ CloudFront (U1)                        │ │
                    │  │  ★ +3 behaviors (U6)                   │ │
                    │  └─────────┬──────────────┬───────────────┘ │
                    │            │              │                 │
                    │            ▼              ▼                 │
                    │     ┌───────────┐   ┌──────────┐           │
                    │     │ S3        │   │ ALB (U1) │           │
                    │     │ novels-   │   │ ★ +2     │           │
                    │     │ raw       │   │ rules    │           │
                    │     │ ★ /front  │   │ ★ idle   │           │
                    │     │ prefix    │   │ 900s     │           │
                    │     │ ★ life-   │   └───┬──────┘           │
                    │     │ cycle 90d │       │                  │
                    │     └───────────┘       │                  │
                    │                         ▼                  │
                    │  ┌─────────────────────────────────────┐   │
                    │  │ VPC (U1)                             │   │
                    │  │                                      │   │
                    │  │  ECS Cluster (U1)                    │   │
                    │  │   ├─ api-service        (U1+U4+U5)   │   │
                    │  │   ├─ worker-ingestion   (U2)         │   │
                    │  │   ├─ worker-analysis    (U3)         │   │
                    │  │   ├─ worker-generation  (U4)         │   │
                    │  │   ├─ worker-critic      (U5)         │   │
                    │  │   ├─ worker-consistency (U5)         │   │
                    │  │   ├─ worker-moderation  (U1, V2)     │   │
                    │  │   └─ ★ bff-user         (U6)         │   │
                    │  │       desired_count=2                 │   │
                    │  │       0.25 vCPU / 0.5 GB              │   │
                    │  │                                      │   │
                    │  │  ★ ALB TG bff-user-tg                 │   │
                    │  └─────────────────────────────────────┘   │
                    │                                             │
                    │  ┌─────────────────────────────────────┐   │
                    │  │ Secrets Manager (U1)                 │   │
                    │  │  ★ novelgen-{env}-bff-session-       │   │
                    │  │     signing-key (30d rotation)       │   │
                    │  └─────────────────────────────────────┘   │
                    │                                             │
                    │  ┌─────────────────────────────────────┐   │
                    │  │ Cognito User Pool (U1)               │   │
                    │  │   ◀── BFF refresh flow               │   │
                    │  └─────────────────────────────────────┘   │
                    │                                             │
                    │  ┌─────────────────────────────────────┐   │
                    │  │ CloudWatch                           │   │
                    │  │   ★ +5 Alarms (U6):                  │   │
                    │  │     SseTtftHigh (>5s P95)            │   │
                    │  │     LighthouseRegressed (<85)        │   │
                    │  │     ClientErrorRateHigh (>2%)        │   │
                    │  │     BffLatencyHigh (>500ms)          │   │
                    │  │     TelemetryQpsAnomalous (>3× base) │   │
                    │  │   ★ LogGroup /novelgen/{env}/bff-user│   │
                    │  └─────────────────────────────────────┘   │
                    │                                             │
                    │  ┌─────────────────────────────────────┐   │
                    │  │ ECR                                  │   │
                    │  │  ★ novelgen-bff-user repository     │   │
                    │  └─────────────────────────────────────┘   │
                    └─────────────────────────────────────────────┘

Legend: ★ = U6 net-new or modified; else inherited from U1.
```

---

## 3. CloudFront / ALB 路由流图

```
User Browser
    │
    │ HTTPS GET https://app.novelgen.example/...
    ▼
┌──────────────────────────────────────────────────────────┐
│ CloudFront Distribution (viewer-facing)                  │
│                                                          │
│  Behavior table (evaluated by precedence):               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Priority 10                                         │  │
│  │ Path: /api/v1/generations/*/chapters/*/stream      │  │
│  │   ├─ Cache: DISABLED                               │  │
│  │   ├─ Origin: ALB                                   │  │
│  │   ├─ Origin Request Policy: AllViewerExceptHost    │  │
│  │   └─ Response: passthrough (text/event-stream)     │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Priority 20                                         │  │
│  │ Path: /api/*  /auth/*  /telemetry                  │  │
│  │   ├─ Cache: DISABLED                               │  │
│  │   ├─ Origin: ALB                                   │  │
│  │   └─ Allowed methods: all                          │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Priority 99 (DEFAULT)                               │  │
│  │ Path: /*                                           │  │
│  │   ├─ Cache: Optimized (1d min / 1y max)            │  │
│  │   ├─ Origin: S3 novels-raw @ /frontend             │  │
│  │   ├─ Response headers: SPA fallback → index.html   │  │
│  │   │   for 404 paths matched by router              │  │
│  │   └─ Cache-Control respected per object            │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────┬─────────────────┬─────────────────┘
                       │                 │
                static │                 │  API + Auth + Telemetry
                       ▼                 ▼
               S3 /frontend        ALB (HTTPS :443)
                                       │
                                       ▼
                                ┌──────────────────────────────────┐
                                │ ALB Listener (443)                │
                                │  Listener rules by precedence:    │
                                │                                   │
                                │  pri 90:                          │
                                │    path = /api/v1/generations/*/  │
                                │           chapters/*/stream       │
                                │    forward → bff-user-tg          │
                                │    (same TG, rule kept for audit) │
                                │                                   │
                                │  pri 100:                         │
                                │    path = /api/*, /auth/*,        │
                                │           /telemetry              │
                                │    forward → bff-user-tg          │
                                │                                   │
                                │  pri 1000+ (preserved from U1,    │
                                │    if any directly to             │
                                │    api-service-tg):               │
                                │    —  ★ In U6 we lower their      │
                                │       priority so BFF rules fire  │
                                │       first; BFF becomes sole     │
                                │       /api/* entry.               │
                                │                                   │
                                │  idle timeout: 900s (↑ from 60s)  │
                                └──────────┬────────────────────────┘
                                           │
                                           ▼
                                ┌──────────────────────────────────┐
                                │ bff-user-tg (TargetType=IP)       │
                                │  health /healthz every 15s        │
                                │  stickiness cookie AWSALB 6h      │
                                └──────────┬────────────────────────┘
                                           │
                                           ▼
                                ┌──────────────────────────────────┐
                                │ bff-user Fargate Tasks (×2)       │
                                │  Fastify server on :3000          │
                                │    /auth/* — Cognito flow + sid   │
                                │    /api/*  — proxy to ApiService  │
                                │    /api/v1/.../stream — SSE proxy │
                                │    /telemetry — EMF writer        │
                                │    /healthz — ALB health           │
                                └──────────┬────────────────────────┘
                                           │
                                           │  internal HTTPS
                                           │  Authorization: Bearer idToken
                                           │  X-Team-Id: session.team_id
                                           ▼
                                ┌──────────────────────────────────┐
                                │ ApiService (U1+U2+U4+U5)          │
                                │   via Service Discovery or        │
                                │   internal ALB                    │
                                └──────────────────────────────────┘
```

---

## 4. 关键非功能保证

- **SSE idle timeout**：ALB 全局 idle timeout 调至 900s，覆盖 Chapter 流式最坏 10 分钟预期（超过则 SSE 自然结束，浏览器重连）
- **ALB sticky**：`AWSALB` cookie 6h —— 保证同会话落在同 BFF 实例（D1=A 进程内 LRU 要求）
- **TLS 终端**：CloudFront + ALB 双层，都在 ACM 证书下
- **BFF 不公开暴露**：ECS Service 只附 ALB 内部 target group；无 public IP

---

## 5. 部署风险与缓解

| 风险 | 缓解 |
|---|---|
| 调整 ALB idle timeout 60s → 900s 影响 U1-U5 现有规则 | 提前在 stage 环境压测长连接；现有规则对 idle 不敏感 |
| CloudFront behaviors 新增 3 条，与 U1 既有冲突 | 以新 priority 10/20 插入，不改现有默认 |
| Bucket policy 改动误放开其它前缀 | 使用 `Condition.StringEquals.AWS:SourceArn == CloudFront distribution ARN` + `s3:prefix=frontend/*` |
| BFF LRU 会话丢失 | ALB sticky + Rolling 部署 drain 30s；用户感知为单次重登（可接受） |

---

## 6. 架构图文本导出说明

三张图使用 ASCII 盒形标记，与 `infrastructure-design.md` 及 `logical-components.md` 资源名严格一致；PDF 导出建议 monospace 字体。
