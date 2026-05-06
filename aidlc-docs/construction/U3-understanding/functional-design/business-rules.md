# U3 Business Rules

**Unit**：U3 Understanding Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## ✅ Changelog v1.1

用户将 F4 从 C 改为 A（粗读初稿 + 细读增量快照，不重建 Profile），将 F7 从 B 改为 A（每章单次 LLM 调用输出全部抽取）。

影响：
- LLM 调用量从 ~1800 降至 ~300（6 倍缩减）
- 预计 100 万字分析时间 ~8-12 min，**满足 NFR-1 (< 15 min)** ✅
- R4 改为"粗读初稿 + 细读增量快照"
- R7 改为"每章单次复合调用 + JSON schema 约束"

---

## R1. Supervisor Agent 编排（F1=B）

### R1.1 Supervisor 职责
- 读取 SupervisorContext，决定下一步调用哪个 sub-agent
- 最多 50 步决策防死循环
- 每一步都要发射 `agent_span_duration_ms` metric + 写 AgentCore Observability trace

### R1.2 可用 sub-agent 工具清单（通过 Strands `@tool` 注册）
- `sample_chapters(novel_id, goal)` → RoughReadSubAgent
- `classify_tags(samples)` → ClassificationSubAgent
- `extract_characters_global(samples)` → CharacterSubAgent (粗读产出 Profile 初稿, F4=A)
- `extract_chapter_all(chapter_idx)` → DeepReadSubAgent (F7=A 单次复合调用，返回 character_updates/map_updates/events/facts)
- `extract_map_global(samples)` → MapSubAgent (粗读主要地点/势力初稿)
- `analyze_style(samples)` → StyleSubAgent
- `rewrite_character_profile(character_id)` → 罕见情况 Profile 重写（R4.4）
- `merge_character_aliases(primary_id, alias_id)` → 别名合并
- `write_memory(facts, nodes, edges)` → MemoryFacade
- `finalize_report()` → 收尾

### R1.3 推荐决策路径（Supervisor 自由决定但通常遵循）
```
1. sample_chapters (F2=C LLM 自适应选 8-15 章)
2. 并行: classify_tags, extract_characters_global, extract_map_global, analyze_style
3. 对每个细读章节:
     extract_chapter_all (F7=A 单次复合调用)
4. write_memory (批量 flush)
5. finalize_report
```

### R1.4 循环保护
- Supervisor 决策数上限 50
- 同一 (agent, chapter_idx) 重复调用 ≥ 2 次 → 警告并跳过
- 未在 15 分钟内收敛 → job FAILED

---

## R2. RoughRead（粗读，F2=C LLM 自适应）

### R2.1 抽样算法
1. 读取 novel 目录（title 列表，不读正文）
2. 调用 Haiku 4.5：prompt 包含完整目录 + 全书字数 + 章节数
3. Haiku 返回 8-15 个章节编号 + 选择理由
4. 服务端强制补充：首 2 章 + 末 2 章（即使 LLM 未选）
5. 读入被选章节的正文

### R2.2 抽样数量约束
- 最少 8 章，最多 15 章
- 总字数不超过 60,000 字（Haiku context 约束）
- 超限时按 importance 分数截断

---

## R3. 类型鉴别（F3=A 多标签 + 置信度）

### R3.1 输出约束
- 最多 5 个标签
- 每个标签 confidence ∈ [0, 1]
- 至少返回 1 个 > 0.5 的主标签

### R3.2 Admin 标签校准流程（见 US-08-03）
- 新出现的标签进入"待审核队列"
- Admin 可合并（"修真" → "修仙"）
- 合并映射保存到 `novelgen_config` 表

---

## R4. 人物抽取（F4=A 粗读初稿 + 细读增量）

### R4.1 粗读产出 Profile 初稿
粗读阶段对 12 章样本一次性调用 `extract_characters_global`：
1. LLM 从样本章节中识别主要人物
2. 产出每个人物的 Profile 初稿（性格/外貌/关键行为/重要性）
3. 写入 `CHARACTER#{novel_id}#{character_id}`

