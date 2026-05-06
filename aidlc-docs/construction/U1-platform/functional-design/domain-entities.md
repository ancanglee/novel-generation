# U1 Domain Entities

**Unit**：U1 Platform & Infrastructure
**阶段**：Functional Design
**日期**：2026-04-27

本文定义 U1 层的领域实体（非数据库 schema；后者在 Infrastructure Design 中映射）。

---

## E1. User

表示一个已注册的平台用户。

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID | 主键（Cognito sub）|
| email | Email | 登录邮箱 |
| display_name | String | 显示名 |
| team_id | UUID | **归属的 Team（U1-F1=A，1:N）** |
| global_role | Enum{REGULAR, ADMIN, MODERATOR} | 全局角色（Cognito Group 映射）|
| status | Enum{ACTIVE, DISABLED} | 状态 |
| created_at | Timestamp | 注册时间 |
| last_login_at | Timestamp | 最近登录 |

**业务约束**：
- user_id 不可变
- 一个 User 恰好属于一个 team_id（变更 team 需要管理员操作或重新登录流程）
- email 全局唯一

---

## E2. Team

表示一个租户边界。

| 字段 | 类型 | 说明 |
|---|---|---|
| team_id | UUID | 主键 |
| name | String | 团队显示名 |
| owner_user_id | UUID | 团队所有者 |
| status | Enum{ACTIVE, DISABLED} | 状态 |
| created_at | Timestamp | 创建时间 |

**业务约束**：
- 注册新用户时自动创建一个个人 Team（team_id 新生成，owner=user_id）
- Team 删除时其下所有 User 必须先迁移或删除
- team_id 贯穿 DynamoDB PK、S3 key 前缀、Neptune/OpenSearch namespace，是多租户隔离的核心键

---

## E3. Role（角色模型 U1-F2=B）

**全局角色**（Cognito Group）：
- `regular_user`：默认
- `admin`：跨 team 全局管理
- `content_moderator`：内容审核员

**Team 级角色**（Cognito custom:team_roles JSON）：
```json
{ "team_id_1": "owner", "team_id_2": "member" }
```
- `owner`：Team 的所有者
- `member`：普通成员
- `moderator`：Team 内的内容审核员（如果 Team 内做审核）

由于 U1-F1=A（1:N），custom:team_roles 实际只有 1 个条目。保留 JSON 结构是为了 V2 升级到 M:N 时无需修改字段。

---

## E4. Principal（身份上下文）

每个已认证请求解析出的不可变值对象，在整个请求生命周期内传递。

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | UUID | |
| team_id | UUID | 用户当前所属 team（取自 User.team_id）|
| email | Email | |
| global_role | Enum | `REGULAR / ADMIN / MODERATOR` |
| team_role | Enum | `OWNER / MEMBER / MODERATOR` |
| jwt_expiry | Timestamp | token 过期时间 |

**业务约束**：
- Principal 在 AuthAdapter 中从 Cognito JWT 构造，只读
- **U1-F5=C** 决定：Principal 作为**显式参数**在函数签名中传递，不使用 ContextVar

---

## E5. Job

长时任务的统一抽象。所有任务类型（分析/大纲/章节/Critic/一致性/审核）共享此实体（**U1-F3=A 统一状态机**）。

| 字段 | 类型 | 说明 |
|---|---|---|
| job_id | UUID | 主键 |
| team_id | UUID | 租户 |
| owner_user_id | UUID | 创建者 |
| job_type | Enum{ANALYSIS, OUTLINE, CHAPTER, CRITIC, CONSISTENCY, MODERATION, INGESTION, EXPORT} | 任务类型 |
| subject_id | UUID | 关联实体（novel_id / generation_id / chapter_id）|
| status | Enum{QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELED} | 统一状态机 |
| progress | Int (0-100) | 进度 |
| error_code | String? | 失败错误码 |
| error_message | String? | 失败错误信息 |
| cancel_requested | Bool | 取消标志（US-06 的 Cancel 端点写入）|
| step_functions_execution_arn | ARN? | Step Functions 执行句柄 |
| payload | JSON | 任务输入参数 |
| result_ref | String? | 结果存储位置（S3 key 或 DynamoDB ref）|
| token_usage | Object{input, output, model} | Bedrock token 记账 |
| started_at | Timestamp | |
| ended_at | Timestamp? | |
| created_at | Timestamp | |

**统一状态机**：
```
QUEUED ──► RUNNING ──► SUCCEEDED
   │          │
   │          ├──► FAILED
   │          │
   │          └──► CANCELED
   │
   └───────────────► CANCELED（未开始即取消）
```

---

## E6. AuditEvent

Admin 管理操作的审计记录（**U1-F4=A 仅 Admin 管理操作**）。

| 字段 | 类型 | 说明 |
|---|---|---|
| audit_id | UUID | 主键 |
| timestamp | Timestamp | ISO 8601 |
| actor_user_id | UUID | 操作者（Admin） |
| actor_team_id | UUID | 操作者所属 team |
| action | Enum{USER_CREATE, USER_DISABLE, TEAM_CREATE, TEAM_DISABLE, MEMBER_ADD, MEMBER_REMOVE, MODEL_CONFIG_UPDATE, CONCURRENCY_UPDATE, SCHEMA_UPSERT, TAG_MERGE, ALERT_UPSERT} | 动作类型 |
| target_type | String | 目标资源类型（例如 "User" / "Team" / "ModelConfig"）|
| target_id | String | 目标资源 ID |
| before | JSON? | 变更前 |
| after | JSON? | 变更后 |
| request_id | UUID | 关联请求 trace id |

**业务约束**：
- 仅对 Admin 管理操作写入；普通用户的数据访问与生成/导出**不写**审计（U1-F4=A）
- 不可修改，不可删除（append-only）

