# U1 Business Rules

**Unit**：U1 Platform & Infrastructure
**阶段**：Functional Design
**日期**：2026-04-27

---

## R1. 多租户隔离规则（硬性）

### R1.1 Principal 注入
- 所有受保护的 API 路由（`/api/v1/*` 除健康检查外）必须通过 `verify_principal` 依赖解析出 Principal
- Principal 构造失败 → 401
- **U1-F5=C**：Principal 作为**显式参数**传递到 Service、Adapter 层方法（不使用 ContextVar）

### R1.2 path/body/query 中的 team_id 必须与 Principal.team_id 一致
- API 层守卫：任何 path 或 body 中出现的 `team_id` 字段与 Principal.team_id 不匹配 → 403
- 例外：`global_role=ADMIN` 的用户可以访问其他 team_id（但每次跨访问都会写审计，仅 Admin 操作入审计）
- 例外：`global_role=MODERATOR` 可以只读访问其被分配的 team（范围配置在另一个关联表）

### R1.3 StorageAdapter 强制前缀
- S3 key 必须以 `teams/{team_id}/` 开头，否则运行时 `TeamScopeViolation` 异常
- DynamoDB PK 必须以 `TEAM#{team_id}#` 开头
- Neptune 节点必须带 property `team_id=:tid`
- OpenSearch 文档必须带字段 `team_id`，查询时强制 filter

### R1.4 跨 team 访问响应（U1-F8=A）
- 检测到跨 team 访问尝试（API 层或 StorageAdapter 层）→ **返回 403 + 日志记录**，不触发告警、不冻结账户
- 静默响应：不向客户端暴露资源是否存在（避免 timing oracle）
- 通过 `ObservabilityAdapter.metric("cross_team_denied", 1)` 发射指标，admin 可自行在告警规则中配置阈值

---

## R2. Job 生命周期规则（U1-F3=A 统一状态机）

### R2.1 允许的状态转换
```
QUEUED   → RUNNING           : Worker 开始处理
QUEUED   → CANCELED          : 用户在 RUNNING 前取消
RUNNING  → SUCCEEDED         : 正常完成
RUNNING  → FAILED            : 错误且重试耗尽
RUNNING  → CANCELED          : 用户取消；Worker 检测到 cancel_requested=true
```
其他转换（例如 SUCCEEDED → RUNNING）一律拒绝并抛 `InvalidJobTransition`。

### R2.2 取消语义
- `POST /api/v1/jobs/{id}/cancel` 只更新 `cancel_requested=true`（幂等）
- 实际终结由 Worker 负责：每次 Bedrock stream 回调检查该标志，为真则终止流 + 状态转为 CANCELED
- 已消耗的 token 仍记账（token_usage 字段）
- 已流出的章节文本保留在 S3，状态标记为部分生成

### R2.3 失败重试
- Step Functions 层面：每个 Task 最多 3 次重试，指数退避（1s, 4s, 16s）
- 重试耗尽后 Job → FAILED；保留 error_code + error_message
- Job FAILED 后不可恢复（需重新发起新 Job）

### R2.4 Job 归属检查
- `GET /api/v1/jobs/{id}` 与 `POST /api/v1/jobs/{id}/cancel`：Principal.team_id 必须等于 Job.team_id；不满足返回 403
- Admin 例外

---

## R3. 认证与授权规则

### R3.1 JWT 验证
- AuthAdapter 每次请求验证 Cognito JWT 签名（JWKs 缓存 15 分钟）
- 过期 token → 401
- 令牌签名不合法 → 401

### R3.2 全局角色映射
- Cognito Group `admin` → `global_role = ADMIN`
- Cognito Group `content_moderator` → `global_role = MODERATOR`
- 默认 → `global_role = REGULAR`

### R3.3 Team 角色解析
- 读取 Cognito `custom:team_roles` 自定义属性（JSON）
- 根据 Principal.team_id 查找匹配项；找不到则 `team_role = MEMBER` 默认值
- 注册新用户时自动创建 Team 并设 `team_role = OWNER`

### R3.4 角色门禁装饰器
- `@require_role("admin")` 要求 global_role == ADMIN；否则 403
- `@require_team_role("owner")` 要求 Principal.team_role == OWNER；否则 403
- `@require_team_access` 要求 path/body 中 team_id 与 Principal.team_id 一致（见 R1.2）

---

## R4. 审计规则（U1-F4=A 仅 Admin 管理操作）

### R4.1 触发写入审计的操作
仅以下 Admin API 操作写入 `AuditEvent`：
- 用户 CRUD（USER_CREATE / USER_DISABLE）
- 团队 CRUD（TEAM_CREATE / TEAM_DISABLE）
- 成员 CRUD（MEMBER_ADD / MEMBER_REMOVE）
- ModelConfig 更新（MODEL_CONFIG_UPDATE）
- ConcurrencyConfig 更新（CONCURRENCY_UPDATE）
- AnalysisSchema upsert（SCHEMA_UPSERT）
- 类型标签合并（TAG_MERGE）
- AlertRule upsert（ALERT_UPSERT）

### R4.2 不触发审计的操作
- 普通用户的数据访问（Novel 列表、分析查看、生成配置）
- 生成/导出的完成事件（不进入审计；仅 Job 记录）
- 审核员打回操作（不进入审计；仅 Review 记录）
- 跨 team 访问被拒绝（不入审计；仅 metric，见 R1.4）

### R4.3 审计不可变性
- AuditEvent 一经写入，不可更新、不可删除
- DynamoDB 表开启 PITR；任何 UpdateItem/DeleteItem 到 audit 表被 IAM 策略拒绝

