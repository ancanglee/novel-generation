# U1 Business Logic Model

**Unit**：U1 Platform & Infrastructure
**阶段**：Functional Design
**日期**：2026-04-27

---

## 概览

本文描述 U1 层的核心业务流程（technology-agnostic）。每个流程给出触发条件、步骤、副作用、错误分支。

---

## Flow 1. 用户注册与登录

**触发**：用户通过 Cognito Hosted UI 完成认证（Google/GitHub/邮箱）。

**步骤**：
1. Cognito 在 PreSignUp Trigger 阶段调用 Lambda Hook（U1 提供）
2. Hook 检查是否首次注册：
   - 是：生成新的 `team_id`，调用 U1 API 写入 `Team` 记录（owner=user_id），并在 User 的 Cognito custom:team_id 中写入该 team_id
   - 否：跳过
3. Cognito 返回 id_token 给前端
4. 前端把 id_token 交给 NodeBff 换 HttpOnly Cookie
5. NodeBff 调用 ApiService 的 `/api/v1/auth/me`，ApiService 基于 JWT 构造 Principal 并返回用户信息
6. Principal 包含 team_id, global_role, team_role，供后续 API 校验

**副作用**：
- 新用户：DynamoDB 写入 User 与 Team 记录
- 所有用户：更新 last_login_at

**错误分支**：
- Cognito 认证失败 → Hosted UI 返回错误
- PreSignUp Hook 失败 → 注册回滚，用户看到错误
- JWT 验证失败 → 401

---

## Flow 2. Principal 构造与传递（U1-F5=C）

**触发**：任何受保护的 API 请求到达。

**步骤**：
1. ApiService 的 FastAPI 依赖 `verify_principal(authorization: str = Header(...))` 被调用
2. AuthAdapter.verify_jwt() 验证签名与过期
3. 解析 claims，从 Cognito Group 映射 global_role
4. 解析 custom:team_roles JSON，查找 Principal.team_id 的角色 → team_role
5. 构造 `Principal` 对象返回

**传递**：
- Principal 作为**显式参数**从 router → service → adapter 一路透传（U1-F5=C）
- 不使用 ContextVar；代码虽然繁琐但可测试性与可审查性最好

**示例**（伪代码）：
```python
@router.get("/novels")
async def list_novels(principal: Principal = Depends(verify_principal)):
    return await novel_service.list(principal)

class NovelService:
    async def list(self, principal: Principal) -> list[NovelSummary]:
        return await self.repo.list(principal)  # 显式传递

class NovelRepository:
    async def list(self, principal: Principal) -> list[NovelSummary]:
        # 使用 principal.team_id 构造查询
        return await self.ddb.query(
            pk=f"TEAM#{principal.team_id}#NOVEL",
        )
```

---

## Flow 3. 多租户守卫

**触发**：API 请求或 Adapter 层的任何数据访问。

**步骤**（API 层）：
1. Router 函数签名中声明 `@require_team_access`
2. 装饰器检查 request.path_params / body 中的 `team_id` 字段
3. 如果不等于 `Principal.team_id` 且 Principal 非 ADMIN → 抛 `ForbiddenCrossTeamAccess`
4. FastAPI exception handler 转为 403 响应
5. ObservabilityAdapter 发射 `cross_team_denied` 指标（R1.4）

**步骤**（StorageAdapter 层）：
1. 方法接收 `principal: Principal` 参数
2. 使用 `principal.team_id` 构造 key/PK/过滤器
3. Runtime 断言：传入的 key/PK 前缀与 principal.team_id 一致；否则抛 `TeamScopeViolation`

**为什么双层守卫**：防御深度。API 层防错；Adapter 层防低层代码漏校验。

---

## Flow 4. Job 生命周期

**触发**：前端发起长时任务（例如 `POST /api/v1/analyses`）。

**步骤**：
1. ApiService 创建 Job 记录（status=QUEUED, team_id, owner_user_id, job_type, subject_id）
2. 调用 Step Functions `StartExecution`（execution name = job_id 保证幂等）
3. 返回 `{job_id, status: QUEUED}` 给前端
4. Step Functions 派发消息到 SQS
5. Worker 消费消息：
   a. 更新 Job.status = RUNNING, started_at = now
   b. 执行业务逻辑（理解/生成/Critic/一致性/审核）
   c. 过程中周期性更新 Job.progress
   d. 每次 LLM 调用后累加 token_usage
