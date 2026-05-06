# U5 Domain Entities

**Unit**：U5 Critic & Consistency
**阶段**：Functional Design
**日期**：2026-04-28

> **Scope change**: 用户在 F4/F6 明确移除 ModerationAgent。U5 范围缩减为 **Critic + Consistency** 两个 Agent。US-09-01 / US-09-02（ContentModerator 审核队列）在本 Unit 不实现；U1 预建的 `moderation-queue` SQS 与 `worker-moderation` Service 作为 V2 预留。

---

## E1. CritiqueReport（Layer-2 Critic 输出，F1=B 复核）

| 字段 | 类型 | 说明 |
|---|---|---|
| report_id | UUID | |
| generation_id | UUID | |
| chapter_idx | Int | |
| team_id | UUID | |
| score | Int (0-100) | 本章总评分 |
| issues | list[Issue] | 复核结论：Layer-1 已发现问题 + Layer-2 补充 |
| cross_chapter_concerns | list[CrossChapterConcern] | **跨章节风格漂移 / 角色走样** |
| suggestions | list[str] | 可执行修改建议 |
| layer1_confirmed | list[Issue] | 与 Layer-1 重合的 issue（复核同意）|
| layer1_overridden | list[Issue] | Layer-1 误判（降级为 info）|
| model_id | String | 使用的 Claude 模型 id |
| generated_at | Timestamp | |

**PK/SK**：`TEAM#{team_id}` / `CRITIQUE#{generation_id}#{chapter_idx:05d}`

## E2. Issue

```python
class Issue(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: Literal["logic", "character", "style_drift", "consistency", "language"]
    excerpt: str
    comment: str
    layer: Literal["layer1", "layer2"] = "layer2"
```

## E3. CrossChapterConcern

```python
class CrossChapterConcern(BaseModel):
    concern_type: Literal["style_drift", "character_inconsistency", "plot_divergence"]
    chapters_involved: list[int]
    excerpt_pairs: list[tuple[str, str]]   # 跨章引用的对比片段
    comment: str
    severity: Literal["low", "medium", "high"]
```

---

## E4. ConsistencyReport（全局一致性）

| 字段 | 类型 | 说明 |
|---|---|---|
| report_id | UUID | |
| generation_id | UUID | |
| scanned_from_chapter | Int | 扫描起点 |
| scanned_to_chapter | Int | 扫描终点 |
| conflicts | list[ConflictItem] | 矛盾清单 |
| model_id | String | |
| generated_at | Timestamp | |

**PK/SK**：`TEAM#{team_id}` / `CONSISTENCY#{generation_id}#{to_chapter:05d}`

## E5. ConflictItem

```python
class ConflictItem(BaseModel):
    conflict_type: Literal[
        "character_state",     # 修为/存活/心情不连续
        "location_order",       # 地点顺序矛盾
        "timeline",             # 时间线反转
        "power_level",          # 修为等级反向
        "faction_affiliation",  # 派系变更无依据
        "other",
    ]
    chapter_range: tuple[int, int]
    description: str
    evidence: list[str]         # 原文引用
    suggestion: str             # 建议修改哪个章节
    severity: Literal["low", "medium", "high"]
    user_action: Literal["pending", "ignored", "rewrite_requested"] = "pending"
```

---

## E6. CriticEvent（EventBridge detail-type）

| detail-type | 触发方 | 订阅方 |
|---|---|---|
| `critic.report_ready` | U5 Critic Worker | ApiService SSE → 用户 UI |
| `consistency.report_ready` | U5 Consistency Worker | 同上 |

---

## E7. CriticContext（Worker 运行态）

```python
class CriticContext(BaseModel):
    generation_id: UUID
    chapter_idx: int
    team_id: UUID
    chapter_text: str              # 本章完整文本
    layer1_critique: dict          # 从 U4 Chapter 记录读取的 self_critique
    previous_chapters_summary: list[str]  # 最近 N 章摘要，用于跨章节评审
    style_vector: dict
    outline_item: dict
```

---

## E8. ConsistencyContext

```python
class ConsistencyContext(BaseModel):
    generation_id: UUID
    team_id: UUID
    scan_from: int
    scan_to: int
    chapters: list[str]            # 最近 N 章文本
    memory_facts: list[dict]       # 从 MemoryFacade 召回的相关 facts
    character_snapshots: dict      # 涉及人物的章节快照
```

---

## 移除的实体（原计划含 Moderation）

以下实体因 F4=D / F6=C 决策移除：
- ~~ModerationFlag~~
- ~~ModerationReport~~
- ~~ReviewQueueItem~~
- ~~ContentModerator UI 数据模型~~

相关 U1 基础设施（moderation-queue / worker-moderation Service）保留为 V2 预留，不激活。
