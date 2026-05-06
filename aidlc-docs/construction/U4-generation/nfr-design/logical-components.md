# U4 逻辑组件（Logical Components）

**Unit**：U4 Generation Agents
**阶段**：NFR Design
**日期**：2026-04-28

U4 继承 U1 预建资源。本文列出 U4 **新增 / 扩展** 元素。

---

## 1. SQS 队列

扩展 U1 `MessagingStack`：

| 队列 | 消费者 | DLQ | 新增/复用 |
|---|---|---|---|
| `generation-queue` | worker-generation | `generation-dlq` | **复用 U1** |
| `review-queue` | worker-generation (扩展) | `review-dlq` | **新增**（D4=A）|

**review-queue 参数**：Visibility Timeout 180s / maxReceive 3 / Retention 4 days

---

## 2. ECS Service

**复用 U1 `worker-generation`**，镜像内加入：
- U4 agents 代码（Outline/Chapter/SelfCritique/ModeRouter/OutlineReview）
- SQS 消费循环同时读 generation-queue + review-queue（根据 msg kind 分派）

无需新 Service。

---

## 3. Step Functions

填充 U1 `ChapterStateMachine` 骨架：

```
StartAt: LoadGenerationContext (Lambda)
States:
  LoadGenerationContext: Task (Lambda: load-generation-context)
    - Reads Generation row
    - Calls MemoryFacade.hybrid_search(top_k=3) for style excerpts
    - Writes GEN_CONTEXT#{gid} to DDB (24h TTL)
    → InitLoop
  InitLoop: Pass → sets i=1
  LoopGuard: Choice
    - if cancel_requested → JobCanceled
    - if i > chapter_count → JobSucceeded
    - else → GenerateChapter
  GenerateChapter: Task (SQS WAIT_FOR_TASK_TOKEN → generation-queue)
    → IncrementCounter
  IncrementCounter: Pass → i = i + 1 → LoopGuard
  JobSucceeded: DynamoDB UpdateItem status=SUCCEEDED → End
  JobCanceled: DynamoDB UpdateItem status=CANCELED → End
  JobFailed: DynamoDB UpdateItem status=FAILED → Fail
```

OutlineStateMachine 独立骨架（U1 预定义），由 OutlineAgent 填充。

---

## 4. EventBridge

### 4.1 新增 Archive
- `novelgen-gen-archive-{env}`
- Bus: default
- Retention: 7 days
- Event pattern: `{"source": ["novelgen.generation"]}`

### 4.2 新增 Rules
- `generation-chapter-completed-to-critic`（已在 U1 预建）→ critic-queue
- `generation-chapter-completed-to-moderation`（已在 U1 预建）→ moderation-queue

---

## 5. DynamoDB 新 SK 模式

复用 `novelgen_jobs` 与 `novelgen_tenancy` 表：

| SK | 用途 | TTL |
|---|---|---|
| `GEN#{generation_id}` | Generation 主记录 | 无 |
| `GEN_CHAPTER#{generation_id}#{idx:05d}` | Chapter 状态 | 无 |
| `GEN_CONTEXT#{generation_id}` | Worker 缓存（风格参考 + 前一章末尾）| 24h |
| `OUTLINE_ADVICE#{generation_id}#v{N}` | F3=B LLM 校验建议 | 30 天 |

---

## 6. S3 新前缀

| 前缀 | 用途 | Lifecycle |
|---|---|---|
| `teams/{tid}/generations/{gid}/outline.v{N}.json` | 大纲版本化 | 无 |
| `teams/{tid}/generations/{gid}/chapters/{idx:05d}.md` | 章节文本 | 保留 10 noncurrent + 30 天降冷 |
| `teams/{tid}/generations/{gid}/chapters/{idx:05d}.partial.md` | Cancel 部分保存 | 30 天过期 |

---

## 7. 新增 Lambda

### 7.1 `load-generation-context`
- Runtime: Python 3.12
- 职责：ChapterStateMachine 第一步调用
- 操作：读 Generation → 调 MemoryFacade.hybrid_search → 写 GEN_CONTEXT 行
- IAM：DDB RW + bedrock-runtime:InvokeModel（embed）+ aoss:APIAccessAll + neptune-db:ReadDataViaQuery

---

## 8. SSM Parameters（U4 新增 5 条）

```
/novelgen/{env}/config/chapter-rewrite-max = 5
/novelgen/{env}/config/cancel-cache-ttl-seconds = 8
/novelgen/{env}/config/chapter-target-words-default = 3000
/novelgen/{env}/config/outline-review-timeout-seconds = 120
/novelgen/{env}/config/chapter-retention-versions = 10
```

---

## 9. CloudWatch Alarms（U4 新增 3 条）

| Alarm | Metric | 阈值 |
|---|---|---|
| `U4ChapterTTFTHigh` | `ChapterTTFTMs` P95 | > 3000 ms |
| `U4ChapterGenerationSlow` | `ChapterGenerationMs` P95 | > 60_000 ms |
| `U4CancelResponseSlow` | `CancelResponseMs` P95 | > 10_000 ms |

---

## 10. IAM 扩展

`worker-generation` Task Role 补充：
- `bedrock:InvokeModelWithResponseStream`（已有）
- `aoss:APIAccessAll` / `neptune-db:ReadDataViaQuery`（调 MemoryFacade）
- `events:PutEvents`（流式事件发布）
- `sqs:ReceiveMessage` on review-queue 新增

---

## 11. 资源总结

| 类别 | 新增 | 扩展 U1 | 说明 |
|---|---|---|---|
| SQS | 2 (review + DLQ) | generation-queue 复用 | |
| ECS Service | 0 | worker-generation 镜像更新 | |
| Step Functions | 0 | 填充 ChapterStateMachine + OutlineStateMachine | |
| EventBridge Archive | 1 | — | 新增 |
| DDB 新 SK 模式 | 4 | 复用表 | |
| S3 前缀 | 3 | 复用 bucket | |
| Lambda | 1 | — | load-generation-context |
| SSM 参数 | 5 | — | |
| Alarms | 3 | — | |

**U4 增量约 14 个基础设施元素**。
