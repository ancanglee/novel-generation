# U5 Business Rules

**Unit**：U5 Critic & Consistency
**阶段**：Functional Design
**日期**：2026-04-28

> **Changelog**：用户 F4=D / F6=C 移除 ModerationAgent。U5 范围为 Critic + Consistency。

---

## R1. CriticAgent（F1=B 复核评审）

### R1.1 触发
订阅 EventBridge `generation.chapter.completed` 事件，路由到 `critic-queue`（U1 预建）。

### R1.2 复核输入
- 本章完整文本（从 S3 读）
- Layer-1 SelfCritique 结果（U4 Chapter 记录的 `self_critique` 字段）
- 最近 5 章的 summary（U4 outline_items 或简短提取）
- 风格向量（从 GEN_CONTEXT 读）

### R1.3 输出结构（F1=B）
CritiqueReport 包含：
- `score` 0-100
- `issues`：**复核所有 Layer-1 问题 + 补充 Layer-2 新问题**
- `layer1_confirmed`：Layer-2 同意的 Layer-1 issue
- `layer1_overridden`：Layer-2 认为 Layer-1 误判的（降级 / 忽略）
- `cross_chapter_concerns`：跨章节 style_drift / character_inconsistency / plot_divergence
- `suggestions`：可执行修改建议

### R1.4 模型
默认 Opus 4.7（admin 可通过 U1 ModelConfig 改）。

### R1.5 成本
每章 ~$0.6（Opus 4.7 + 3-4k input tokens + 1k output tokens）

---

## R2. ConsistencyAgent

### R2.1 触发（F2=D admin 可配）
SSM 参数 `/novelgen/{env}/config/consistency-interval`（默认 **10**）：
- 每生成 N 章由 ChapterAgent 完成时发 `consistency.trigger` 事件
- EventBridge Rule 路由到 `consistency-queue`

### R2.2 扫描范围（F3=B 增量）
- 最近 N 章的完整文本
- MemoryFacade.recall 相关 facts（人物/地点/事件 top_k=30）
- 涉及人物的 CharacterSnapshot（通过 `get_character`）

### R2.3 ConflictItem 分类（6 类）
character_state / location_order / timeline / power_level / faction_affiliation / other

### R2.4 输出落库（F7=A 清单供用户）
- ConsistencyReport 写 DDB `CONSISTENCY#{gid}#{to_chapter:05d}`
- 每 ConflictItem 初始 `user_action=pending`
- UI 让用户选择 `ignore` / `rewrite_requested`
- `rewrite_requested` 时 Api 层启动 ChapterRewrite（U4 已有能力）

### R2.5 模型
默认 Sonnet 4.6

---

## R3. 并行 fan-out 关系

虽然用户移除了 Moderation，Critic 与 Consistency 在触发条件不同：
- Critic：每章触发（chapter.completed）
- Consistency：每 N 章触发（chapter.completed with idx % N == 0）

两者通过独立 EventBridge Rule 分发到各自队列，互不阻塞。

---

## R4. Memory 读取（Consistency 专用）

ConsistencyAgent 调用 U3 MemoryFacade：
- `recall(query="character {name} status in chapter range", top_k=30)`
- `get_character(character_id, at_chapter)` 获取关键角色历史
- `neighbors(node_id, edge_type="visited")` 查地点/角色关系

失败降级：U3 MemoryFacade 分层降级已覆盖（Neptune/OpenSearch 失败 → AgentCore Memory only）。

---

## R5. 重写集成（US-06-04）

用户点击某 ConflictItem 的 "Rewrite Chapter"：
- `POST /api/v1/generations/{gid}/chapters/{n}/rewrite`（U4 路由已实现）
- body 包含 ConflictItem 摘要作为 `instruction` 提示
- U4 worker-generation 接管章节重写
- 重写完成后 Critic 自动再跑一次；用户可再次查看新 Report

---

## R6. Admin 监控（US-08-04 Collab）

U5 输出以下 metric 供 Admin 面板：
- `CriticScore` dimension={Severity=low/medium/high}
- `ConsistencyConflictCount` by conflict_type
- `CriticDurationMs` / `ConsistencyDurationMs`

---

## R7. 失败与降级

| 失败场景 | 处理 |
|---|---|
| Critic LLM 超时 | SFN Retry 3 次；耗尽标 FAILED，Chapter 仍可查看 |
| Consistency Memory 不可用 | 降级扫描：仅文本对比，不做 Memory 约束；输出 warning |
| 用户手动忽略所有 Conflict | ConsistencyReport.dismissed=true，后续章节不再触发同类 warning |

---

## R8. 错误码

| Error | Code | HTTP |
|---|---|---|
| Critic 超时 | `UPSTREAM_CRITIC_TIMEOUT` | 504 |
| Consistency Memory 全部失败 | `UPSTREAM_MEMORY_UNAVAILABLE` | 502 |
| 重复请求同一 report | `CONFLICT_REPORT_EXISTS` | 409 |

---

## R9. 未实现的 Story（由 F4=D/F6=C 决策引起）

- **US-09-01 审核队列**：不实现
- **US-09-02 段落级打回**：不实现
- **ContentModerator Persona** 在 personas.md 保留但无功能入口（可在 U7 阶段决定是否完全移除）

相关 U1 基础设施（`moderation-queue` SQS / `worker-moderation` ECS / EventBridge `chapter.completed→moderation-queue` Rule）保留为 V2 预留。
