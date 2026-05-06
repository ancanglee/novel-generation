# U5 基础设施设计（Infrastructure Design）

**Unit**：U5 Critic & Consistency
**阶段**：Infrastructure Design
**日期**：2026-04-28

---

## 1. 总体原则

U5 资源增量极少（1 Rule + 3 SSM + 4 Alarms + 4 API 路由 + 2 ECS 镜像更新 + 4 DDB SK 模式）。**不新建 Stack**，而是通过 CDK `shared_constructs/u5_extensions.py` 对 U1 Stack 做轻量补丁（与 U2/U3/U4 风格保持一致）。

- **I1=A**：`shared_constructs/u5_extensions.py::apply_u5_extensions(stack, props)` 集中声明 U5 资源
- **I3=C**：`consistency.trigger` Rule 归属 **U4** 的事件语义（事件源 ChapterAgent 在 U4 Worker 内），因此以 **retrofit 方式** 追加到已有的 `shared_constructs/u4_extensions.py::apply_u4_extensions(stack, props)` 中 —— U4 infra 已完成，U5 infra 阶段对其做一次增量 patch，CDK `cdk diff` 只新增该 Rule + 相关 IAM

---

## 2. CDK 组织

```
infra/
├── app.py
├── stacks/
│   ├── u1_platform_stack.py         # 已存在
│   └── ...
└── shared_constructs/
    ├── u2_extensions.py             # 已存在
    ├── u3_extensions.py             # 已存在
    ├── u4_extensions.py             # 已存在 —— U5 阶段 retrofit 追加 consistency-trigger Rule
    └── u5_extensions.py             # 新增
```

### 2.1 `u4_extensions.py` retrofit 新增内容

```python
# shared_constructs/u4_extensions.py (已存在)
def apply_u4_extensions(stack, props):
    # ... existing U4 resources (ChapterAgent SFN, worker ECR, etc.) ...

    # === U5 retrofit: consistency-trigger Rule ===
    # 事件源在 U4 ChapterAgent，逻辑归 U4 管理
    stack.consistency_trigger_rule = events.Rule(
        stack, "ConsistencyTriggerRule",
        rule_name=f"novelgen-{props.env}-consistency-trigger",
        event_bus=stack.default_bus,          # U1 预建 novelgen-default-bus
        event_pattern=events.EventPattern(
            source=["novelgen.chapter_agent"],
            detail_type=["consistency.trigger"],
        ),
    )
    stack.consistency_trigger_rule.add_target(
        targets.SqsQueue(
            stack.consistency_queue,           # U1 预建
            message_group_id=events.EventField.from_path("$.detail.generation_id"),  # 同 generation 串行
        )
    )
```

### 2.2 `u5_extensions.py` 新增内容

```python
def apply_u5_extensions(stack, props):
    """U5 Critic & Consistency 资源扩展。"""

    # --- 1. SSM Parameters ---
    for name, default in [
        ("consistency-interval", "10"),
        ("conflict-rewrite-max-attempts", "3"),
        ("critic-layer2-recent-summary-count", "5"),
    ]:
        ssm.StringParameter(
            stack, f"U5SsmParam-{name}",
            parameter_name=f"/novelgen/{props.env}/config/{name}",
            string_value=default,
        )

    # --- 2. CloudWatch Alarms ---
    _create_u5_alarms(stack, props)

    # --- 3. IAM 补充 ---
    _extend_worker_roles(stack, props)

    # --- 4. api-service 环境变量注入 ---
    stack.api_service_task_def.add_environment(
        "U5_CRITIC_REPORT_SK_PREFIX", "CRITIQUE#"
    )
    stack.api_service_task_def.add_environment(
        "U5_CONSISTENCY_REPORT_SK_PREFIX", "CONSISTENCY#"
    )
    stack.api_service_task_def.add_environment(
        "U5_CONFLICT_SK_PREFIX", "CONFLICT#"
    )
```

---

## 3. 资源清单

### 3.1 EventBridge Rule（retrofit 到 U4）

| Rule | Event Bus | Pattern | Target |
|---|---|---|---|
| `novelgen-{env}-consistency-trigger` | `novelgen-default-bus`（U1） | `source=novelgen.chapter_agent, detail-type=consistency.trigger` | `consistency-queue`（U1 SQS） |

> **归属**：由于事件源在 U4 ChapterAgent，Rule 在 `u4_extensions.py` 内声明（I3=C 决策）。U5 阶段对 u4_extensions 做 retrofit patch。