### R4.2 细读只写增量 snapshot（不重建 Profile）
每一章 DeepRead 产出 CharacterUpdate 时：
1. **只记录状态变化**（location / power_level / mood / alive）作为新的 CharacterSnapshot
2. 追加写入 `CHAR_SNAP#{...}#{chapter:05d}`
3. **Profile 本身不重写**，除非满足 R4.4 重大变化触发条件

### R4.3 归一化与去重
- `character_id = normalize(display_name)`（NFKC + 小写 + 去空格）
- 别名映射表（每 novel 独立）：`{alias: primary_id}`
- 新别名出现 → Supervisor 可调用 `merge_character_aliases(primary, alias)` 工具

### R4.4 Profile 重写触发条件（罕见）
只在以下情况触发 Profile 更新（非每章）：
- 新发现的主角级人物（粗读遗漏）→ 首次出现章节写 Profile
- 身份彻底反转（卧底身份曝光等）→ Supervisor 显式调用 `rewrite_character_profile`

### R4.5 角色关系提取
细读阶段 CharacterUpdate 附带 relationship_delta（例如"张三与李四从朋友变敌人"），更新 Neptune 的 edges。

---

## R5. 地图与图谱（F5=C 含 Faction）

### R5.1 节点创建
- 新 place_id 首次出现 → Neptune 创建 Place 节点
- 新 faction_id → Faction 节点
- 幂等：同 (team_id, novel_id, place_id) 的节点只创建一次（upsert）

### R5.2 边更新
- visited 边：每章追加 chapter 到 `chapter_range` 列表（合并连续章节段）
- adjacent：LLM 推断的相邻关系（低置信度标 warning）
- located_in：层级关系
- belongs_to：角色-势力关系，带时间段

### R5.3 图谱一致性
- 每 10 章做一次图谱健壮性检查（环路检测 located_in）
- 发现冲突（例如 A located_in B 且 B located_in A）→ warning

---

## R6. 风格分析（F6=A 纯 LLM）

### R6.1 Prompt 结构
Claude Sonnet 4.7 接收：
- 样本章节正文（<= 60,000 字）
- 6 维度定义与打分范围说明

### R6.2 输出约束
- 每维度 integer 0-100
- 每维度必须配一句 < 80 字的解释
- JSON schema 强制校验；失败则重试 1 次

---

## R7. 细读章节（F7=A 每章单次 LLM 复合调用）

### R7.1 单次复合调用
每章 DeepRead 只调用 1 次 LLM，用复合 prompt 让 LLM 在**一次响应里同时返回** 4 类抽取结果：
```json
{
  "character_updates": [...],   // 人物状态变化（snapshot delta）
  "map_updates": {
    "places": [...],            // 新地点
    "factions": [...],          // 新势力
    "edges": [...]              // 新边
  },
  "events": [...],              // 本章事件
  "facts": [...]                // 杂项事实（rule / world_setting）
}
```

### R7.2 JSON Schema 约束
- LLM 响应必须符合预定义 JSON schema
- 响应解析失败 → 重试 1 次（prompt 附加错误示例）
- 仍失败 → 该章标记 partial，Job 继续

### R7.3 章节级并发（在 AD6=F 配置上叠加）
- 细读阶段按 Map state 并行 N 章
- 每章只有 1 次 Bedrock 调用，实际并发 = min(N, BEDROCK_RPS_QUOTA)
- N 由 AD6=F 动态并发决定

### R7.4 失败处理
单次调用失败 → 重试 3 次（指数退避）；耗尽后该章标记 partial，Job 继续。

### R7.5 成本估算
100 万字 / 300 章小说：
- 粗读阶段：~6 次调用（1 抽样 + 4 并行分析 + 1 Supervisor 决策）
- 细读阶段：300 章 × 1 次 = 300 次
- Supervisor 决策：~20 次
- **总计 ~330 次 LLM 调用，预计 8-12 min 完成**，满足 NFR-1

