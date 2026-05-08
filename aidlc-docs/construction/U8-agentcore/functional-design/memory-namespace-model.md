# AgentCore Memory — Namespace / Event / Strategy 模型

## Memory 资源
- **单一 Memory per env**：`novelgen-{env}-memory`（dev / prod 各一个）
- **eventExpiryDuration**：`P365D`（1 年；按合规）
- **memoryStrategies**（两条平行策略，SDK 会异步把 event 聚合成长期记忆）：
  1. **SEMANTIC（语义事实）**
     - `name=novel-facts-semantic`
     - `namespaces=["{actorId}/{sessionId}","{actorId}"]`
     - 用于存"人物属性 / 地点属性 / 事件"
  2. **SUMMARIZATION（章节摘要）**
     - `name=chapter-summaries`
     - `namespaces=["{actorId}/chapters"]`
     - 用于存"每章浓缩摘要"，给后续章节生成做 recall

## Actor / Session 映射

| Event 类型 | actorId | sessionId | payload |
|---|---|---|---|
| Fact (character/map/event) | `{team_id}:{novel_id}` | `{job_id}` | `conversational(role=USER, content.text=json.dumps(fact))` |
| Chapter summary | `{team_id}:{novel_id}` | `chapter-{chapter_idx}` | `conversational(role=ASSISTANT, content.text=summary)` |
| Style analysis | `{team_id}:{novel_id}` | `style` | `blob(data=json.dumps(style))` |

## Namespace 检索

```python
# 人物
RetrieveMemoryRecords(
  memoryId=MEMORY_ID,
  namespace=f"{team_id}:{novel_id}",
  searchCriteria={"searchQuery": f"character snapshot for {character_id}", "topK": 5}
)

# 章节摘要
RetrieveMemoryRecords(
  memoryId=MEMORY_ID,
  namespace=f"{team_id}:{novel_id}:chapters",  # 与策略 namespaces 定义对齐
  searchCriteria={"searchQuery": query, "topK": 10}
)
```

## Fact → Event payload 转换

```python
def fact_to_event_payload(fact: Fact) -> list[dict]:
    return [{
        "conversational": {
            "role": "USER",
            "content": {"text": json.dumps({
                "fact_key": fact.fact_key,
                "fact_type": fact.fact_type.value,
                "content": fact.content,
                "source_chapter": fact.source_chapter,
            }, ensure_ascii=False)}
        }
    }]
```

## 幂等

- AgentCore Memory event 本身没有幂等键；我们在业务层用 `fact_key` 作为 dedup——写入前先本地布隆过滤器（size=1e6，基于 `{job_id}:{fact_key}`）过滤，避免同 job 重试造成 event 爆炸。
- DLQ：`CreateEvent` 抛 ThrottlingException → tenacity 3×exp-backoff → 仍失败 → 走 SQS DLQ。
