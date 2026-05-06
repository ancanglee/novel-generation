# U5 Business Logic Model

**Unit**：U5 Critic & Consistency
**阶段**：Functional Design
**日期**：2026-04-28

---

## Flow 1. Critic Agent（每章触发）

**触发**：U4 ChapterAgent 完成章节 → EventBridge `generation.chapter.completed`

1. EventBridge Rule `chapter-completed-to-critic` → `critic-queue`
2. worker-critic 消费：
   a. 读章节文本（S3）
   b. 读 Layer-1 SelfCritique（DDB GEN_CHAPTER 记录）
   c. 读最近 5 章 summary（outline_items 或 DDB）
   d. 读 GEN_CONTEXT 中的 style_vector
3. 调用 CriticAgent（Opus 4.7, Tool Use schema）
   - Input: 本章文本 + Layer-1 结果 + 历史 summary + style_vector
   - Output: CritiqueReport（含 layer1_confirmed / layer1_overridden / cross_chapter_concerns）
4. 写 DDB `CRITIQUE#{gid}#{idx:05d}`
5. 更新 Chapter 记录：`critique_report_ref` 指向上述 SK
6. 发 `critic.report_ready` EventBridge → SSE → 前端

**前端展示**：Critic Panel 分两栏：
- Layer-1 + Layer-2 合并后的 issue 列表（layer1_overridden 的高亮为"已被复核降级"）
- Cross-Chapter Concerns 独立区

---

## Flow 2. Consistency Agent（每 N 章触发）

**触发**：U4 ChapterAgent 完成章节，检查 `chapter_idx % N == 0`（N 从 SSM 读）时发 `consistency.trigger` 事件

1. EventBridge Rule `consistency-trigger-to-queue` → `consistency-queue`
2. worker-consistency 消费：
   a. 计算扫描范围（scan_from = last_scan_to + 1, scan_to = current_chapter）
   b. 读最近 N 章文本（S3）
   c. MemoryFacade.recall 相关 facts（top_k=30）
   d. 对涉及的主要人物调 `get_character(at_chapter=scan_to)`
3. 调用 ConsistencyAgent（Sonnet 4.6 + Tool Use）
   - Input: chapters + memory_facts + character_snapshots
   - Output: ConsistencyReport（含 ConflictItem 列表，user_action=pending）
4. 写 DDB `CONSISTENCY#{gid}#{scan_to:05d}`
5. 发 `consistency.report_ready` EventBridge → SSE → 前端
6. 前端在生成页显示"一致性报告待审阅"badge

---

## Flow 3. 用户处理 Conflict

**触发**：用户在 UI 查看 ConsistencyReport，对某 ConflictItem 选 "Rewrite"

1. Api 更新 ConflictItem.user_action=`rewrite_requested`
2. Api 调用 U4 `POST /generations/{gid}/chapters/{n}/rewrite`
   - instruction = ConflictItem.suggestion + 引用矛盾证据
3. U4 worker-generation 接管重写（保留 S3 历史版本，rewrite_count++）
4. 新章节生成完成 → 再次触发 Critic（Flow 1）
5. 用户可再次查看新 Report + 决定是否接受

---

## Flow 4. 用户忽略 Conflict

1. 用户选 "Ignore"
2. Api 更新 ConflictItem.user_action=`ignored`
3. 后续 Consistency 扫描时跳过此 ConflictItem 类型（若 severity=low）
4. `severity=high` 的 Conflict 即使 ignored 也保留在 Report 中用于审计

---

## Flow 5. Admin 监控

ObservabilityStack 聚合以下 metric 到 Admin UI：
- Critic 平均分数
- ConflictItem 按 conflict_type 分布
- Critic / Consistency 平均耗时

每日预聚合 Lambda（U1 已有 `daily-cost-aggregator`）可扩展聚合 U5 质量指标。

---

## Flow 6. Critic 失败降级

1. Bedrock ThrottlingException → SFN Retry 3 次
2. 仍失败 → 写一份 minimal CritiqueReport（score=0 + single issue "critic_failed"）
3. Chapter 状态仍为 GENERATED（用户可手动触发再跑 Critic）

---

## Flow 7. Consistency Memory 不可用降级

1. MemoryFacade.recall 返回空 → warning
2. Agent 仅做文本对比（前后 N 章内容 diff）
3. Report 标注 `memory_unavailable=true`

---

## 与其他 Unit 的接口摘要

| 方向 | 接口 |
|---|---|
| 消费 U4 | EventBridge `generation.chapter.completed` 事件 |
| 消费 U3 | MemoryFacade.recall / get_character / neighbors |
| 向 U6 | EventBridge `critic.report_ready` / `consistency.report_ready` → ApiService SSE（复用 U4 SSE relay）|
| 向 U7 | Admin 读 U5 metric 聚合 |

---

## 未实现流程（由 F4=D/F6=C 移除）

- ~~Flow 8 Moderation 触发~~
- ~~Flow 9 Moderator 段落级审核~~
