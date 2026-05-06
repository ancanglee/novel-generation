# U2 逻辑组件（Logical Components）

**Unit**：U2 Ingestion Service
**阶段**：NFR Design
**日期**：2026-04-27

U2 绝大多数基础设施继承 U1。本文列出 **U2 新增 / 修改** 的逻辑组件。

---

## 1. 新增 SQS 队列

加入 U1 `MessagingStack` 的队列列表：

| 队列 | 消费者 | DLQ |
|---|---|---|
| `ingestion-queue` | worker-ingestion | `ingestion-dlq` |

参数：
- Visibility Timeout = **360s**（3min 解析超时 + 60s 余量）
- Max Receive Count = 3
- Retention = 4 days
- Batch size（Worker 拉取）= 5（配合 D1=B asyncio 5 并发）

---

## 2. 新增 ECS Service

加入 U1 `ComputeStack`：

| Service | TaskDef CPU / Mem | 数量 | Capacity Provider |
|---|---|---|---|
| `worker-ingestion` | 2048 / 4096 MB | min 1 / max 5 | FARGATE_SPOT 混合（4:1） |

Auto Scaling：
- `ingestion-queue` `ApproximateNumberOfMessagesVisible > 10` → +1 task
- 空闲 10min → -1

---

## 3. 扩展 IngestionStateMachine

填充 U1 骨架，实际 ASL：

```
UpdateJobRunning
    ↓
Parallel [ResolveInput, CheckDuplicates]
    ├─ ResolveInput: 派发到 SQS(ingestion-queue) via WAIT_FOR_TASK_TOKEN
    │     → Worker: parse + extract chapters + s3 write + ddb write
    └─ CheckDuplicates: query DDB for normalized_title match
    ↓
MergeResults
    ↓
PublishNovelIngested (EventBridge)
    ↓
UpdateJobSucceeded
```

Retry/Catch 按照 NFR Design §3.2。

---

## 4. 新增 EventBridge Rule

加入 U1 `MessagingStack`：

```yaml
NovelIngestedRule:
  event_pattern:
    source: ["novelgen.ingestion"]
    detail-type: ["novel.ingested"]
  targets:
    - ApiService SSE 转发
    - (U3) worker-analysis（当 U3 落地时自动触发分析）
```

---

## 5. S3 新增前缀

在 U1 `novelgen-novels-dev` bucket 复用：

| 前缀 | 用途 | Lifecycle |
|---|---|---|
| `teams/{team_id}/uploads/tmp/` | 上传临时文件 | 1 day expire |
| `teams/{team_id}/novels/{novel_id}/raw.md` | 整本 Markdown | 随 bucket 策略 |
| `teams/{team_id}/novels/{novel_id}/chapters/{idx:05d}.md` | 每章 Markdown | 同上 |
| `teams/{team_id}/crawl-cache/{sha256}.html` | URL 抓取缓存 | **7 day expire**（NFR-3.1）|
| `teams/{team_id}/crawl-cache/{sha256}.meta.json` | 缓存元信息 | 同上 |

在 CDK DataStack 中扩展 `novels_bucket.lifecycle_rules` 添加上述规则。

---

## 6. 新增 CloudWatch Alarms

加入 U1 `ObservabilityStack`：

| Alarm | Metric | 阈值 |
|---|---|---|
| `U2CrawlDowngradeRateHigh` | `CrawlTierDowngraded / (sum of all)` | > 30% (5 min) |
| `U2SearchDowngradeRateHigh` | `SearchTierDowngraded / (sum of all)` | > 30% (5 min) |
| `U2BrowserOverused` | `BrowserSessionCount` | > 100 / hour |
| `U2IngestionTimeoutP95` | `IngestionDurationMs` P95 | > 120_000 ms (2 min) |
| `U2RobotsBlockedHigh` | `RobotsTxtBlocked` | > 20 / 5 min |

---

## 7. 新增 IAM 策略

### 7.1 worker-ingestion Task Role（继承 U1 worker-analysis 角色的基础策略）
额外授予：
- `bedrock-agentcore:InvokeBrowser*`（Tier 2 Browser）
- `bedrock:InvokeModel` （章节切分 LLM 辅助）
- 对 `ingestion-queue` 的 ReceiveMessage/DeleteMessage

### 7.2 API Service 扩展策略
保持不变（U1 已授予 StartExecution / DynamoDB RW / S3 RW）。

---

## 8. 新增 SSM Parameters

```
/novelgen/{env}/config/max-upload-size-mb = 200
/novelgen/{env}/config/parse-timeout-seconds = 180
/novelgen/{env}/config/browser-session-timeout-seconds = 60
/novelgen/{env}/config/crawl-cache-ttl-days = 7
/novelgen/{env}/config/search-sources-enabled = "gutenberg,ctext,wikisource,baidu,bing"
/novelgen/{env}/config/crawler-user-agent = "NovelGenBot/0.1 (+https://novelgen.example.com/bot)"
```

Admin 可在线调整，Worker 每 60s 轮询最新值。

---

## 9. 新增 Docker 镜像

| Repo | Base | 额外 apt 依赖 | 预估大小 |
|---|---|---|---|
| `novelgen/worker-ingestion` | python:3.12-slim | libxml2, libxslt1-dev, poppler-utils | ~250 MB |

---

## 10. 不需要修改的 U1 资源

| 资源 | 原因 |
|---|---|
| VPC / Subnets / NAT | U2 Worker 在已有 private subnet |
| Cognito User Pool | U2 复用 Principal |
| DynamoDB 4 表 | 只是新增行，不改 schema |
| ALB / CloudFront | 路由规则 `/api/v1/novels/*` 已覆盖 |
| Secrets Manager / SSM | 仅在 §8 新增 SSM 参数 |

---

## 11. 资源数量总结

| 类别 | 新增 | 继承 U1 | 合计 |
|---|---|---|---|
| SQS 队列 | 2 (ingestion + DLQ) | 10 | 12 |
| ECS Service | 1 (worker-ingestion) | 8 | 9 |
| Step Functions 状态机 | 0（填充现有骨架） | 5 | 5 |
| EventBridge Rule | 1 (NovelIngestedRule) | 3 | 4 |
| CloudWatch Alarm | 5 | 10 | 15 |
| SSM Parameters | 6 | 10+ | 16+ |
| ECR Repos | 1 (worker-ingestion) | 8 | 9 |
| Docker 镜像 | 1 | — | — |
| IAM 策略 | worker-ingestion 额外 2 条 | 8 角色 | 8 |

**U2 总体新增：约 10 个新基础设施元素**。
