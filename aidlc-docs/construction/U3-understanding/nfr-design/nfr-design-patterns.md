# U3 非功能设计模式（NFR Design Patterns）

**Unit**：U3 Understanding Agents
**阶段**：NFR Design
**日期**：2026-04-28

---

## 1. Supervisor Prompt 模式（D1=C 工具清单 + 推荐路径 + few-shot）

### 1.1 System Prompt 骨架
```
你是小说理解任务的 Supervisor Agent，负责编排多个 sub-agent 完成小说分析。

# 可用工具（9 个）
- sample_chapters(novel_id, goal): 选 8-15 章抽样
- classify_tags(samples): 多标签 + 置信度
- extract_characters_global(samples): 粗读产出 Profile 初稿
- extract_map_global(samples): 粗读地点/势力初稿
- analyze_style(samples): 6 维风格向量
- extract_chapter_all(chapter_idx): 单次复合调用，抽取本章全部
- rewrite_character_profile(character_id): 罕见 Profile 重写
- write_memory(facts, nodes, edges): 批量写入
- finalize_report(): 结束并组装报告

# 推荐路径
1. sample_chapters
2. 并行 classify_tags + extract_characters_global + extract_map_global + analyze_style
3. 对每章 extract_chapter_all
4. write_memory
5. finalize_report

# 硬约束
- 总步数 ≤ 50
- 总时长 ≤ 15 min
- 同 (tool, args) 不能调用 ≥ 2 次
- 任何错误都记录到 context.warnings

# Few-shot 成功示例
<example 1>
输入：一本 50 万字现代言情小说
决策序列：
  step 1: sample_chapters(novel_id, goal="understand main characters and emotional arcs")
  step 2-5: 并行调用 classify_tags / extract_characters_global / extract_map_global / analyze_style
  step 6-12: 抽样细读 7 章（主要情节节点）
  step 13: write_memory(flush_all=true)
  step 14: finalize_report()
总步数：14，耗时 9 min
</example 1>

<example 2>
输入：一本 300 万字修仙小说
决策序列：
  step 1: sample_chapters
  step 2-5: 并行全局分析
  step 6-45: 按大纲分批细读（40 章）
  step 46: write_memory
  step 47: finalize_report
总步数：47，耗时 14 min
</example 2>

<example 3>
输入：一本风格高度戏仿的小说，粗读识别失败
决策序列：
  step 1: sample_chapters
  step 2: classify_tags（confidence < 0.3 → 警告）
  step 3: 扩大 sample 到 20 章重试
  ...
</example 3>
```

### 1.2 每步响应格式
Claude 必须返回 `{"tool": "...", "args": {...}, "reason": "..."}`，通过 Bedrock Tool Use 强制。

### 1.3 记忆压缩
Supervisor Context 随步数增长可能溢出 prompt size。当 step_count % 10 == 0 时压缩 partial_results（保留 top-10 关键事实）。

---

## 2. JSON Schema 约束（D6=B Bedrock Tool Use）

### 2.1 extract_chapter_all 的 toolConfig
```python
tool_config = {
    "tools": [
        {
            "toolSpec": {
                "name": "record_chapter_extraction",
                "description": "Record all extractions for one chapter",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "character_updates": {"type": "array", "items": {...}},
                            "map_updates": {
                                "type": "object",
                                "properties": {
                                    "places": {"type": "array"},
                                    "factions": {"type": "array"},
                                    "edges": {"type": "array"}
                                }
                            },
                            "events": {"type": "array"},
                            "facts": {"type": "array"}
                        },
                        "required": ["character_updates", "map_updates", "events", "facts"]
                    }
                }
            }
        }
    ],
    "toolChoice": {"tool": {"name": "record_chapter_extraction"}}
}
```

### 2.2 优点
- Claude 服务端强制遵守 schema，解析失败率降至接近 0
- 客户端代码只处理 `response.output.message.content[0].toolUse.input`
- 仍保留重试（网络/超时原因）但不再重试 schema 问题