### 3.2 SSM Parameters（U5 新增）

| Parameter | 默认值 | 用途 |
|---|---|---|
| `/novelgen/{env}/config/consistency-interval` | 10 | 每 N 章触发一次 Consistency |
| `/novelgen/{env}/config/conflict-rewrite-max-attempts` | 3 | 同一 Conflict 最大重写尝试数 |
| `/novelgen/{env}/config/critic-layer2-recent-summary-count` | 5 | Critic Layer-2 上下文纳入的最近章节 summary 数 |

### 3.3 CloudWatch Alarms（U5 新增 4 条）

| Alarm | Metric (ns=`novelgen/critic`) | Evaluation | Threshold | Action |
|---|---|---|---|---|
| `U5-{env}-CriticDurationHigh` | `CriticDurationMs` P95, 5 min | 3/3 | > 60_000 ms | SNS `ops-critical` |
| `U5-{env}-ConsistencyDurationHigh` | `ConsistencyDurationMs` P95, 5 min | 3/3 | > 240_000 ms | SNS `ops-critical` |
| `U5-{env}-CriticFailureRateHigh` | `CriticFailureCount / CriticTotalCount` | 3/3 (5 min) | > 5% | SNS `ops-critical` |
| `U5-{env}-ConflictLoopDetected` | `ConflictLoopDetected` Sum 1 min | 1/1 | > 0 | SNS `ops-critical`（立即告警） |

全部复用 U1 已创建的 SNS topic `novelgen-{env}-ops-critical`。

### 3.4 DynamoDB SK 模式（零新表）

| SK | Item | GSI 需求 |
|---|---|---|
| `CRITIQUE#{generation_id}#{idx:05d}` | CritiqueReport | 无 |
| `CONSISTENCY#{generation_id}#{scan_to:05d}` | ConsistencyReport | 无 |
| `CONFLICT#{generation_id}#{conflict_id}` | ConflictItem (rewrite_attempts, frozen) | 无（by conflict_id 直查） |
| `GEN_SCAN#{generation_id}` | last_scan_to 游标 | 无 |

全部写入 U1 预建 `novelgen_tenancy` 表（PK=`TEAM#{team_id}`，SK 见上）。CDK 无需变更。

### 3.5 ECS Services（复用 U1 预建，仅镜像更新）

| Service | 用途 | desired_count | 镜像 Tag |
|---|---|---|---|
| `worker-critic` | Opus 4.7 复核 | 1（min=1, max=4） | U5 发布后更新为 `critic:u5-{git_sha}` |
| `worker-consistency` | Sonnet 4.6 增量扫描 | 1（min=1, max=2） | U5 发布后更新为 `consistency:u5-{git_sha}` |
| `worker-moderation` | V2 预留 | **0** | 保留 U1 预建，不激活 |
| `api-service` | FastAPI 主服务 | 2（已 U4 设定） | 追加 4 个 U5 路由，发布为 `api:u5-{git_sha}` |

### 3.6 IAM 扩展

`worker-critic` / `worker-consistency` Task Role 在 U1 基础 IAM 上追加：

```python
task_role.add_to_policy(iam.PolicyStatement(
    actions=["events:PutEvents"],
    resources=[stack.default_bus.event_bus_arn],
))
task_role.add_to_policy(iam.PolicyStatement(
    actions=["bedrock:InvokeModel", "bedrock:Converse", "bedrock:ConverseStream"],
    resources=[
        f"arn:aws:bedrock:{region}::foundation-model/claude-opus-4-7*",
        f"arn:aws:bedrock:{region}::foundation-model/claude-sonnet-4-6*",
    ],
))
# AOSS + Neptune 已在 U3 阶段授予（MemoryFacade 消费者共用同一 Role）
task_role.add_to_policy(iam.PolicyStatement(
    actions=["ssm:GetParameter", "ssm:GetParameters"],
    resources=[
        f"arn:aws:ssm:{region}:{account}:parameter/novelgen/{env}/config/*",
    ],
))
```

`api-service` Task Role 补充：
```python
# CONFLICT / CRITIQUE / CONSISTENCY SK 都在 novelgen_tenancy 表内 —— U1 已授予该表完全读写
# 但需新增 PutEvents（调 U4 rewrite 端点时发 events 不需要，调 U4 是内部 HTTP；保持原状即可）
```

---

## 4. API 端点部署（I2=A）

4 个 U5 端点追加到现有 `api-service` 的 FastAPI app：

