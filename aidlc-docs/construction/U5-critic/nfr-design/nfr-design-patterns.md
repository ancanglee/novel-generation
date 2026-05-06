# U5 非功能设计模式（NFR Design Patterns）

**Unit**：U5 Critic & Consistency
**阶段**：NFR Design
**日期**：2026-04-28

---

## 1. Critic 触发模式（并行 fan-out）

### 1.1 EventBridge Rule
U1 已有 Rule `generation-chapter-completed-to-critic` → `critic-queue`。本阶段沿用。

### 1.2 Worker 消费
worker-critic 从 critic-queue 拉消息 → 调用 CriticAgent → 写 DDB `CRITIQUE#{gid}#{idx:05d}` → 发 `critic.report_ready` EventBridge。

---

## 2. Consistency 触发模式（D1=A 事件驱动）

### 2.1 ChapterAgent 发事件
U4 ChapterAgent 完成每章后：
```python
if idx % CONSISTENCY_INTERVAL == 0:
    await publisher.publish(GenerationEvent(
        detail_type="consistency.trigger",
        generation_id=..., team_id=..., chapter_idx=idx,
        payload={"scan_to": idx},
        event_id=f"{gid}:{idx}:consistency"
    ))
```

### 2.2 新增 EventBridge Rule
- `consistency-trigger-to-queue`：`detail-type=consistency.trigger` → `consistency-queue`

### 2.3 SSM 配置
- `/novelgen/{env}/config/consistency-interval`（默认 10，admin 可配）
- Worker 启动时读取 + 每 60s 刷新

---

## 3. 重写循环保护（D2=A）

### 3.1 ConflictItem.rewrite_attempts 字段
```python
class ConflictItem(BaseModel):
    ...
    rewrite_attempts: int = 0
    frozen: bool = False
```

### 3.2 冻结逻辑
用户点 Rewrite：
```python
if conflict.frozen:
    raise ConflictLoopFrozen(...)  # 409 "多次尝试未能解决"

conflict.rewrite_attempts += 1
if conflict.rewrite_attempts >= 3:
    conflict.frozen = True
    emit_metric("ConflictLoopDetected")
await trigger_chapter_rewrite(...)
```

### 3.3 UI 显示
frozen=True 的 ConflictItem 在 UI 上灰化 + 提示"已尝试 3 次未能解决，建议手动编辑"。

---

## 4. Critic Layer-2 复核组装（F1=B + D3=B）

### 4.1 输入构造
```python
async def build_critic_input(ctx: CriticContext) -> str:
    chapter = await s3.get_object(...)  # 本章完整文本
    layer1 = chapter_record["self_critique"]
    outline = await s3.get_object(outline_key)
    recent_summaries = [
        item["summary"] for item in outline["items"]
        if item["chapter_idx"] in range(ctx.chapter_idx - 5, ctx.chapter_idx)
    ]
    return render_prompt(
        chapter_text=chapter,
        layer1_critique=layer1,
        recent_summaries=recent_summaries,
        style_vector=ctx.style_vector,
    )
```

### 4.2 Token 预算
- 章节正文：~8k tokens
- Layer-1 critique：~500 tokens
- 5 章 summary × 100 字 ≈ 500 tokens
- 风格向量 + 指令：~500 tokens
- **总 input ~10k tokens**，Opus 4.7 context 200k 充裕

---

## 5. Consistency 增量扫描（F3=B）

### 5.1 扫描窗口
- `scan_from = last_scan_to + 1`（从 Generation 记录读）
- `scan_to = current_chapter`（触发时的章节号）
- 每次扫描 10 章 + Memory facts top_k=30

### 5.2 Memory 读取
```python
facts = await memory.recall(team_id, novel_id, query=f"chapters {scan_from}-{scan_to}", top_k=30)
for char_id in main_characters:
    snap = await memory.get_character(team_id, novel_id, char_id, at_chapter=scan_to)
```

### 5.3 Neptune 失败降级
- `memory.recall` 返回空 → ConsistencyAgent 仅做相邻章节文本 diff
- Report 标注 `memory_unavailable=true`

---

## 6. 并发与顺序

### 6.1 Critic 并发
同 Generation 不同章节的 Critic 可并行（不同 SQS 消息）。
- worker-critic Service Auto Scaling：基于 critic-queue 深度 > 10 → +1 task

### 6.2 Consistency 串行
同 Generation 的 Consistency 报告按 chapter 顺序生成（后一次扫描依赖前一次 `last_scan_to`）。
- 用 DDB conditional update 保证串行：`scan_to > last_scan_to`

---

## 7. 失败降级矩阵

| 层 | 失败处理 |
|---|---|
| Opus 4.7 Throttle | tenacity 指数退避 3 次 |
| SFN Task 级 | Retry 3 次，耗尽 Catch → minimal report |
| Memory (U3) 不可用 | 降级仅文本 diff |
| DDB 写失败 | SFN Retry 2 次 |
| EventBridge PutEvents 失败 | log + emit metric，不阻断业务 |

---

## 8. 可观测

### 8.1 Metric 发射点
- CriticAgent 开始 → 结束：`CriticDurationMs`
- ConsistencyAgent 开始 → 结束：`ConsistencyDurationMs`
- 每 CritiqueReport 写 `CriticScore{Severity}` 分桶
- 每 ConflictItem 写 `ConsistencyConflictCount{Type}`

### 8.2 Trace
复用 U3 的 AgentCore Observability。CriticContext 携带 request_id 贯穿。

---

## 9. ConflictItem 重写流程

ApiService 的 `POST /api/v1/conflicts/{conflict_id}/rewrite`：
1. 查 ConflictItem，若 frozen=true → 409
2. 自增 `rewrite_attempts`，检查是否达到 3 → 设 frozen
3. 调 U4 `POST /generations/{gid}/chapters/{n}/rewrite`，instruction 自动填充 ConflictItem 摘要
4. 返回 U4 job_id

---

## 10. 多租户

继承 U1/U3/U4。所有 DDB PK 带 `TEAM#{team_id}`；MemoryFacade 三层 filter。