---

## R8. MemoryFacade 填充（U1 骨架 → U3 完整实现）

### R8.1 `remember(facts)` 实现
```python
for fact in facts:
    # 1. AgentCore Memory (必须成功)
    await agentcore_memory.upsert(team_id, novel_id, fact.fact_key, fact.content)
    # 2. Neptune (F5 图节点/边) — 失败仅 warning
    try:
        await neptune.upsert(node_or_edge_from(fact))
    except Exception:
        log.warning(...)
        emit_metric("MemoryWriteFailure", dims={"Layer": "neptune"})
    # 3. OpenSearch (向量) — 失败仅 warning
    try:
        embedding = await titan_embed(fact.content_text)
        await opensearch.index(fact.fact_key, embedding, payload)
    except Exception:
        log.warning(...)
        emit_metric("MemoryWriteFailure", dims={"Layer": "opensearch"})
```

### R8.2 `recall(query, top_k)` 实现
1. `titan_embed(query)` → 查询向量
2. OpenSearch kNN 搜索 top_k（**包含 team_id + novel_id filter**）
3. 对每个 hit 从 AgentCore Memory 读完整 Fact
4. 返回排序后的 Fact 列表

### R8.3 `upsert_graph(nodes, edges)` 实现
- Neptune Gremlin：`g.V().has('team_id', :tid).has('node_id', :nid).fold().coalesce(unfold(), addV(...))`
- 幂等 upsert：先 lookup 再 addV 或修改属性
- 每批次事务 100 节点 + 100 边

### R8.4 `hybrid_search` 实现
- 同时执行：BM25 文本搜索 + kNN 向量搜索
- RRF (Reciprocal Rank Fusion) 合并两份排序

### R8.5 Embeddings
- 模型：Amazon Titan Embeddings V2（1024 维）
- 缓存：进程内 LRU（key=text_hash）
- 失败：重试 2 次，耗尽抛 `MemoryBackendError`

---

## R9. 分层降级（F8=A）

### R9.1 写入降级矩阵
| 层 | 失败处理 |
|---|---|
| AgentCore Memory 写失败 | **致命** — 整 Fact 写失败，`remember()` 抛异常 |
| Neptune 失败 | warning + metric，Fact 继续 |
| OpenSearch 失败 | warning + metric，Fact 继续 |

### R9.2 读取降级
- `recall` 时 OpenSearch 不可用 → 降级到 DynamoDB 顺序扫描（按 novel_id），性能差但可用
- Neptune 不可用 → 图查询返回空 + warning，Agent 决策路径可继续

### R9.3 Circuit Breaker
- Neptune 连续 5 次失败 → 熔断 30s
- OpenSearch 同

---

## R10. 多租户（继承 U1）

所有 MemoryFacade 方法都要求 principal.team_id：
- AgentCore Memory namespace = `{team_id}:{novel_id}`
- Neptune 节点 property `team_id`，查询强制 `.has('team_id', :tid)`
- OpenSearch 文档字段 `team_id`，查询强制 filter

---

## R11. 可观测性

### R11.1 metric
- `AgentSpanDurationMs{agent, model}` — 每 sub-agent 耗时
- `SupervisorStepCount{job_id}` — Supervisor 决策数
- `MemoryWriteFailure{Layer}` — 分层降级计数
- `ChapterProcessingMs` — 单章细读耗时
- `LlmInvocationCount{stage}` — 每阶段 LLM 调用数（追溯成本）

### R11.2 AgentCore Observability
- 每 sub-agent 注册为独立 agent，trace 通过 request_id 串联

---

## R12. Job 状态写回（对接 U1 IngestionStateMachine 后续）

U3 分析 Job 对应 U1 `AnalysisStateMachine`（之前由 U1 创建骨架）。Worker 完成后：
- 将 AnalysisReport 写 S3
- 更新 Novel.status = ANALYZED
- 发 EventBridge `novel.analyzed`（U4 订阅）
