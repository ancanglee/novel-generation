# U2 非功能设计模式（NFR Design Patterns）

**Unit**：U2 Ingestion Service
**阶段**：NFR Design
**日期**：2026-04-27

---

## 1. Parser 并发模式（D1=B asyncio 内并发 5）

### 1.1 Worker 内部调度
- 单个 Worker ECS Task 内启动 asyncio 事件循环
- Semaphore 控制并发解析数 = **5**
- 每个 SQS 消息领取一批（最多 5 条）一并处理

### 1.2 并发策略
```python
sem = asyncio.Semaphore(5)

async def handle_message(msg):
    async with sem:
        result = await run_in_threadpool(parser.parse, msg.body)
        ...
```

**注意**：解析库（pypdf、ebooklib 等）是 **CPU 密集型** 且多为同步阻塞。用 `run_in_threadpool` 让它们在 ThreadPoolExecutor 里并发，避免 asyncio 事件循环被阻塞。

### 1.3 Memory 限制
- 每个解析任务最大内存 ~500MB（200MB 文件 × 2.5x 峰值）
- 5 并发 × 500MB = 2.5GB，匹配 Task 规格（4096MB）+ 安全余量
- 内存超限 → OOM Killer；Auto Scaling 基于 CPU 60% 触发横向扩展

### 1.4 Graceful shutdown
- SIGTERM 后 30s 内完成在途任务（U1 R优雅停止同规范）
- 停止接收新 SQS 消息；已持有的最多 5 个继续处理

---

## 2. 搜索分组并行模式（D2=C）

### 2.1 分组结构
```
Group A — API 源（快且稳定）：
  - gutenberg (API)
  - ctext (HTML)
  - wikisource (API)
  → asyncio.gather，取最快返回的展示

Group B — 搜索引擎（慢且可能降级 Browser）：
  - baidu
  - bing
  → 独立 asyncio.gather，单独合并
```

### 2.2 分阶段返回给前端
- **阶段 1**（Group A 完成后，< 5s）：立即返回 Group A 候选；前端渲染 "公版书候选"
- **阶段 2**（Group B 完成后，< 30s）：追加 Group B 候选；前端追加 "搜索引擎候选（版权自负）"
- 通过 SSE 推送两阶段事件：`search.tier1.results` / `search.tier2.results`

### 2.3 取消语义
- Group A 完成后，若用户已点击某结果 → 取消 Group B（节约 Browser 成本）
- Worker 订阅 Job.cancel_requested 标志

---

## 3. Tier 2 降级模式（D3=C Worker + SFN 双层）

### 3.1 Worker 层（主决策）
```python
async def fetch_with_downgrade(url, source):
    # Tier 1
    try:
        resp = await tier1_http_fetch(url, timeout=10)
        if should_downgrade(resp):
            raise DowngradeSignal(reason=classify(resp))
        return extract_content(resp)
    except (DowngradeSignal, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        emit_metric("CrawlTierDowngraded", dims={"host": host(url), "reason": e.reason})
        # Tier 2
        return await tier2_browser_fetch(url, timeout=60)
    # 让未捕获异常向上冒泡到 SFN 兜底层
```

**降级触发条件**（business-rules R5.2）：
- HTTP 403 / 429 / 503
- 正文 < 200 字 或 JS-only 页面特征
- 超时 > 10s
- robots.txt disallow → **不降级**，抛 `RobotsDenied` 到上层

### 3.2 SFN 兜底层（Catch）
```yaml
FetchTask:
  Retry:
    - ErrorEquals: [States.TaskFailed, States.Timeout, UpstreamTransient]
      MaxAttempts: 2
      BackoffRate: 2.0
  Catch:
    - ErrorEquals: [RobotsDenied]
      Next: JobFailed
      ResultPath: $.error
    - ErrorEquals: [States.ALL]
      Next: TryBrowserOnce  # SFN 兜底 Browser Task
      ResultPath: $.error
  Next: ExtractContent
```

**职责分工**：
- Worker 主决策：覆盖 99% 场景（Tier 1 特征判断 → Tier 2）
- SFN Catch 兜底：网络异常、Worker crash、Pod 被 Spot 回收等罕见场景

---

## 4. crawl-cache Key 设计（D4=B 去 tracking）

