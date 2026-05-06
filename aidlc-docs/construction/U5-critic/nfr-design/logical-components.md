# U5 逻辑组件（Logical Components）

**Unit**：U5 Critic & Consistency
**阶段**：NFR Design
**日期**：2026-04-28

U5 几乎全部复用 U1 预建资源。本文列出 **新增/扩展** 元素。

---

## 1. SQS 队列

| 队列 | 消费者 | 状态 |
|---|---|---|
| `critic-queue` + DLQ | worker-critic | **复用 U1** |
| `consistency-queue` + DLQ | worker-consistency | **复用 U1** |
| `moderation-queue` + DLQ | — | **保留为 V2 预留**（未订阅事件）|

---

## 2. EventBridge Rules

| Rule | Pattern | Target | 状态 |
|---|---|---|---|
| `chapter-completed-to-critic` | `detail-type=generation.chapter.completed` | critic-queue | U1 预建 |
| `chapter-completed-to-moderation` | 同上 | moderation-queue | U1 预建，**保留不启用** |
| `consistency-trigger-to-queue` | `detail-type=consistency.trigger` | consistency-queue | **U5 新增** |

---

## 3. ECS Service

- `worker-critic`（U1 预建）：仅更新镜像
- `worker-consistency`（U1 预建）：仅更新镜像
- `worker-moderation`（U1 预建）：保留为 V2 预留，desired_count=0

---

## 4. DynamoDB 新 SK 模式

| SK | 用途 |
|---|---|
| `CRITIQUE#{generation_id}#{chapter_idx:05d}` | CritiqueReport |
| `CONSISTENCY#{generation_id}#{scan_to:05d}` | ConsistencyReport |
| `CONFLICT#{generation_id}#{conflict_id}` | 单独存储每 ConflictItem 便于独立操作（rewrite_attempts / frozen / user_action）|
| `GEN_SCAN#{generation_id}` | Consistency 扫描游标（记录 last_scan_to）|

全部复用 `novelgen_tenancy` 表，无需新表。

---

## 5. SSM Parameters（U5 新增 3 条）

```
/novelgen/{env}/config/consistency-interval = 10
/novelgen/{env}/config/conflict-rewrite-max-attempts = 3
/novelgen/{env}/config/critic-layer2-recent-summary-count = 5
```

---

## 6. CloudWatch Alarms（U5 新增 4 条）

| Alarm | Metric | 阈值 |
|---|---|---|
| `U5CriticDurationHigh` | `CriticDurationMs` P95 | > 60_000 ms |
| `U5ConsistencyDurationHigh` | `ConsistencyDurationMs` P95 | > 240_000 ms |
| `U5CriticFailureRateHigh` | `CriticFailureCount / CriticTotalCount` | > 5% |
| `U5ConflictLoopDetected` | `ConflictLoopDetected` | > 0（立即告警）|

---

## 7. IAM 策略扩展

worker-critic + worker-consistency Task Role（U1 已授予基础）补充：
- `bedrock:InvokeModel` / `Converse`（已有）
- `aoss:APIAccessAll` / `neptune-db:ReadDataViaQuery`（消费 U3 MemoryFacade）
- `events:PutEvents`（发 report_ready 事件）
- DynamoDB 读写 tenancy + jobs（U1 已授予）

---

## 8. API Service 扩展

新增路由（在 U4 generations 路由之外补充）：
- `GET /api/v1/generations/{gid}/chapters/{n}/critique`
- `GET /api/v1/generations/{gid}/consistency-reports?since_chapter={n}`
- `POST /api/v1/conflicts/{conflict_id}/ignore`
- `POST /api/v1/conflicts/{conflict_id}/rewrite`（调 U4 `/rewrite`）

---

## 9. 未实现资源（F4=D 决策）

- ~~ModerationReport SK 模式~~
- ~~ModerationFlag~~
- ~~Moderator 审核队列 UI~~
- ~~moderation-queue 事件订阅~~

U1 `moderation-queue` 与 `worker-moderation` 保留但不激活（desired_count=0），便于 V2 直接启用。

---

## 10. 资源总结

| 类别 | 新增 | 复用 U1 | 说明 |
|---|---|---|---|
| SQS | 0 | critic-queue / consistency-queue | moderation-queue V2 预留 |
| EventBridge Rule | 1 (consistency-trigger) | 2 | moderation Rule V2 预留 |
| ECS Service | 0 | worker-critic / worker-consistency | worker-moderation desired=0 |
| DDB SK 模式 | 4 | 复用 novelgen_tenancy | |
| SSM 参数 | 3 | — | |
| Alarms | 4 | — | |
| API 端点 | 4 | 嵌入 api-service | |

**U5 增量约 12 个元素**。
