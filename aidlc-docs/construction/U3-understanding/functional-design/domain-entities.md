# U3 Domain Entities

**Unit**：U3 Understanding Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## E1. TagCandidate（类型标签候选，F3=A）

| 字段 | 类型 | 说明 |
|---|---|---|
| tag | String | 归一化类型名（例如"修仙"、"穿越"、"系统流"）|
| confidence | Float (0-1) | LLM 给出的置信度 |
| evidence | list[String] | 支持该标签的章节引用（最多 3 条）|
| novel_id | UUID | |
| source_agent | String | 固定 "classification" |

**存储**：作为 AnalysisReport.tags 列表的元素，不单独写表。

---

## E2. CharacterProfile（人物档案，F4=A 粗读初稿 + 细读增量）

| 字段 | 类型 | 说明 |
|---|---|---|
| character_id | String | 归一化姓名（NFKC + 小写 + 去空格）|
| display_name | String | 原文出现的标准姓名 |
| aliases | list[String] | 别名列表（例如"主角" → "李白"）|
| gender | Enum{MALE, FEMALE, UNKNOWN, OTHER} | |
| appearance | String | 外貌描述（自由文本）|
| personality | String | 性格描述 |
| key_behaviors | list[String] | 代表性行为 |
| first_chapter | Int | 首次出现章节 |
| last_chapter | Int | 最后出现章节（细读阶段更新）|
| importance | Float (0-1) | 重要性评分（主角/配角/龙套）|
| faction_id | String? | 所属势力 ID（F5=C） |

**PK/SK**：`TEAM#{team_id}` / `CHARACTER#{novel_id}#{character_id}`
**F4=A 约定**：粗读阶段产出 Profile 初稿并写入；细读阶段**不重建 Profile**，只追加 CharacterSnapshot。仅在 R4.4 罕见情况（新主角发现/身份反转）才触发 Profile 重写。

---

## E3. CharacterSnapshot（人物章节状态快照）

| 字段 | 类型 | 说明 |
|---|---|---|
| character_id | String | 对应 Profile |
| novel_id | UUID | |
| chapter | Int | 快照所在章节 |
| location | String? | 当时所在地点 |
| power_level | String? | 修为/等级（修仙/武侠类型适用）|
| mood | String? | 情绪 |
| alive | Bool | 存活状态（死亡后为 false，关键一致性字段） |
| relationships_delta | dict[character_id, RelationChange] | 关系变化 |

**PK/SK**：`TEAM#{team_id}` / `CHAR_SNAP#{novel_id}#{character_id}#{chapter:05d}`

---

## E4. MapPlace（地图节点，F5=C）

| 字段 | 类型 | 说明 |
|---|---|---|
| place_id | String | 归一化地名 |
| display_name | String | |
| aliases | list[String] | 别名（长安 = 西京）|
| place_type | Enum{CITY, COUNTRY, SECT, DOMAIN, REALM, BUILDING, OTHER} | |
| description | String | |
| first_chapter | Int | |
| last_chapter | Int | |
| located_in | String? | 上级地点 ID（located_in 边的源头）|

**Neptune 节点**：label=`Place`

---

## E5. Faction（势力节点，F5=C 新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| faction_id | String | |
| display_name | String | 例如"青云宗"、"魔门"|
| faction_type | Enum{SECT, EMPIRE, TRIBE, CLAN, ORGANIZATION, OTHER} | |
| description | String | |
| first_chapter | Int | |
| alignment | Enum{PROTAGONIST, ANTAGONIST, NEUTRAL, UNKNOWN} | |

**Neptune 节点**：label=`Faction`

---

## E6. MapEdge（图谱边）

四种边类型（F5=A + C 扩展）：

| 边类型 | 起点 → 终点 | 属性 |
|---|---|---|
| visited | Character → Place | chapter_range (start, end), frequency |
| adjacent | Place ↔ Place | distance_hint, direction |
| located_in | Place → Place（从属）/ Faction → Place（盘踞）| depth |
| event_at | Event → Place | chapter |
| belongs_to | Character → Faction | role（宗主/弟子/叛徒）, chapter_range |
| rival | Faction ↔ Faction | intensity |

---

## E7. Event（事件节点）

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | String | `event:{chapter}:{seq}` |
| summary | String | 一句话摘要 |
| chapter | Int | |
| participants | list[character_id] | |
| location | String? | place_id |
| importance | Float (0-1) | |
| event_type | Enum{BATTLE, BREAKTHROUGH, DEATH, MEETING, CEREMONY, TRAVEL, OTHER} | |