---

## R5. Fact 幂等规则（U1-F6=B 业务键）

### R5.1 fact_key 规范
- 所有事实写入 MemoryFacade 时必须提供 fact_key
- fact_key 由业务维度组合而成（见 domain-entities.md E7 规则）
- 相同 fact_key 的写入视为同一事实，采用 **upsert**（覆盖 content）

### R5.2 fact_key 不可变
- 一旦写入后 fact_key 不可更改（即使 content 变化也保留同 key）
- 如果发现写入 key 与现有冲突（同 key 不同 novel 等）→ 抛 `FactKeyCollision`

### R5.3 命名归一化
- 人物、地点名字写入前经过归一化（去除空格、繁简统一、别名合并）
- 归一化算法在 MemoryFacade 内实现，支持后续演进

---

## R6. 删除规则（U1-F7=A 硬删除）

### R6.1 User 删除
- 用户自己请求删除 → 删除 Cognito User + DynamoDB User 项 + 级联删除该用户拥有的 Novel 与 Job
- 级联：其 team_id 下的所有 S3 对象（前缀匹配）
- 如果该 User 是所属 Team 的唯一 owner，必须先转移所有权或一起删除 Team

### R6.2 Team 删除（仅 Admin）
- Admin 操作 `DELETE /admin/teams/{id}`
- 级联删除所有 User、Novel、Job、Fact、向量索引、图数据
- **二次确认**：API 要求 body 中带 `confirm: "permanent-delete-{team_id}"` 字符串
- 审计记录 TEAM_DISABLE 或 TEAM_DELETE（action 扩展）

### R6.3 Novel 删除
- Owner 或 Admin 触发
- 级联：S3 raw + generations 前缀、DynamoDB 元数据、Fact（按 novel_id 清理）、Neptune 子图、OpenSearch 过滤删除

### R6.4 不提供"垃圾箱"功能
- 硬删除不可恢复；UI 必须明确提示

---

## R7. ModelConfig 与热加载规则

### R7.1 版本号
- 每次 ModelConfig 更新递增 `version`
- Worker 每 30 秒轮询当前 version；变更时热替换
- 正在执行的任务冻结其起始时的 version（记录在 Job.payload）

### R7.2 回滚
- Admin 可通过 `POST /admin/models/rollback?to_version=N` 回滚到旧版本（设 version=N+1 等于旧内容）
- 回滚动作也入审计

---

## R8. ConcurrencyConfig 动态自适应规则（AD6=F）

### R8.1 起步值
- 新 Analysis Job 启动时 current = min(4, deep_read_max)

### R8.2 调节逻辑
每 batch（例如每 10 章）结束：
```
throttle_rate = throttle_errors / total_calls_in_batch
if throttle_rate < 0.01:
    current = min(current + 2, deep_read_max)
elif throttle_rate < 0.05:
    keep
else:
    current = max(1, current // 2)
```

### R8.3 共享状态
- 当前 concurrency 值保存在 Redis（DAX 或 ElastiCache）/ DynamoDB `ConcurrencyState` 表中，key=`job_id`
- 单 Job 跨 Worker 共享；Job 结束后清理

### R8.4 dynamic_enabled=false
- 直接用固定 deep_read_max，不动态调节

---

## R9. Alert 规则

### R9.1 默认 Alert 列表
平台启动时预置以下 AlertRule（admin 可修改）：

| metric | threshold | window |
|---|---|---|
| BEDROCK_ERROR_RATE | 2% | 5 min |
| JOB_TIMEOUT | 1 job/5min | 5 min |
| TOKEN_BUDGET_EXCEEDED | 1 job/5min | 5 min |
| MEMORY_WRITE_FAILURE | 3 errors/5min | 5 min |
| CROSS_TEAM_DENIED | 10 attempts/5min | 5 min |

### R9.2 告警传递
- CloudWatch Alarm → SNS Topic → Email（admin 订阅）

---

## R10. 输入验证与错误响应

### R10.1 基础验证
- 所有 pydantic 模型在 FastAPI 入口处做 schema 校验（422 on failure）
- 业务规则校验在 service 层（抛自定义异常）

### R10.2 统一错误响应格式
```json
{
  "error": {
    "code": "CROSS_TEAM_ACCESS_DENIED",
    "message": "user-facing safe message",
    "request_id": "uuid"
  }
}
```

### R10.3 错误码约定
- `AUTH_*`：认证相关（401）
- `FORBIDDEN_*`：授权相关（403）
- `NOT_FOUND_*`：资源不存在（404）
- `VALIDATION_*`：输入校验（422）
- `CONFLICT_*`：状态冲突（409）
- `RATE_LIMIT_*`：限流（429）
- `UPSTREAM_*`：下游依赖错误（502/504）
- `INTERNAL_*`：内部错误（500）

---

## R11. 幂等性约定

### R11.1 写操作的幂等键
- `POST /api/v1/novels/upload`：基于 `Idempotency-Key` header；重复 key 返回先前结果
- `POST /api/v1/jobs/{id}/cancel`：天然幂等（多次调用结果相同）
- ModelConfig 更新：基于 version 的乐观锁（If-Match header）

### R11.2 Step Functions execution
- 每个 execution 使用唯一的 name（= job_id），避免重复执行

---

## R12. 回溯追溯

### R12.1 request_id
- 每个 HTTP 请求由 NodeBff 注入 X-Request-Id（UUID）；如客户端自带则透传
- 贯穿 BFF → ApiService → Worker → AgentCore；在所有日志与 audit 中记录
- X-Ray 的 trace_id 与 request_id 关联（parallel header）