### 2.3 所有 sub-agent 都使用 Tool Use
- `classify_tags` → tool `record_tags`
- `extract_characters_global` → tool `record_characters`
- `extract_map_global` → tool `record_map`
- `analyze_style` → tool `record_style_vector`
- 供 Supervisor 调用的工具通过相同机制注册

---

## 3. MemoryFacade 每章立即 Flush（D2=A）

### 3.1 Flush 时机
每章 `extract_chapter_all` 完成 → 立即调用 `memory_facade.remember_and_upsert(facts, nodes, edges)`

### 3.2 三后端写入顺序
```
1. AgentCore Memory (critical, 必须成功)
   - 按 fact_key 批量 upsert 20 facts
2. Neptune (降级，全 openCypher, batch 100)
   - MERGE nodes (Place, Character, Event, Faction)
   - MERGE edges (visited, located_in, etc.)
3. OpenSearch (降级，bulk API)
   - Titan embed(fact.content_text) × 20
   - bulk _index(facts-{team_id})
```

### 3.3 并行写入
Neptune 和 OpenSearch 写入可 asyncio.gather 并行（互不依赖），减少 per-chapter 延迟。

### 3.4 降级时的 warning
- Neptune 失败 → `emit_metric('MemoryWriteFailure', {'Layer':'neptune'})` + context.warnings.append
- OpenSearch 失败 → 同上
- AgentCore Memory 失败 → raise 致命

---

## 4. Neptune openCypher 模式（D3=A）

### 4.1 统一 openCypher 使用
所有节点/边操作用 openCypher 语句：

**Upsert Place**：
```cypher
MERGE (p:Place {team_id: $tid, novel_id: $nid, place_id: $pid})
SET p += $props, p.updated_at = timestamp()
```

**Upsert Edge (visited)**：
```cypher
MATCH (c:Character {team_id: $tid, novel_id: $nid, character_id: $cid})
MATCH (p:Place {team_id: $tid, novel_id: $nid, place_id: $pid})
MERGE (c)-[r:VISITED]->(p)
SET r.chapter_range = $range, r.frequency = coalesce(r.frequency, 0) + 1
```

**邻居查询 (depth=1)**：
```cypher
MATCH (n {team_id: $tid, novel_id: $nid, node_id: $nid_val})-[r]-(neighbor)
WHERE type(r) = $edge_type
RETURN neighbor, r
LIMIT 50
```

### 4.2 强制多租户
每条语句必须带 `team_id: $tid` 过滤，由 MemoryFacade 包装层自动注入。

### 4.3 连接管理
- HTTPS POST 到 Neptune 查询端点 + sigv4 签名
- 连接池 10 并发（单 Worker）
- 每批次事务 ≤ 100 节点 + 100 边

---

## 5. OpenSearch Per-Team 索引（D4=A）

### 5.1 索引模板
```json
{
  "index_patterns": ["facts-*"],
  "settings": {"index.knn": true},
  "mappings": {
    "properties": {
      "team_id": {"type": "keyword"},
      "novel_id": {"type": "keyword"},
      "fact_key": {"type": "keyword"},
      "fact_type": {"type": "keyword"},
      "chapter": {"type": "integer"},
      "content_text": {"type": "text", "analyzer": "ik_max_word"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 1024,
        "method": {"name": "hnsw", "space_type": "cosinesimil",
                    "parameters": {"ef_construction": 512, "m": 16}}
      }
    }
  }
}
```

### 5.2 索引生命周期
- 新 team 第一次 ingest 时 lazy 创建 `facts-{team_id}` 索引
- team 删除时 drop 对应索引
- 单索引容量：单 novel ~30k 向量，100 novels/team = 3M 向量 = ~12 GB（远低于 OpenSearch 单索引限制）