---

## E7. Fact（事实，供 MemoryFacade 使用）

小说理解与生成过程中产生的结构化事实。

| 字段 | 类型 | 说明 |
|---|---|---|
| fact_key | String | 业务键（幂等主键）**U1-F6=B** |
| team_id | UUID | 租户 |
| novel_id | UUID | 关联小说 |
| fact_type | Enum{CHARACTER_SNAPSHOT, MAP_PLACE, MAP_EDGE, EVENT, STYLE_VECTOR, RULE} | 事实类型 |
| content | JSON | 事实内容（pydantic 模型序列化）|
| source_chapter | Int? | 来源章节号 |
| embedding | Vector? | 可选向量表示（用于语义检索）|
| created_at | Timestamp | |

**fact_key 的生成规则**（U1-F6=B 业务键）：
```
CHARACTER_SNAPSHOT:  "character:{normalized_name}:chapter:{n}"
MAP_PLACE:           "place:{normalized_name}"
MAP_EDGE:            "edge:{place_a}:{edge_type}:{place_b}"
EVENT:               "event:{chapter}:{seq}"
STYLE_VECTOR:        "style:{novel_id}"
RULE:                "rule:{normalized_rule_text}"
```

同一 fact_key 的写入为幂等覆盖（upsert），不产生重复 Memory 污染。

---

## E8. ModelConfig（模型配置）

Admin 在后台为每个任务阶段配置 Claude 模型。

| 字段 | 类型 | 说明 |
|---|---|---|
| config_id | UUID | 主键 |
| version | Int | 单调递增，用于 Worker 轮询对比 |
| mapping | Map<Stage, Entry> | 9 个 Stage 的模型映射 |
| updated_by_user_id | UUID | 修改者 |
| updated_at | Timestamp | |

**Stage 列表**：
`classification / character / map / style / outline / chapter / self_critique / critic / consistency`

**Entry**：
```
{ model_id: "anthropic.claude-opus-4-7" | ... , fallback: "anthropic.claude-sonnet-4-6" | null }
```

---

## E9. ConcurrencyConfig（细读并发配置 AD6=F）

| 字段 | 类型 | 说明 |
|---|---|---|
| config_id | UUID | 主键（单例）|
| deep_read_max | Int (1-100) | admin 设置的并发上限；默认 50 |
| dynamic_enabled | Bool | 是否启用 throttle-自适应 |
| updated_by_user_id | UUID | |
| updated_at | Timestamp | |

运行时 Worker 根据 `dynamic_enabled` 决定：
- True：从 `min(4, deep_read_max)` 起步，按 throttle 率调节，上限 `deep_read_max`
- False：固定 `deep_read_max`

---

## E10. AlertRule

| 字段 | 类型 | 说明 |
|---|---|---|
| rule_id | UUID | 主键 |
| metric | Enum{BEDROCK_ERROR_RATE, JOB_TIMEOUT, TOKEN_BUDGET_EXCEEDED, MEMORY_WRITE_FAILURE, CROSS_TEAM_DENIED} | 监控指标 |
| threshold | Float | 阈值 |
| window_minutes | Int | 时间窗口 |
| sns_topic_arn | ARN | 告警目标 |
| enabled | Bool | |

---

## E11. Novel（仅在 U1 层定义骨架；完整字段在 U2 扩展）

骨架：

| 字段 | 类型 | 说明 |
|---|---|---|
| novel_id | UUID | 主键 |
| team_id | UUID | 租户 |
| owner_user_id | UUID | 上传者 |
| title | String | 书名 |
| source_type | Enum{UPLOAD, PUBLIC_DOMAIN, CRAWL} | 来源 |
| status | Enum{INGESTING, INGESTED, ANALYZING, ANALYZED} | 状态 |
| created_at | Timestamp | |

**删除策略（U1-F7=A 硬删除）**：
- Novel、Team、User 的删除为硬删除：直接 DynamoDB DeleteItem + 关联 S3 对象级联删除
- 不做软删除回收站
- 警告：Admin 删除操作需二次确认 UI + 审计记录（AuditEvent 保留，见 E6）

---

## 实体关系图

```
                  ┌─────────┐
                  │  Team   │◄────┐
                  └────┬────┘     │owner
                       │ 1:N      │
                       ▼          │
                  ┌─────────┐     │
                  │  User   │─────┘
                  └────┬────┘
                       │
             ┌─────────┼─────────┐
             │         │         │
             ▼         ▼         ▼
         ┌──────┐  ┌──────┐  ┌────────┐
         │Novel │  │ Job  │  │ Audit  │
         └──┬───┘  └──────┘  │ Event  │
            │                └────────┘
            ▼
         ┌──────┐
         │ Fact │（通过 MemoryFacade，以 team_id+novel_id 隔离）
         └──────┘

系统配置（单例或版本化，不含 team_id）：
   ModelConfig | ConcurrencyConfig | AlertRule
```

---

## 类型总览（pydantic）

所有实体将在 `packages/shared-types-py/novelgen/types/` 中以 pydantic v2 模型实现。字段命名遵循 snake_case，Enum 使用字符串字面量。

```python
# packages/shared-types-py/novelgen/types/identity.py
class Principal(BaseModel):
    user_id: UUID
    team_id: UUID
    email: EmailStr
    global_role: GlobalRole
    team_role: TeamRole
    jwt_expiry: datetime

# packages/shared-types-py/novelgen/types/job.py
class Job(BaseModel):
    job_id: UUID
    team_id: UUID
    owner_user_id: UUID
    job_type: JobType
    subject_id: UUID
    status: JobStatus  # QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED
    ...
```