**Neptune 节点**：label=`Event`

---

## E8. StyleVector（风格向量，F6=A 纯 LLM）

```python
class StyleVector(BaseModel):
    tone: int          # 0=深沉严肃 → 100=风趣幽默
    pace: int          # 0=慢节奏 → 100=快节奏
    detail_density: int    # 0=简洁 → 100=细腻
    dialogue_ratio: int    # 0=无对话 → 100=全对话
    emotion_intensity: int # 0=平静 → 100=浓烈
    scope: int             # 0=个人小事 → 100=宏大史诗
    # 每个维度由 LLM 给出 0-100 分 + 一句话解释
    explanations: dict[str, str]
```

**存储**：作为 AnalysisReport.style 字段。`fact_key = f"style:{novel_id}"` 写入 MemoryFacade。

---

## E9. ChapterSample（粗读采样章节，F2=C LLM 自适应）

| 字段 | 类型 | 说明 |
|---|---|---|
| chapter_idx | Int | |
| title | String | |
| content | String | Markdown 正文 |
| selection_reason | String | LLM 为何选这章（例如"首章开场"、"大事件"）|
| word_count | Int | |

**F2=C 生成流程**：
1. 获取全书章节目录（title 列表）
2. Claude Haiku 4.5 根据章节标题选 8-15 章（含开头 2 章 + 结尾 2 章必选）
3. 读入被选章节正文 → ChapterSample 列表

---

## E10. ChapterExtraction（单章细读产出，F7=A 单次复合调用）

F7=A 要求每章 1 次 LLM 调用，在同一响应中返回 4 类抽取结果：

```python
class ChapterExtraction(BaseModel):
    chapter_idx: int
    character_updates: list[CharacterUpdate]   # 状态变化（snapshot delta）
    map_updates: MapExtraction                 # {places, factions, edges}
    events: list[Event]
    facts: list[Fact]                          # rule / world_setting 类型
    warnings: list[str] = []                   # LLM 自报的不确定信息
```

**JSON Schema 强制校验**：LLM 响应必须符合上述结构；解析失败重试 1 次，仍失败则该章标记 partial。

**Strands `@tool` 名称**：`extract_chapter_all(chapter_idx)` 一个工具包含所有抽取逻辑。

---

## E11. AnalysisReport（总报告，对外 API 返回）

| 字段 | 类型 | 说明 |
|---|---|---|
| novel_id | UUID | |
| tags | list[TagCandidate] | 多标签 + 置信度 |
| characters | list[CharacterProfile] | 主要人物（importance > 0.3）|
| places | list[MapPlace] | |
| factions | list[Faction] | |
| style | StyleVector | |
| summary | String | 一段话整体摘要（300 字以内）|
| generated_at | Timestamp | |
| model_versions | dict[stage, model_id] | 记录每阶段使用的模型 |

**存储**：S3 `teams/{team_id}/novels/{novel_id}/analysis-report.json`

---

## E12. SupervisorContext（F1=B Supervisor 运行态）

```python
class SupervisorContext(BaseModel):
    novel_id: UUID
    job_id: UUID
    principal_team: UUID
    step_history: list[str]           # 已执行的 sub-agent 名称
    current_goal: str                  # 当前目标
    novel_metadata: dict[str, Any]    # 章节数、字数等
    partial_results: dict[str, Any]   # 已完成 sub-agent 的输出
```

Supervisor 每轮决定下一个 sub-agent（或判定完成）。
**决策边界**：最多 50 步，防止循环。

---

## Neptune 节点/边完整 schema

```
Nodes:
  Place      {place_id, name, type, team_id, novel_id, ...}
  Character  {character_id, name, team_id, novel_id, ...}
  Event      {event_id, summary, chapter, team_id, novel_id, ...}
  Faction    {faction_id, name, type, team_id, novel_id, ...}

Edges:
  visited(Character → Place)       {chapter_range, frequency}
  adjacent(Place ↔ Place)          {distance_hint}
  located_in(Place → Place)        {depth}
  located_in(Faction → Place)      {role="base"}
  event_at(Event → Place)          {}
  participated(Character → Event)  {role}
  belongs_to(Character → Faction)  {role, chapter_range}
  rival(Faction ↔ Faction)         {intensity}
```

所有节点/边都带 `team_id` 与 `novel_id` 属性用于多租户过滤（Gremlin/openCypher 查询强制 filter）。
