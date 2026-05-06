# U4 Business Rules

**Unit**：U4 Generation Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## R1. 模式路由（F1=A）

### R1.1 两套 system prompt
- `Mode.CLEAN_ROOM` → `prompts/clean_room.md`（强调新世界、新角色）
- `Mode.CONTINUATION` → `prompts/continuation.md`（强调接续原作时间线、保持角色连贯）

### R1.2 模式切换
- 创建 Generation 时固定 Mode，**不允许中途切换**
- 切换需新建 Generation

---

## R2. 大纲生成（F2=A 章节级）

### R2.1 OutlineAgent 输入
- novel_id（原作）
- mode
- style_vector
- target_chapter_count / target_words_per_chapter
- U3 分析报告（tags / main characters / main places / factions）

### R2.2 OutlineAgent 输出结构
- `main_plot`（< 500 字）
- `character_table`（6-20 人物，每人 role + arc）
- `world_summary`（< 300 字）
- `items`（章节级大纲，每章 ~100 字 + 涉及人物 + 地点 + plot_tags + target_words）

### R2.3 幂等性
Generation ID + outline version 唯一。重新生成大纲创建新 version（不覆盖历史）。

### R2.4 Outline 存储
- JSON 存 S3：`teams/{tid}/generations/{gid}/outline.v{N}.json`
- 元数据写 DynamoDB：`SK=GEN#{gid}` 的 `outline_s3_key` 指向最新版

---

## R3. 用户大纲编辑（F3=B LLM 校验）

### R3.1 编辑保存
用户通过 `PUT /api/v1/generations/{gid}/outline` 提交修改，`version += 1`，standalone LLM 异步校验。

### R3.2 LLM 校验流程
- 异步调度 `OutlineReviewAgent`（Sonnet 4.6）
- 输入：原始 Outline v(N-1) + 用户修改 Outline vN + 原作风格向量
- 输出：`OutlineRevisionAdvice` 列表（severity=info/warn）
- **不强制阻断**生成，仅在 UI 显示

### R3.3 用户明示关闭校验
Header `X-Skip-Outline-Review: true` 可跳过，适合 admin 快速迭代。

---

## R4. Memory 召回（F4=A 固定 top_k=20 hybrid）

### R4.1 召回时机
每章 `ChapterAgent.generate_stream` 开始前。

### R4.2 召回参数
```python
facts = await memory_facade.recall(
    team_id, novel_id,
    query=f"Chapter {n} context: {outline_item.summary}",
    top_k=20,
)
```

### R4.3 召回内容优先级
将 facts 按相关性排序，前 20 条注入 prompt 的 "Memory Context" 段。

### R4.4 MemoryFacade 降级时的行为
如果 recall 失败（返回空列表 + metric），章节生成继续，但 prompt 中标注"无 Memory 上下文"警告。

---

## R5. 章节流式生成（US-06-01）

### R5.1 输入准备
1. 读 outline_item(chapter_idx)
2. Memory.recall 获取 20 条相关事实
3. 构造 `StyleInjectionBlock`（F7=C）：6 维向量前缀 + Memory 召回的 3 段相似风格片段
4. 获取前一章末尾（最后 500 字）作为衔接上下文

### R5.2 流式输出
- 用 Bedrock `converse_stream` API
- 每个 text_delta 块通过 EventBridge `generation.chapter.streaming` 发出
- 由 ApiService SSE 端点转发到前端

### R5.3 边界
- 单章目标字数 `target_words`；超出 150% 则截断（warning）
- 生成延迟 P95 < 60 秒（NFR-2）
- 首字节 < 3 秒

---

## R6. Cancel 语义（F6=A + AD4 澄清 2=A）

### R6.1 用户触发
`POST /api/v1/jobs/{job_id}/cancel` → 写 `novelgen_jobs` 的 `cancel_requested=true`

### R6.2 Worker 检查
每收到 Bedrock stream token 回调时：
- 从进程内 TTLCache(5s) 读 cancel_requested
- 为 true → 关闭 stream + 发 `generation.cancel_requested` 事件 + 更新 Job status=CANCELED
- 已生成部分保存到 S3，标记 partial

