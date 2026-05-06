# U4 Domain Entities

**Unit**：U4 Generation Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## E1. Mode（F1=A 生成模式）

```python
class Mode(str, Enum):
    CLEAN_ROOM = "clean_room"       # 同风格新世界（全新仿写）
    CONTINUATION = "continuation"   # 续写原作
```

两种模式使用不同的 system prompt（`prompts/clean_room.md` / `prompts/continuation.md`）。

---

## E2. Generation（生成任务）

| 字段 | 类型 | 说明 |
|---|---|---|
| generation_id | UUID | 主键 |
| team_id | UUID | 租户 |
| owner_user_id | UUID | 创建者 |
| novel_id | UUID | 原作 novel（续写/仿写的源）|
| mode | Mode | CLEAN_ROOM / CONTINUATION |
| style_vector | StyleVector | 6 维风格 + 用户滑块覆盖 |
| reference_novels | list[UUID] | 额外风格参考（Q10=B+C） |
| reference_weights | list[float] | 混合权重（和 = 1.0） |
| target_chapter_count | Int | 目标章节数 |
| target_words_per_chapter | Int | 目标每章字数 |
| outline_s3_key | String? | 大纲 JSON 存 S3 |
| outline_approved | Bool | 用户是否批准大纲 |
| status | Enum{DRAFT, OUTLINING, OUTLINE_READY, APPROVED, GENERATING, COMPLETED, CANCELED, FAILED} | |
| current_chapter | Int | 已生成/正在生成的章节索引 |
| created_at | Timestamp | |
| updated_at | Timestamp | |

**PK/SK**：`TEAM#{team_id}` / `GEN#{generation_id}`

---

## E3. OutlineItem（章节级大纲，F2=A）

| 字段 | 类型 | 说明 |
|---|---|---|
| chapter_idx | Int | 1 起 |
| title | String | 章节标题建议 |
| summary | String | 约 100 字梗概 |
| main_characters | list[character_id] | 本章主要人物 |
| locations | list[place_id] | 本章地点 |
| plot_tags | list[String] | 情节标签（如"战斗"、"转折"）|
| target_words | Int | 目标字数 |
| user_edited | Bool | 是否被用户修改过 |

---

## E4. Outline（全书大纲）

```python
class Outline(BaseModel):
    generation_id: UUID
    main_plot: str              # 全书主线概述，< 500 字
    character_table: list[dict]  # 人物表（id, role, arc）
    world_summary: str          # 世界观概述，< 300 字
    items: list[OutlineItem]    # 章节级
    version: int                # 每次用户编辑 +1
```

**存储**：S3 `teams/{team_id}/generations/{generation_id}/outline.v{version}.json`

---

## E5. Chapter（生成章节）

| 字段 | 类型 | 说明 |
|---|---|---|
| generation_id | UUID | |
| chapter_idx | Int | |
| status | Enum{QUEUED, GENERATING, GENERATED, CRITIQUED, APPROVED, REWRITE_REQUESTED, REJECTED} | |
| content_s3_key | String | `teams/.../generations/{gid}/chapters/{idx:05d}.md` |
| word_count | Int | |
| self_critique | CritiqueNote? | Layer-1 自检（F5=A 独立调用） |
| critique_report_ref | String? | U5 Layer-2 Critic 报告 |
| moderation_ref | String? | U5 moderation 报告 |
| rewrite_count | Int | 用户打回次数 |
| generated_at | Timestamp | |

**PK/SK**：`TEAM#{team_id}` / `GEN_CHAPTER#{generation_id}#{idx:05d}`

---

## E6. CritiqueNote（Self-Critique 输出）

```python
class CritiqueNote(BaseModel):
    score: int                  # 0-100 总体评分
    issues: list[Issue]         # 问题清单
    suggestions: list[str]      # 改进建议
    dimensions: dict[str, int]  # 按风格 6 维度打分（对比目标）

class Issue(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: Literal["logic", "character", "style_drift", "consistency", "language"]
    excerpt: str                # 问题片段
    comment: str                # 具体说明
```

---

## E7. StreamEvent（SSE 事件）

```python
class StreamEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    CHAPTER_START = "chapter_start"
    CHAPTER_COMPLETE = "chapter_complete"
    CRITIQUE_READY = "critique_ready"
    ERROR = "error"
    CANCELED = "canceled"
    HEARTBEAT = "heartbeat"

class StreamEvent(BaseModel):
    type: StreamEventType
    event_id: str               # 递增 ID（用于 Last-Event-ID 恢复）
    generation_id: UUID
    chapter_idx: int | None
    data: dict[str, Any]
    timestamp: datetime
```

---

## E8. GenerationContext（Worker 运行态）

```python
class GenerationContext(BaseModel):
    generation_id: UUID
    team_id: UUID
    novel_id: UUID
    mode: Mode
    style_vector: StyleVector
    outline: Outline
    current_chapter: int
    principal_user_id: UUID
    model_config_version: int   # 冻结本 Job 的模型配置版本
```

---

## E9. OutlineRevisionAdvice（F3=B 用户编辑大纲后的 LLM 校验建议）

```python
class OutlineRevisionAdvice(BaseModel):
    item_idx: int
    concerns: list[str]         # "与原作风格冲突"、"破坏前后逻辑" 等
    suggestions: list[str]
    severity: Literal["info", "warn"]
```

输出后**不强制应用**，仅在 UI 上显示给用户参考。

---

## E10. StyleInjectionBlock（F7=C 风格注入）

```python
class StyleInjectionBlock(BaseModel):
    vector_prefix: str          # 6 维数值 + 解释（F7=A 部分）
    reference_excerpts: list[str]  # Memory 召回的相似风格片段（F7=C 新增）
```

构造方式：
1. 固定模板展开 StyleVector 6 维
2. 调用 `MemoryFacade.hybrid_search(query_text="风格描述", top_k=3)`
3. 取前 3 段 300 字原作片段插入

---

## E11. GenerationEvent（EventBridge 事件）

| detail-type | 用途 | 订阅方 |
|---|---|---|
| `generation.outline.ready` | 大纲生成完成 | API SSE |
| `generation.chapter.streaming` | 含 text_delta 块 | API SSE |
| `generation.chapter.completed` | 单章完成（含 self_critique）| U5 Critic / Moderation |
| `generation.cancel_requested` | 用户发起取消 | Worker 内部（通过 DDB 读）|
| `generation.completed` | 全书生成完成 | U6 / 通知 |