### 5.3 查询强制 filter
```json
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"team_id": "${tid}"}},
        {"term": {"novel_id": "${nid}"}}
      ],
      "must": [
        {"knn": {"embedding": {"vector": [...], "k": 20}}}
      ]
    }
  }
}
```

---

## 6. Strands Agent 模块化（D5=A）

### 6.1 代码结构
```
services/worker-analysis/src/worker_analysis/
├── supervisor.py              # Supervisor Opus 4.7，含 few-shot 示例
├── agents/
│   ├── __init__.py
│   ├── rough_read.py          # sample_chapters
│   ├── classification.py      # classify_tags
│   ├── character_global.py    # extract_characters_global
│   ├── map_global.py          # extract_map_global
│   ├── style.py               # analyze_style
│   ├── chapter_all.py         # extract_chapter_all (核心细读)
│   ├── profile_rewrite.py     # rewrite_character_profile (罕见)
│   └── memory_writer.py       # write_memory (封装 MemoryFacade)
├── memory/
│   ├── __init__.py
│   ├── facade_impl.py         # MemoryFacade 具体实现
│   ├── agentcore_memory.py    # AgentCore Memory 包装
│   ├── neptune_client.py      # openCypher + sigv4
│   └── opensearch_client.py   # knn 查询
├── prompts/
│   ├── supervisor.md          # few-shot examples
│   ├── chapter_extraction.md
│   ├── style.md
│   └── ...
└── main.py                    # SQS consumer + Supervisor 入口
```

### 6.2 @tool 注册模式
```python
# agents/chapter_all.py
from strands import tool

@tool(name="extract_chapter_all", description="...")
async def extract_chapter_all(chapter_idx: int, ctx: SupervisorContext) -> ChapterExtraction:
    ...
```

Supervisor 初始化时自动扫描并注册。

### 6.3 per-agent 测试
每 sub-agent 独立单测（mock Bedrock），集成测试覆盖 Supervisor 主路径。

---

## 7. Checkpoint 模式（NFR-2.1 每 5 步）

### 7.1 数据结构
写到 `novelgen_jobs` 表：
```
pk: TEAM#{team_id}
sk: CHECKPOINT#{job_id}
partial_results: <json>
step_history: [...]
current_goal: "..."
saved_at: timestamp
ttl: +24h
```

### 7.2 恢复流程
Worker 启动时：
1. 从 SQS 拉到消息后，先查对应 job_id 的 CHECKPOINT 项
2. 若存在 → 从 partial_results 恢复 SupervisorContext
3. 不存在 → 从头开始

---

## 8. 多租户（继承 U1 + U2）

MemoryFacade 所有方法第一参数 `team_id`，内部强制：
- AgentCore Memory namespace = `{team_id}:{novel_id}`
- Neptune 所有节点/边带 `team_id` 属性，查询强制 filter
- OpenSearch 索引名含 team_id，文档字段双重约束

---

## 9. 可观测

### 9.1 Supervisor trace
每步决策在 AgentCore Observability 开一个 span，记录：
- Supervisor 输入 context 摘要
- 决策的 tool + args
- sub-agent 执行耗时
- partial_results 变化

### 9.2 EMF Metric
继承 NFR-5.2 定义的 8 个 metric。

---

## 10. 总结：架构模式图

```
SQS → Worker (asyncio) → Supervisor (Opus 4.7)
                          │
                          ├─[ReAct-free]→ 决策下一步 Tool
                          │               │
                          │               ▼
                          │          Sub-agent (Strands @tool)
                          │               │
                          │               ├─ Bedrock Tool Use (schema-enforced JSON)
                          │               ├─ MemoryFacade.remember()
                          │               │   ├─ AgentCore Memory (critical)
                          │               │   ├─ Neptune openCypher (degradable)
                          │               │   └─ OpenSearch bulk (degradable)
                          │               └─ Titan Embeddings V2 (1024 dim)
                          │
                          └─ Every 5 steps → Checkpoint → DDB
```
