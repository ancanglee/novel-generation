# U4 非功能设计模式（NFR Design Patterns）

**Unit**：U4 Generation Agents
**阶段**：NFR Design
**日期**：2026-04-28

---

## 1. SSE 端点双路径（D1=C）

### 1.1 两路径并存
| 路径 | 用途 |
|---|---|
| `/api/v1/jobs/{job_id}/stream` | 通用 job 流（含 outline 生成 / analysis / generation）|
| `/api/v1/generations/{gid}/chapters/{n}/stream` | 聚焦单章生成，便于前端按章显示 |

### 1.2 共享底层实现
两路径共用同一 SSE 中继逻辑（ApiService `sse_relay`），仅 filter 条件不同：
- per-job：`event.detail.job_id == job_id`
- per-chapter：`event.detail.generation_id == gid AND event.detail.chapter_idx == n`

### 1.3 Last-Event-ID 支持
客户端断线重连时通过 `Last-Event-ID` header 恢复，后端从 EventBridge Archive 拉取该 id 之后的事件回放。

---

## 2. EventBridge Archive（D2=A）

### 2.1 配置
- Archive 名称：`novelgen-gen-archive-{env}`
- 关联 default bus
- Retention：**7 天**
- Event pattern：`source=['novelgen.generation']`

### 2.2 重放路径
SSE 客户端发 `Last-Event-ID: abc` → ApiService：
1. 查询 Archive 中 `event_id > abc` 的事件
2. 按顺序 replay 给客户端
3. 继续订阅 live 事件

### 2.3 成本
~$0.10 / GB / 月，预估 7 天 events < 10 GB，月成本 **< $1**。

---

## 3. 显式循环 Choice 串行（D3=B）

### 3.1 放弃 Map state
虽然 Map state MaxConcurrency=1 理论可串行，但 SFN ASL 中 concurrency 参数易被误改；改用显式循环更清晰。

### 3.2 Choice 循环骨架
```
StartAt: InitLoop
States:
  InitLoop: Pass → sets i=1
  LoopGuard: Choice
    if i > chapter_count → DoneAllChapters
    else → GenerateChapter
  GenerateChapter: Task (SQS WAIT_FOR_TASK_TOKEN)
    → IncrementCounter
  IncrementCounter: Pass → i = i + 1 → LoopGuard
  DoneAllChapters: ...
```

### 3.3 Cancel 支持
每次 LoopGuard 检查时额外读 Job.cancel_requested；为 true → Next=JobFailed/Canceled。

---

## 4. OutlineReviewAgent 独立 review-queue（D4=A）

### 4.1 新增 SQS 队列
- `review-queue` + `review-dlq`
- 参数：Visibility Timeout 180s / maxReceive 3

### 4.2 独立 Worker？
两种实现：
- **A**：扩展 `worker-generation` 的消费循环，同时拉 review-queue + generation-queue（msg kind 派发）
- **B**：新建 `worker-review` 独立 Service

**推荐**：扩展现有 worker-generation（增量消费一个额外队列开销可忽略；避免新 ECS Service 与镜像）。

### 4.3 触发
用户 PUT /outline → API 写 DDB → 发送 review 消息到 review-queue → worker 异步处理。

---

## 5. 启动时缓存风格 Memory（D5=B）

### 5.1 缓存结构
GenerationContext 字段：
```python
style_reference_excerpts: list[str]  # 3 段文本，Generation 启动时 hybrid_search 得到
```

### 5.2 生成时机
ChapterStateMachine 的 `InitLoop` Pass state 中调用一次 Lambda `load-generation-context`：
- 读 Generation.style_vector
- `hybrid_search(top_k=3)` 召回 3 段
- 写入 DDB `GEN_CONTEXT#{gid}` 行 24h TTL

### 5.3 Worker 每章消费
Chapter Worker 读 `GEN_CONTEXT#{gid}` 拿到 style_reference_excerpts 拼到 system prompt；无需每章再 hybrid_search。

### 5.4 成本收益
减少 50 章 × 1 次 hybrid_search 调用（每次含 embed + knn + bm25），约节省 $0.5 + 3-5 秒。

---

## 6. Cancel 响应（NFR-1.2 10s）

### 6.1 TTLCache 8s
进程内 `TTLCache(maxsize=1000, ttl=8)` 缓存 `cancel_requested` 读结果。

### 6.2 Worker 检查点
```python
def on_stream_chunk(chunk):
    if _cancel_cache.get(job_id) is None:
        _cancel_cache[job_id] = ddb_read(job_id).cancel_requested
    if _cancel_cache[job_id]:
        stream.close()
        mark_canceled()
        return
    yield chunk
```

### 6.3 SSE 中继也读
ApiService SSE 也应检查 cancel_requested，收到时发 `canceled` 事件给浏览器。

---

## 7. 重写版本管理（NFR-3.1）

### 7.1 S3 Versioning
`novelgen-novels-{env}` bucket 原已启用 Versioning。

### 7.2 NoncurrentVersionExpiration
```yaml
LifecycleRule:
  Id: U4ChapterRewriteVersions
  Prefix: teams/*/generations/*/chapters/
  NoncurrentVersionExpiration:
    NewerNoncurrentVersions: 10
    NoncurrentDays: 30
```

保留最近 10 个非当前版本；超过 30 天的旧版本自动删除。

---

## 8. 模式 Prompt 注入

### 8.1 Prompt 组装顺序
```
System Prompt Sections:
  1. Mode header (from clean_room.md or continuation.md)
  2. Style Injection Block (vector prefix + 3 cached reference excerpts)
  3. Memory Context (20 facts from recall)
  4. Outline Context (this chapter's outline_item + main characters + locations)
  5. Previous Chapter Tail (last 500 chars)
```

### 8.2 Token 预算
总 system prompt < 40k tokens；Claude Sonnet 4.7 context 200k，充裕。

---

## 9. 可观测（U4 扩展 U1/U3）

### 9.1 trace 关联
每 chapter task 的 request_id = `{generation_id}:{chapter_idx}`，SSE 事件携带。

### 9.2 Metric 发射点
- Bedrock stream first token 时间 → `ChapterTTFTMs`
- 章节总耗时 → `ChapterGenerationMs`
- Cancel 到 stream 关闭 → `CancelResponseMs`

---

## 10. 失败分类

| 错误 | Worker 处理 | SFN 处理 |
|---|---|---|
| Bedrock ThrottlingException | tenacity 重试 | retry 2 次 |
| JSON schema 违规（Self-Critique）| warning，不阻断 | — |
| S3 write failure | 重试 3 次 | catch → FAILED |
| Memory recall failure | 空 facts + warning | — |
| Cancel | 关 stream + 部分保存 | JobFailed |
