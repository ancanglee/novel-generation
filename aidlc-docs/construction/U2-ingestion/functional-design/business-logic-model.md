# U2 Business Logic Model

**Unit**：U2 Ingestion Service
**阶段**：Functional Design
**日期**：2026-04-27

---

## Flow 1. 文件上传（US-02-01）

**触发**：`POST /api/v1/novels/upload` (multipart)

1. ApiService 接收 multipart，校验 size ≤ 200 MB、MIME 白名单（R1.1, R1.3）
2. 计算 `sha256(body)`；查 idempotency_key 缓存（R7.1）；命中则直接返回原 novel_id
3. 归一化 title，查重（R6.2）；命中且无 `force=true` → 409 带 existing_novel_id
4. 创建 `Novel` 记录（status=INGESTING），分配 novel_id，写 upload 临时 S3 key
5. 创建 Job（type=INGESTION, kind=upload），启动 IngestionStateMachine
6. 返回 `{novel_id, job_id, status: INGESTING}`
7. Step Functions → SQS → IngestionWorker：
   a. 按 MIME 派发 parser → ParsedDocument（R2）
   b. 章节切分（R3 启发式；confidence<0.6 触发 LLM）
   c. 写 S3：`raw.md` + `chapters/{idx:05d}.md`
   d. 写 DynamoDB：Novel.status=INGESTED + Chapter 元数据
   e. 发 EventBridge 事件 `novel.ingested`
8. 前端通过 SSE 订阅 Job 进度

**失败分支**：
- 解析失败 → Novel.status=PARSE_FAILED，Job FAILED，错误码写回 Job
- S3 写失败 → 重试 3 次（U1 StepFunctions Retry），耗尽标记 FAILED

---

## Flow 2. 公版书搜索下载（US-02-02, U2-F3=D；两级抓取）

**触发**：`POST /api/v1/novels/download` body=`{title: "...", engines?: ["gutenberg","ctext","wikisource","baidu","bing"]}`

1. ApiService 校验 title 非空
2. 启动 SearchWorkflow（Step Functions）
3. Worker 按源顺序执行搜索（R4.1），每源采用**两级策略**（R4.2）：
   ```
   for source in [gutenberg, ctext, wikisource, baidu, bing]:
       # Tier 1：HTTP 爬虫
       results = try_http_crawler(source, title, timeout=10s)
       if results is None or empty:
           downgrade_reason = classify_failure(...)
           if downgrade_reason in {'403', '429', 'js-only', 'timeout'}:
               emit_metric('SearchTierDowngraded', {source})
               # Tier 2：降级 AgentCore Browser
               results = try_agentcore_browser(source, title, timeout=60s)
           elif downgrade_reason == 'robots-disallow':
               results = []  # 硬拒，不降级
       merge(all_results, results)
   ```
4. 跨源去重、按相关性排序；返回候选 `{results: [...]}`（每条带 source, title, url, snippet, warning）
5. 前端渲染待选择列表（Baidu/Bing 结果附 ⚠️ "版权自负"）
6. 用户点击某一结果 → `POST /api/v1/novels/download/confirm` body=`{title, source, url}`
7. 写 audit（R9.2 强制，记录搜索词、来源、目标 URL）
8. 复用 Flow 3 URL 抓取（同样两级策略）
9. 抓取结果作为普通 Novel 入库（source_type = PUBLIC_DOMAIN 或 SEARCH_ENGINE）

**合规**：Baidu/Bing 结果必须用户主动点击。robots.txt disallow 的目标不允许通过 Browser 绕过。

---

## Flow 3. URL 抓取（US-02-03；两级抓取）

**触发**：`POST /api/v1/novels/crawl` body=`{url: "https://..."}`

1. ApiService 校验 URL 合法
2. 拉取 host `/robots.txt`（TTL 缓存 24h）
3. 检查目标 path 是否 Allowed（R5.1）；不允许 → 403（**不降级 Browser**）
4. 启动 CrawlWorkflow（IngestionStateMachine 变种）
5. Worker 按 R5.2 两级策略抓取：
   ```
   # Tier 1：HTTP 爬虫
   try:
       resp = httpx.get(url, headers={'User-Agent': 'NovelGenBot/0.1 (+...)'}, timeout=10)
       wait(crawl_delay)
       content = trafilatura.extract(resp.text)
       if is_js_only(content) or resp.status in (403, 429, 503):
           raise DowngradeSignal(reason='tier1-insufficient')
   except DowngradeSignal as d:
       emit_metric('CrawlTierDowngraded', {host})
       # Tier 2：AgentCore Browser
       with agentcore_browser.session(timeout=60) as sess:
           sess.navigate(url)
           sess.wait_dom_ready()
           content = trafilatura.extract(sess.html())
   ```
6. 如果是目录页，遍历章节链接逐页抓取（每页独立走两级策略；R5.3）
7. 合成 Markdown → 章节切分（R3）
8. 抓取结果缓存到 `teams/{team_id}/crawl-cache/sha256(url).html`（24h TTL，R5.6）
9. 入库（同 Flow 1 步骤 c–e）
10. 前端 SSE 订阅进度

**失败处理**：Tier 2 也失败 → Job FAILED，错误码 `UPSTREAM_SOURCE_UNREACHABLE`，UI 显示"此页面无法抓取，请尝试其他 URL 或直接上传文件"。

---

## Flow 4. 小说列表（US-02-04）

**触发**：`GET /api/v1/novels`

1. `verify_principal` → Principal
2. `DynamoDBAdapter.query_by_sk_prefix(principal.team_id, "NOVEL#")` 拿到当前 team 的 novel 元数据
3. 按 `created_at DESC` 排序，分页（默认 20）
4. 返回 `NovelSummary[]`

**非 Admin**：只能看自己 team。Admin 可带 `?team_id=xxx` 查询任意 team。

---

## Flow 5. 章节切分 LLM 辅助（R3.3 子流程）

**触发**：启发式 confidence < 0.6

1. 从 Markdown 中抽取 3 段样本（前 30% / 中 30% / 后 30% 各 4KB）
2. 构造 prompt：
   ```
   以下是小说节选。请识别章节标题的正则模式（可能形如"第 X 章"或"Chapter N"或其他）。
   如果识别成功，返回 {"pattern": "...", "examples": [...]}
   如果无法识别，返回 {"pattern": null}
   ```
3. 调 Bedrock Claude Haiku 4.5（`ModelConfig[chapter_split]`，admin 可覆盖）
4. 回调结果为 regex，重新扫全文
5. 仍失败 → 整本作为单章（warning）

---

## Flow 6. robots.txt 缓存

**触发**：URL 抓取前

1. 解析目标 URL 的 host
2. 查 `TTLCache[host]`（24h）；命中返回
3. 未命中：`GET https://{host}/robots.txt`，解析成 `RobotsPolicy`
4. 失败（404 / timeout）→ **默认放行**（记 warning，写 metric `RobotsTxtMissing`）
5. 缓存结果

---

## Flow 7. 上传重试与幂等

**场景**：客户端网络抖动导致重复提交

1. 客户端首次调用时生成 UUID 作为 `Idempotency-Key` header
2. ApiService 查 `(team_id, idempotency_key)` → novel_id 映射（DynamoDB `novelgen_*_jobs`，TTL 24h）
3. 命中 → 返回先前结果（200）
4. 未命中 → 走正常流程，成功后写入映射