6. 完成：更新 Job.status = SUCCEEDED, ended_at = now, result_ref = ...
7. 发 EventBridge 事件 `job.{type}.completed`
8. ApiService 的 SSE 端点订阅并推送给前端

**取消分支**：
1. 前端调 `POST /api/v1/jobs/{id}/cancel`（R2.2）
2. ApiService 更新 Job.cancel_requested = true
3. Worker 在每次 Bedrock stream 回调时检查该标志
4. 为真则关闭 stream，更新 Job.status = CANCELED, ended_at = now
5. 已消耗 token 记账保留；已流出文本保存到 S3（状态标记为 partial）

**失败分支**（见 R2.3）：
- Step Functions Task 重试 3 次后仍失败 → Catch 节点 → 更新 Job.status = FAILED
- 记录 error_code, error_message, request_id

---

## Flow 5. 审计写入（U1-F4=A）

**触发**：Admin 执行 R4.1 列表中的管理操作。

**步骤**：
1. Admin 路由（`/api/v1/admin/*`）有统一的 audit decorator
2. decorator 在路由函数返回后（不是异常路径）同步写入 AuditEvent
3. 写入内容：actor_user_id, actor_team_id, action, target_type, target_id, before (pre-fetch), after (post-result), request_id
4. 如果审计写入失败 → 仅记录 Error Log，不影响业务调用（避免 audit 故障拖垮业务）

**before/after**：
- 对 Update 类操作：路由在执行前先 `ddb.get(key)` 获取 before；操作后把新值作为 after
- 对 Create：before=null
- 对 Delete：after=null

---

## Flow 6. ModelConfig 热加载

**触发**：Admin 更新任务阶段-模型映射。

**步骤**：
1. Admin 调 `PUT /api/v1/admin/models` 提交新 mapping
2. ApiService 读取当前 ModelConfig，递增 version，写入新记录
3. 写入审计 MODEL_CONFIG_UPDATE
4. 返回新版本号
5. Worker 每 30 秒轮询 DynamoDB 最新 version；变更则拉取并替换内存中的 config
6. 正在执行的 Job 冻结其起始 version（存在 Job.payload.model_config_version）；不受影响

---

## Flow 7. ConcurrencyConfig 动态调节（AD6=F）

**触发**：Analysis Worker 处理细读批次。

**步骤**：
1. Job 启动时读 ConcurrencyConfig：
   - dynamic_enabled=false → 使用固定 deep_read_max
   - dynamic_enabled=true → 初始化 current = min(4, deep_read_max)
2. Worker 按批次处理章节（每批 10 个）
3. 每批完成后统计 throttle 率（Bedrock ThrottlingException 计数 / 本批 LLM 调用数）
4. 按 R8.2 规则调节 current
5. current 写入共享 ConcurrencyState（Redis/DynamoDB）
6. 下一批拉取最新 current

**跨 Worker 一致性**：同一 Job 的多 Worker 实例共享 ConcurrencyState；更新用 CAS 或 DynamoDB conditional update。

---

## Flow 8. Fact 幂等写入（U1-F6=B）

**触发**：UnderstandingAgent 或 GenerationAgent 抽取事实后调用 `MemoryFacade.remember(facts)`。

**步骤**：
1. 对每个 Fact，MemoryFacade 计算 fact_key（按 R5.1 规则）
2. 写入 AgentCore Memory / DynamoDB Fact 表：
   - 使用 fact_key 作为主键
   - upsert 语义（覆盖 content，保留创建时间）
3. 如果 fact_type = CHARACTER_SNAPSHOT 或 MAP_PLACE，同时写入 Neptune（nodes + edges）
4. 如果 content 含文本，计算 embedding 并写入 OpenSearch（带 fact_key 作为外部引用）
5. 返回写入统计

**冲突处理**：
- fact_key 归一化后相同视为同一事实 → upsert
- fact_key 归一化前相同但涉及不同 novel_id → fact_key 前缀已含 team_id/novel_id，天然隔离
- 异常情况（例如 race condition）→ 写入失败则重试 3 次，仍失败则抛出，由 Worker 重试 Step Functions Task