```python
# app/main.py
from app.routes import (
    generations,        # U4 existing
    critique,           # U5 new
    consistency,        # U5 new
    conflicts,          # U5 new
)

app.include_router(critique.router, prefix="/api/v1")
app.include_router(consistency.router, prefix="/api/v1")
app.include_router(conflicts.router, prefix="/api/v1")
```

| Endpoint | Method | Handler |
|---|---|---|
| `/generations/{gid}/chapters/{n}/critique` | GET | `critique.get_critique` |
| `/generations/{gid}/consistency-reports?since_chapter={n}` | GET | `consistency.list_reports` |
| `/conflicts/{conflict_id}/ignore` | POST | `conflicts.ignore_conflict` |
| `/conflicts/{conflict_id}/rewrite` | POST | `conflicts.rewrite_conflict` → 内部调 U4 `POST /generations/{gid}/chapters/{n}/rewrite` |

- 鉴权：复用 U1 `RequireTeamMember` 装饰器
- 限流：复用 U1 `X-Team-Id` 窗口限流
- 所有 DDB 访问复用 `TenancyRepository`（U1 提供）

---

## 5. Docker 镜像组织

沿用 U3/U4 的 base layer 复用策略：

```
novelgen-base:{arch}              # U1 提供（Python 3.12 + boto3 + pydantic + shared libs）
  ├─ novelgen-critic:u5-{sha}     # worker-critic 镜像（+ strands + prompts/critic.yaml）
  ├─ novelgen-consistency:u5-{sha}# worker-consistency 镜像（+ diff utils + prompts/consistency.yaml）
  └─ novelgen-api:u5-{sha}        # api-service 镜像（U4 之上追加 U5 routes）
```

目标大小：critic ~280 MB / consistency ~280 MB / api ~300 MB（与 U3/U4 持平）。

---

## 6. 参数读取与热更新

Worker 启动时读取 SSM，并每 60 秒刷新一次（沿用 U3 `SsmConfigCache`）：

```python
cache = SsmConfigCache(prefix=f"/novelgen/{env}/config", refresh_interval=60)
interval = cache.get_int("consistency-interval", 10)
max_attempts = cache.get_int("conflict-rewrite-max-attempts", 3)
```

---

## 7. Observability

- Metric namespace：`novelgen/critic`
- 复用 U1 AgentCore Observability（OTel + CloudWatch Logs `/novelgen/{env}/critic` 和 `/novelgen/{env}/consistency`）
- Log 保留：7 天 (dev) / 30 天 (prod)
- Trace：CriticContext.request_id 贯穿 SQS → worker → Bedrock → DDB → EventBridge

---

## 8. 部署顺序（从 U4 → U5）

1. **更新 `shared_constructs/u4_extensions.py`** —— 追加 `ConsistencyTriggerRule`
2. **创建 `shared_constructs/u5_extensions.py`**
3. **在 U1 Stack 构造函数末尾调用** `apply_u5_extensions(self, props)`
4. `cdk diff` 检查：预期仅增量 1 Rule + 3 SSM + 4 Alarms + 少量 IAM statements + Task Def env vars
5. `cdk deploy` —— 按 dev → stage → prod
6. 更新 worker-critic / worker-consistency / api-service 镜像到 `u5-{sha}` tag，rolling update
7. moderation-queue / worker-moderation 保留，`desired_count=0` 不变（V2 启用时再 flip）

---

## 9. 扩展规则合规摘要

extensions 目录为空，无 opt-in 扩展需要 enforcement。

---

## 10. 与其他 Unit 的依赖矩阵

| 依赖项 | 来源 Unit | 本阶段是否变更 |
|---|---|---|
| `novelgen_tenancy` DDB 表 | U1 | ✗（新增 SK 模式不改表结构） |
| `novelgen-default-bus` | U1 | ✗ |
| `critic-queue` / `consistency-queue` / `moderation-queue` | U1 | ✗ |
| `worker-critic` / `worker-consistency` ECS Service | U1 | 镜像更新 |
| `worker-moderation` ECS Service | U1 | ✗（保留 desired=0） |
| `api-service` ECS Service | U1 + U4 | 镜像更新（追加 router） |
| `MemoryFacade` (AOSS + Neptune) | U3 | ✗ |
| `Outline.items[].summary` | U4 | ✗（只读） |
| U4 `POST /rewrite` 端点 | U4 | ✗（U5 作为调用方） |
