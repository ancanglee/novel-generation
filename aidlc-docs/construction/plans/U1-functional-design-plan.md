# U1 Platform & Infrastructure — 功能设计计划

**Unit**：U1 Platform & Infrastructure
**阶段**：Functional Design
**日期**：2026-04-27

---

## Unit Context Summary

U1 提供所有其他 Unit 的基础设施与共享库，是 新建项目 项目的底座。本阶段聚焦于**业务逻辑与领域模型**（非基础设施资源，基础设施在 Infrastructure Design 阶段处理）。

U1 的"业务"主要体现在：
- **多租户身份与授权领域**（team、user、role、Principal）
- **任务（Job）领域**（长时任务状态机）
- **审计（Audit）领域**（管理操作留痕）
- **系统配置领域**（模型配置、并发配置、告警规则）
- **共享 Adapter 的领域抽象**（StorageAdapter 的 Repository 接口、MemoryFacade 的事实模型、ObservabilityAdapter 的指标模型）

对应 Stories：**US-01-04**（多租户强隔离）、**US-NFR-03**（跨租户反例）、**US-NFR-05**（全链路可观测），协作 US-00-02 / US-01-02 / US-01-03 / US-08-* / US-NFR-04。

---

## Part 1 — 功能设计澄清问题

### Question U1-F1 — Team 与 User 的关系模型
Q21=B 选择了团队级隔离。需要明确模型：

A) **1:N**（一个 User 只属于一个 Team）：注册时自动创建个人 Team；可邀请切换 Team；切换需注销并重新登录
B) **M:N**（一个 User 可同时属于多个 Team）：用户可在 UI 中下拉切换当前 Team（不需重登录）；每个 API 请求携带 activeTeamId ✓
C) **层级 Team**（Team 下可有 SubTeam）：更复杂
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-F2 — Role（角色）模型
用户的权限角色如何表达？

A) **Cognito Group + 3 固定角色**：`regular_user`, `admin`, `content_moderator`（Cognito native）
B) **Cognito Group + 自定义属性**：Group 承载跨 Team 的全局角色（`admin`），`custom:team_roles` JSON 承载 Team 级角色（`{teamId: "owner"/"member"/"moderator"}`） ✓
C) **外部 RBAC**（Cedar / OPA）
D) Other (please describe after [回答]： tag below)

[回答]： B. 

### Question U1-F3 — Job（长时任务）的状态机
分析/大纲/章节/一致性/审核等长时任务共用一套状态机？

A) **统一状态机**：`QUEUED → RUNNING → SUCCEEDED | FAILED | CANCELED`，所有任务类型共享 ✓
B) **按任务类型独立状态机**（例如 ChapterJob 有 `OUTLINE_READY` 等特定状态）
C) **两层状态机**：外层统一（A），内层任务类型特定子状态（如 chapter 的 generating/self_critique/done）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-F4 — 审计（Audit）事件范围
哪些操作必须记录审计？

A) **仅 Admin 管理操作**（用户/团队 CRUD、模型配置变更、模板管理、告警配置）
B) **A + 所有跨 team 数据访问尝试**（包括被拒的 403）
C) **A + B + 生成/导出完成事件**（法律合规要求）
D) **A + B + 审核员的打回操作**
E) B + C + D（综合）✓
F) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-F5 — 身份上下文（Principal）如何在代码中传递
Python 代码中 `Principal` 对象如何在请求上下文中可用？

A) **FastAPI Depends + ContextVar**：路由依赖注入，ContextVar 在下游（如 StorageAdapter）校验 ✓
B) **全局 threadlocal / asyncio contextvar**：隐式传递
C) **显式参数**：每个函数签名都带 Principal 参数
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question U1-F6 — Fact（事实）的幂等键
MemoryFacade 写入事实时如何保证幂等（避免重复 Memory 污染）？

A) **基于事实内容哈希**：hash(team_id + novel_id + fact_type + normalized_content) 作为主键
B) **基于业务键**：例如人物事实的键是 `character:{name}:chapter:{n}`
C) **A + B**：hash 做去重，业务键做快速检索 ✓
D) 不做幂等（每次覆盖写入）
E) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-F7 — 软删除 vs 硬删除
删除小说、Team、User 时：

A) **硬删除**（直接 DynamoDB DeleteItem + S3 DeleteObject）
B) **软删除**（status=DELETED，N 天后后台作业硬删除） ✓
C) **用户级硬删除 + Admin 级软删除**
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-F8 — 多租户违规的响应策略
如果检测到跨 team 访问尝试（不论是恶意还是 bug）：

A) **返回 403 + 记 audit**（静默） ✓
B) **返回 403 + 记 audit + 触发 CloudWatch 告警**（三次以上触发 SNS）
C) **返回 403 + 记 audit + 告警 + 冻结账户**（最严格）
D) Other (please describe after [回答]： tag below)

[回答]： A

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U1F-1: 根据答案确定领域模型
- [x] Step U1F-2: 生成 `domain-entities.md`（User/Team/Role/Principal/Job/AuditEvent/Fact/ModelConfig/ConcurrencyConfig/AlertRule）
- [x] Step U1F-3: 生成 `business-rules.md`（多租户守卫规则、Job 状态转换规则、审计触发规则、硬删除规则、幂等规则）
- [x] Step U1F-4: 生成 `business-logic-model.md`（关键业务流程：登录态建立、Team 切换、Job 生命周期、审计写入、Principal 注入、多租户守卫、事实幂等写入）
- [x] Step U1F-5: 更新 aidlc-state.md

---

## Part 3 — 我的推荐

- U1-F1 = **B**（M:N + activeTeamId）：符合 Q21=B 的团队协作，也让切换体验顺畅
- U1-F2 = **B**（Cognito Group + custom:team_roles JSON）
- U1-F3 = **C**（两层状态机）：外层通用便于统一查询，内层类型特定便于精确 UI
- U1-F4 = **E**（综合）：审计完整性优先
- U1-F5 = **A**（Depends + ContextVar）：FastAPI 社区最佳实践
- U1-F6 = **C**（hash + 业务键）
- U1-F7 = **B**（软删除 + 后台硬删除）：可恢复 + 合规留痕
- U1-F8 = **B**（403 + audit + 告警）：平衡可用性与安全