---

## Flow 9. 硬删除 Novel（U1-F7=A）

**触发**：Owner 或 Admin 触发 `DELETE /api/v1/novels/{id}`。

**步骤**：
1. 路由验证 Principal（owner/admin）
2. 二次确认（UI 层；API 层可要求 body 带 `confirm` 字符串）
3. 调用 NovelService.delete(principal, novel_id)：
   a. DynamoDB：删除 Novel 元数据 + 关联 Chapter、Generation、Fact 记录
   b. S3：batch delete `teams/{team_id}/novels/{novel_id}/*`
   c. Neptune：`g.V().has('novel_id', :nid).has('team_id', :tid).drop()`
   d. OpenSearch：`delete_by_query {term: {novel_id: :nid}}`
4. 如果任何一步失败 → 整体状态标记为 PARTIALLY_DELETED，后台作业周期重试
5. Admin 操作写审计

**为什么不做软删除**：用户明确选择 U1-F7=A，接受不可恢复。UI 必须给出醒目的警告提示。

---

## Flow 10. 全链路可观测（US-NFR-05）

**触发**：任何请求/任务执行。

**步骤**：
1. NodeBff 为每个请求注入 `X-Request-Id`
2. ApiService 在 middleware 中启动 X-Ray segment，设置 request_id 作为 annotation
3. 每次 AWS SDK 调用 + Bedrock 调用由 X-Ray 自动采样
4. ObservabilityAdapter.log 发射结构化日志（JSON），字段含 request_id, team_id, job_id, agent_id
5. ObservabilityAdapter.metric 发射 EMF 格式指标到 CloudWatch
6. AgentCore Observability 采集 Agent 调用的 trace
7. Admin 监控面板（U7）聚合上述数据并展示 waterfall 图

**request_id 贯穿**：贯穿前端 → BFF → API → Step Functions → Worker → AgentCore，全链路可关联。

---

## Flow 11. Team 切换（U1-F1=A 1:N + 重新登录）

**触发**：用户希望切换到另一 Team（例如通过管理员邀请）。

**步骤**：
1. Admin 调用 `PUT /api/v1/admin/users/{user_id}/team` 将用户迁移到新 Team
2. 更新 DynamoDB User.team_id
3. 更新 Cognito custom:team_id 属性
4. 写审计 MEMBER_REMOVE + MEMBER_ADD
5. 通知用户（邮件 / 应用内通知）
6. 用户必须重新登录以刷新 JWT 中的 team_id 与 team_roles claims

**注意**：由于 U1-F1=A，单个用户在任意时刻只属于一个 Team。JWT 中携带该 team_id，前端仪表盘数据直接按 Principal.team_id 过滤，无需前端切换逻辑。

---

## Flow 12. 请求错误处理与响应

**触发**：任何异常冒出。

**步骤**：
1. FastAPI Global exception handler 捕获
2. 按类型分派：
   - `ValidationError` (pydantic) → 422 + `VALIDATION_*`
   - `ForbiddenCrossTeamAccess` → 403 + `FORBIDDEN_CROSS_TEAM_ACCESS`
   - `TeamScopeViolation` (Adapter) → 403 + `FORBIDDEN_SCOPE_VIOLATION`
   - `InvalidJobTransition` → 409 + `CONFLICT_JOB_TRANSITION`
   - `BedrockThrottlingException` → 429 + `RATE_LIMIT_UPSTREAM`
   - `TimeoutError` → 504 + `UPSTREAM_TIMEOUT`
   - `RuntimeError` 其他 → 500 + `INTERNAL_UNEXPECTED`
3. 所有错误响应包含 request_id（R10.2）
4. 5xx 错误同时发射 metric `http_5xx_total`

---

## 业务流程编号索引

- Flow 1: 用户注册与登录
- Flow 2: Principal 构造与传递
- Flow 3: 多租户守卫
- Flow 4: Job 生命周期
- Flow 5: 审计写入
- Flow 6: ModelConfig 热加载
- Flow 7: ConcurrencyConfig 动态调节
- Flow 8: Fact 幂等写入
- Flow 9: 硬删除 Novel
- Flow 10: 全链路可观测
- Flow 11: Team 切换
- Flow 12: 请求错误处理