### R6.3 Cancel 幂等
多次调用只写一次（condition: attribute_not_exists 或 `cancel_requested=false`）

---

## R7. Self-Critique（F5=A 独立调用）

### R7.1 触发
章节 `status=GENERATED` 后，异步任务调用 `SelfCritiqueAgent`（Sonnet 4.6）。

### R7.2 输入
- 本章完整文本
- 原作 StyleVector
- Memory 召回的相关事实（20 条）
- outline_item

### R7.3 输出 CritiqueNote
- score 0-100
- issues（low/medium/high）
- suggestions（改进建议）
- dimensions（6 维与目标对比）

### R7.4 Self-Critique 失败
非致命。章节继续进入 CRITIQUED 状态，self_critique=None + warning。

---

## R8. 风格注入（F7=C 前缀 + Memory 相似段）

### R8.1 StyleInjectionBlock 构造
```python
prefix = render_style_prefix(style_vector)  # F7=A 部分
query = f"风格参考: 基调={tone} 节奏={pace} ..."
excerpts = await memory.hybrid_search(team_id, ref_novel_id, query, top_k=3)
block = StyleInjectionBlock(vector_prefix=prefix, reference_excerpts=[h.payload["content_text"] for h in excerpts])
```

### R8.2 注入位置
system prompt 中 `<style_reference>` 块。

### R8.3 多参考小说混合（Q10=C）
若 `reference_novels` 有多本，按 `reference_weights` 加权采样。

---

## R9. 章节串行（F8=A）

### R9.1 严格串行
章节生成任务按 `chapter_idx` 顺序派发到 SQS。上一章 COMPLETED 后才派发下一章。

### R9.2 派发机制
ChapterStateMachine Map state MaxConcurrency=1，或应用层用 DynamoDB condition 确保。

### R9.3 NFR-2 保障
单章 60s + 50 章 = 50 min 总耗时。若超出用户可接受范围，前端允许用户选择"允许分批并行"（V2）。

---

## R10. 重写（US-06-04 打回）

### R10.1 用户点"重写本章"
`POST /api/v1/generations/{gid}/chapters/{n}/rewrite` body=`{instruction: "..."}`

### R10.2 Worker 行为
- 读现有章节作为参考
- 合并 user instruction 到 prompt
- 输出新版本，替换原文件（S3 版本化保留历史）
- rewrite_count += 1

### R10.3 重写次数上限
admin 可配置（默认 5 次）；超过 → 409 `CONFLICT_REWRITE_LIMIT`。

---

## R11. 对接 U5 Critic（Layer-2）与 Moderation

### R11.1 触发
ChapterAgent 完成 Self-Critique 后：
- 发 `generation.chapter.completed` EventBridge
- 由 EventBridge Rule 同时 fan-out 到：
  - `critic-queue` → U5 CriticAgent
  - `moderation-queue` → U5 ModerationAgent

### R11.2 U4 不阻塞等待 U5 结果
Job 在 COMPLETED 后结束。Critic/Moderation 结果异步写入 Chapter 记录。

---

## R12. 全书完成

当所有 chapter status ∈ {APPROVED, COMPLETED} 时：
- Generation.status = COMPLETED
- 发 `generation.completed` 事件
- 可选：触发全书一致性校验（U5 ConsistencyAgent）

---

## R13. 错误码

| 错误 | Code | HTTP |
|---|---|---|
| 大纲未批准 | `CONFLICT_OUTLINE_NOT_APPROVED` | 409 |
| 重写超限 | `CONFLICT_REWRITE_LIMIT` | 409 |
| Memory 不可用（致命）| `UPSTREAM_MEMORY_UNAVAILABLE` | 502 |
| 风格向量无效 | `VALIDATION_STYLE_VECTOR` | 422 |
| 已取消 | `CONFLICT_JOB_CANCELED` | 409 |