### 4.1 归一化算法
```python
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
    "_ga", "spm", "share_source",
}

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    cleaned = [(k, v) for k, v in qs if k.lower() not in TRACKING_PARAMS]
    cleaned.sort()  # stable order
    new_q = urlencode(cleaned)
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path,
        parsed.params,
        new_q,
        "",  # drop fragment
    ))

def cache_key(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()
```

### 4.2 Key 存储
- S3 key：`teams/{team_id}/crawl-cache/{sha256}.html`
- 元数据：`teams/{team_id}/crawl-cache/{sha256}.meta.json`（原始 URL、fetched_at、source）
- 查询：先 HEAD 检查 `.html` 是否存在；存在即使用

### 4.3 缓存过期（继承 NFR-3.1）
- S3 Lifecycle：7 天过期自动删除
- 命中时比较 `fetched_at` 是否超过 7 天（双保险）

---

## 5. Browser UA 策略（D5=A）

### 5.1 UA 使用
- **Tier 1 HTTP 爬虫**：固定 UA `NovelGenBot/0.1 (+https://novelgen.example.com/bot)`
- **Tier 2 AgentCore Browser**：使用 Browser 默认真实 UA（例如 `Chrome/...`）

### 5.2 UA 分层的意义
- Tier 1 可识别身份，善意爬虫方式
- Tier 2 穿反爬是本意，真实 UA 更有效
- 合规边界：**robots.txt 校验在 Tier 1 前完成**，Tier 2 不用于绕过

### 5.3 Browser 会话管理
```python
async with agentcore_browser.session(timeout=60) as session:
    await session.navigate(url)
    await session.wait_for("domcontentloaded")
    await asyncio.sleep(2)  # 动态内容补渲染
    html = await session.content()
# 会话自动释放
```

---

## 6. 幂等与去重

### 6.1 Idempotency-Key（继承 U1 R7）
- 客户端 UUID header
- 服务端 DynamoDB `novelgen_*_jobs` 表：`PK=TEAM#{team}#IDEMPOTENCY`, `SK={key}`, TTL 24h

### 6.2 Title 去重（U2-F6=C）
- 查询：`query_by_sk_prefix("NOVEL#")` + filter by normalized_title
- 命中 → 409 `CONFLICT_TITLE_EXISTS`
- `?force=true` 覆盖

---

## 7. 多租户（继承 U1）

U2 不改变守卫层。所有数据访问经 storage-adapter：
- S3: `teams/{team_id}/novels/...` + `teams/{team_id}/crawl-cache/...`
- DynamoDB: `PK=TEAM#{team_id}`

---

## 8. 可靠性

### 8.1 失败分类
| 错误类 | Worker 处理 | SFN 处理 |
|---|---|---|
| `RobotsDenied` | raise to SFN | Catch → Job FAILED |
| `UpstreamTransient`（5xx 连续） | Worker 降级 Tier 2 | 兜底重试 2 次 |
| `DowngradeSignal`（403/429/JS） | Worker 降级 Tier 2 | — |
| `ParseError` | raise to SFN | Catch → Job FAILED, status=PARSE_FAILED |
| `BrowserSessionFailed` | raise to SFN | 兜底再试 Browser 1 次，再失败 → FAILED |

### 8.2 中断恢复
- Worker 被 Spot 回收：SFN execution 未收到 taskToken → Retry 重新派发到新 Task
- 新 Task 从 SQS 重新消费（visibility timeout 360s 保证）

---

## 9. 观测

### 9.1 关键 metric（业已在 business-rules R9.1 定义）
- 降级率 `CrawlTierDowngraded / (Tier1 + Tier2)`
- 解析时长 `IngestionDurationMs{format}`
- Browser 会话数 `BrowserSessionCount{source}`

### 9.2 追踪
- 每 Job 有 X 形 request_id（通过 observability-adapter ContextVar）
- 从 ApiService → Step Functions → Worker → AgentCore 全链路贯穿

---

## 10. 与 Application Design 模式映射

| AppDesign §服务编排 | U2 实现 |
|---|---|
| §2 异步长任务 | IngestionStateMachine + SQS + Worker |
| §6 事件驱动 | `novel.ingested` EventBridge → U3 |
| §8 多租户强隔离 | 继承 U1 storage-adapter |
| §新增：两级抓取 | §3 Tier 1 Worker + SFN Catch |
