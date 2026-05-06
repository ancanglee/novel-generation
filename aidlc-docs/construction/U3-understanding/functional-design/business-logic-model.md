# U3 Business Logic Model

**Unit**：U3 Understanding Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## Flow 1. 分析 Job 启动

**触发**：EventBridge `novel.ingested`（来自 U2）或 `POST /api/v1/analyses` 显式触发

1. ApiService 创建 AnalysisJob（job_type=ANALYSIS, status=QUEUED）
2. 启动 AnalysisStateMachine（U1 Step Functions）
3. SFN UpdateJobRunning → SendMessage(analysis-queue)
4. UnderstandingWorker 消费消息 → 初始化 SupervisorContext → 调用 Supervisor Agent

---

## Flow 2. Supervisor 主循环（F1=B）

**执行点**：UnderstandingWorker 进程内

1. 初始化 SupervisorContext：novel_id, job_id, step_history=[]
2. While not done and step_count < 50:
   a. Supervisor LLM（Opus 4.7）收到 context + 可用工具列表
   b. Supervisor 决定下一步：调用哪个工具，或 `finalize_report` 结束
   c. 调用对应 sub-agent，结果写回 partial_results
   d. step_history.append(agent_name)
   e. 发射 `SupervisorStepCount` metric
3. 50 步未完成 → 警告 + 强制 finalize
4. 完成后写 AnalysisReport 到 S3 + Novel.status = ANALYZED

---

## Flow 3. 粗读 LLM 自适应抽样（F2=C）

**触发**：Supervisor 决定 `sample_chapters(novel_id, goal)`

1. 从 DynamoDB 拉取全部 Chapter 元数据（title 列表）
2. 构造 prompt：
   ```
   这是一本 {word_count} 字、{chapter_count} 章的小说。
   章节目录：
   第1章 开端
   第2章 初入江湖
   ...
   请选 8-15 个章节用于理解全书风格、类型、主要人物、地图。
   必选：首 2 章 + 末 2 章。
   返回 JSON：{"selected": [1, 2, 5, 10, ...], "reason": {...}}
   ```
3. 调用 Claude Haiku 4.5（成本低）
4. 解析 JSON，强制保留首末各 2 章（即使 LLM 漏选）
5. 从 S3 读取选定章节的 Markdown（`chapters/{idx:05d}.md`）
6. 返回 ChapterSample 列表（≤ 60000 字总量）

---

## Flow 4. 并行抽取（类型/人物全局/地图/风格）

Supervisor 在粗读后可选择并行发起：
- `classify_tags(samples)` → 多标签 + 置信度（Claude Sonnet 4.6）
- `extract_characters_global(samples)` → 全书主要人物初稿（Sonnet 4.6）
- `extract_map(samples)` → 主要地点 + 势力（Sonnet 4.6）
- `analyze_style(samples)` → StyleVector（Sonnet 4.7）

**注意**：在 F1=B Supervisor 模式下，是否并行由 Supervisor 自身决定。Supervisor Prompt 包含"尽可能并行"的提示。

---

## Flow 5. 细读章节（F7=A 每章单次复合调用 + F4=A 增量快照）

**触发**：Supervisor 对每个细读章节循环调用

每章流程：
1. `extract_chapter_all(chapter_idx)` — **单次 Bedrock 调用**输出全部 4 类抽取，JSON schema 约束
2. 响应解析失败 → 重试 1 次（prompt 附加错误示例）
3. 处理结果：
   - character_updates → 写 CharacterSnapshot（**不重建 Profile**，F4=A）
   - map_updates → upsert_graph(places + factions + edges)
   - events → 写 Event 节点
   - facts → remember
4. 批量 flush MemoryFacade.remember(facts) + upsert_graph(nodes, edges)

**成本**：每章 1 次 Bedrock 调用（vs 原 F7=B 的 4 次），总体减 4×；100 万字 / 300 章约 330 次 LLM 调用，预计 8-12 min 满足 NFR-1。

---

## Flow 6. Memory 写入（R8 + F8=A 分层降级）

`MemoryFacade.remember(team_id, novel_id, facts)`：

```
for fact in facts:
    # Layer 1: AgentCore Memory (critical)
    try:
        await agentcore_memory.upsert(ns=f"{team_id}:{novel_id}", key=fact.fact_key, data=fact)
    except Exception as e:
        raise MemoryBackendError(fact.fact_key) from e  # 致命

    # Layer 2: Neptune (degradable)
    if fact_type_has_graph(fact):
        try:
            await neptune.upsert_node_or_edge(...)
        except Exception:
            emit_metric("MemoryWriteFailure", {"Layer": "neptune"})

    # Layer 3: OpenSearch (degradable)
    if fact.content_text:
        try:
            embedding = await titan_embed(fact.content_text)
            await opensearch.index(fact.fact_key, embedding, payload={...})
        except Exception:
            emit_metric("MemoryWriteFailure", {"Layer": "opensearch"})
```

---

## Flow 7. Memory 召回（供 U4 使用）

`MemoryFacade.recall(team_id, novel_id, query, top_k=20)`：

1. `embedding = await titan_embed(query)`
2. OpenSearch kNN：
   ```
   filter: {"bool":{"must":[{"term":{"team_id":tid}},{"term":{"novel_id":nid}}]}}
   query: {"knn":{"embedding":{"vector":embedding, "k":top_k}}}
   ```
3. 对每个 hit 从 AgentCore Memory 读完整 Fact
4. 按相关性排序返回

---

## Flow 8. 图遍历（给 U5 ConsistencyAgent 使用）

`MemoryFacade.neighbors(team_id, novel_id, node_id, edge_type, depth=1)`：

Gremlin 查询：
```
g.V().has('team_id', tid).has('novel_id', nid).has('node_id', node_id)
 .repeat(both(edge_type).simplePath()).times(depth).dedup()
 .valueMap()
```

---

## Flow 9. 角色章节状态快照查询（给 U4 GenerationAgent）

`MemoryFacade.get_character(team_id, novel_id, character_id, at_chapter)`：

1. 查 DynamoDB SK=`CHAR_SNAP#{novel_id}#{character_id}#{chapter:05d}`
2. 找 ≤ at_chapter 的最大 chapter snapshot
3. 合并 snapshot + Profile → CharacterSnapshot 返回

用于：U4 生成第 N 章前，了解人物在第 N-1 章末的状态。

---

## Flow 10. Supervisor 决策安全网

**触发**：每轮决策后

1. 检查 step_count ≤ 50
2. 检查同 (agent, args) 调用 ≤ 2
3. 检查总耗时 ≤ 15 min
4. 超限 → 强制 finalize_report 终止

---

## Flow 11. AnalysisReport 组装

Supervisor 决定 `finalize_report` 后：

1. 从 partial_results 汇总：tags, characters (importance > 0.3), places, factions, style, summary
2. 写 S3：`teams/{team_id}/novels/{novel_id}/analysis-report.json`
3. 更新 Novel.status = ANALYZED
4. SFN SendTaskSuccess
5. EventBridge 发 `novel.analyzed`（U4 订阅）

---

## Flow 12. 失败与重启

- Worker 被 Spot 回收：SFN taskToken 未收到 → Retry 重新派发
- 新 Worker 重启时可从 DynamoDB 读 partial_results 续跑（SupervisorContext 每 5 步写 checkpoint）
- Bedrock 限流：Strands 内置 backoff；若连续失败触发 Circuit Breaker → 暂停 30s
