# U2 Business Rules

**Unit**：U2 Ingestion Service
**阶段**：Functional Design
**日期**：2026-04-27

---

## R1. 上传约束

### R1.1 文件大小上限（U2-F4=B）
- 单文件 ≤ **200 MB**
- 超限 → 422 `VALIDATION_FILE_TOO_LARGE`

### R1.2 支持格式（Q3=D）
TXT / EPUB / PDF / DOCX / Markdown / HTML（预留）

### R1.3 MIME 白名单
只接受以下 MIME：
- `text/plain`（TXT / MD）
- `application/epub+zip`
- `application/pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `text/markdown`, `text/html`

### R1.4 内容哈希
- 解析后的 **Markdown 正文** 计算 SHA-256，写入 `Novel.content_sha256`
- **不用于去重**（U2-F6=C 采用标题去重）
- 仅用于 upload 幂等（Idempotency-Key 与 sha256 双重校验）

---

## R2. 格式派发与解析（U2-F1=A 独立 parser）

### R2.1 派发表
```
text/plain                -> TxtParser
text/markdown             -> MarkdownParser  (pass-through)
application/epub+zip      -> EpubParser      (uses ebooklib)
application/pdf           -> PdfParser       (uses pypdf + pdfplumber fallback)
application/vnd...docx    -> DocxParser      (uses python-docx)
text/html                 -> HtmlParser      (uses trafilatura)
unknown                   -> 422 UNSUPPORTED_FORMAT
```

### R2.2 Parser 契约
每个 parser 实现同一协议：
```python
class DocumentParser(Protocol):
    def parse(self, content: bytes, filename: str | None = None) -> ParsedDocument: ...
```

### R2.3 解析失败
- 解析异常 → `Novel.status = PARSE_FAILED`，在 `warnings` 字段填具体错误
- 用户可在 UI 重新上传或查看错误原因

---

## R3. 章节切分（U2-F2=B 启发式 + LLM 辅助）

### R3.1 启发式优先
按下列 pattern 顺序扫描 Markdown，首个匹配即视为章节头：
1. `# ` / `## ` Markdown heading（heading_level=1/2）
2. `第\s*[一二三四五六七八九十百千万零〇\d]+\s*章.*` 中文章节标题
3. `Chapter\s+\d+.*` 英文章节标题
4. `Part\s+\d+.*` / `卷\s*[一二三\d]+.*`

### R3.2 启发式置信度
- 若识别到 **≥ 5** 个候选且间隔大致均匀（标准差 < 3× 平均间距），confidence = 0.95
- 若识别到 **< 5** 或间隔极不均匀，confidence = 0.4，触发 R3.3

### R3.3 LLM 辅助（confidence < 0.6 时启用）
- 抽样前 30%、中 30%、后 30% 三段各 4KB
- 用 Claude Haiku 4.5 识别章节标题 pattern
- LLM 返回 regex → 重新扫全文
- LLM 若无法识别 → 整本作为单章（warning "章节切分失败，按单章处理"）

### R3.4 章节后处理
- 章节文字 < 200 字 → 与前章合并（避免误识别 TOC 项）
- 章节文字 > 50000 字 → 警告（可能切分不充分）
- 每个章节单独写入 `chapters/{idx:05d}.md`

---

## R4. 公版书搜索（U2-F3=D 扩展到搜索引擎）

### R4.1 搜索源优先级
```
1. Project Gutenberg    (首选 HTTP API)
2. ctext.org            (首选 HTTP 爬取)
3. Wikisource 中文       (首选 HTTP API)
4. Baidu 搜索            (首选 HTTP 爬取，失败降级 AgentCore Browser)
5. Bing 搜索             (首选 HTTP 爬取，失败降级 AgentCore Browser)
```

### R4.2 两级抓取策略（所有源通用，基于用户反馈）
对**每一个搜索源**采用"先爬虫 → 失败降级 Browser"的两级策略：

**Tier 1（轻量 HTTP 爬虫，优先）**：
- 使用 `httpx` + `trafilatura` + 目标站的公开 API/HTML 结构
- 固定 UA `NovelGenBot/0.1 (+...)`、遵守 robots.txt、`Crawl-delay` 等待
- 适用：结构稳定、无 JS 渲染、无反爬验证的站点

**Tier 2（AgentCore Browser，降级）**：
以下任一条件触发降级到 AgentCore Browser：
- Tier 1 返回 HTTP 403 / 429 / 503（反爬拦截）
- Tier 1 返回结果为 JS-only 页面（正文抽取 < 200 字或包含"请开启 JS"字样）
- Tier 1 命中 robots.txt disallow（不降级 — 直接放弃该源，不用 Browser 绕过）
- Tier 1 超时 > 10 秒

**降级后的行为**：
- AgentCore Browser 会话仍然遵守 robots.txt（不豁免合规）
- 每次降级写 metric `SearchTierDowngraded{source}`，admin 可监控反爬趋势
- 如 Browser 也失败 → 返回该源 0 结果，继续下一个源

### R4.3 搜索引擎扩展（Baidu / Bing）的合规约束
鉴于搜索引擎结果可能**指向受版权保护**的内容：
- 搜索结果展示 **标题 + URL + 摘要**（不展示正文长片段），由用户点击确认后才执行下载
- 每条搜索结果附 ⚠️ "版权自负" 提示
- 下载执行由 URL 抓取流程处理（R5），遵守 robots.txt
- 下载时必须写 audit log（即使 U1-F4=A 只对 Admin 操作审计，搜索引擎下载也强制 audit）
- 搜索结果**不得**自动选最优 → 必须用户主动点击

### R4.4 搜索结果去重
跨源合并结果，按 (normalized_title + author) 去重。

### R4.5 AgentCore Browser 使用约束
- 每次 Browser 会话的 timeout = 60s
- 并发上限：每账号 ≤ 3 个 Browser session（AgentCore 配额约束）
- 会话结束后立即释放（降低成本）
- 每会话成本记入 `NovelGen/BrowserSessionCount{source}` metric

---

## R5. URL 抓取（U2-F5=A 遵守 robots.txt；含两级抓取）

### R5.1 robots.txt 检查
- 每次抓取前先拉取目标 host 的 `/robots.txt`（TTL 缓存 24h）
- 如果目标 path 被 `User-agent: *` 或具体 UA 禁止 → **拒绝抓取**，返回 403 `FORBIDDEN_ROBOTS_DISALLOWED`
- 遵守 `Crawl-delay` 指令（最小 1s，最大 30s）
- **robots disallow 的路径不允许通过 Browser 绕过**

### R5.2 两级抓取策略（与 R4.2 对齐）

**Tier 1 — HTTP 爬虫**（优先）：
- `httpx` GET URL，UA=`NovelGenBot/0.1 (+https://novelgen.example.com/bot)`
- 超时 10s
- 用 `trafilatura` / `readability-lxml` 提取主正文
- 保留 heading 结构

**降级判定**（触发 Tier 2）：
| 条件 | 行为 |
|---|---|
| HTTP 4xx（403/429）| 降级 Browser |
| HTTP 5xx 连续 2 次 | 降级 Browser |
| 正文抽取 < 200 字 或 命中"启用 JS"标志 | 降级 Browser |
| 明显 JS 渲染特征（空 body + SPA 框架标签）| 降级 Browser |
| 总超时 > 10s | 降级 Browser |
| robots.txt disallow | **不降级** — 直接放弃，返回 403 |

**Tier 2 — AgentCore Browser**（降级）：
- 通过 AgentCore Browser 会话渲染页面、执行 JS、等待 DOM 稳定
- 仍遵守 robots.txt（该步骤在进入 Browser 前完成）
- 抽取 DOM 正文后传回 Worker，继续走 Tier 1 的 trafilatura 抽取流程
- 每次降级写 metric `CrawlTierDowngraded{host}`

### R5.3 多页面目录处理
- 如果抓取结果是目录页（包含 ≥ 5 个章节链接），按链接顺序逐页抓取
- 每页独立判定 Tier 1 / Tier 2（避免为一页失败整目录降级）
- 每页间插入 `Crawl-delay` 等待
- 失败中断则标记已抓取部分为"不完整"

### R5.4 User-Agent
固定使用 `NovelGenBot/0.1 (+https://novelgen.example.com/bot)`，可识别。
AgentCore Browser 会话的默认 UA（真实浏览器 UA）在反爬场景下自然生效。

### R5.5 合规兜底
- 搜索引擎来源（Baidu/Bing）的下载，**必须**走 R5 完整 robots.txt 校验流程
- 无论 Tier 1 还是 Tier 2，robots.txt disallow 都是硬拒绝
- Browser 不得用于绕过 robots（即使技术上可行）

### R5.6 抓取结果缓存
- 相同 URL 24h 内的抓取结果 key=`sha256(url)` 缓存 S3（`teams/{team_id}/crawl-cache/...`）
- 避免重复爬取造成反爬封锁

---

## R6. 去重（U2-F6=C 标题去重）

### R6.1 归一化标题
```python
def normalize_title(t: str) -> str:
    return unicodedata.normalize("NFKC", t).strip().lower()
```

### R6.2 检测策略
- 上传前查询 `Novel` 表：`team_id == principal.team_id AND normalized_title == X`
- 命中 → 返回 409 `CONFLICT_TITLE_EXISTS` + 已有 novel_id
- 前端决定是否覆盖（创建新 novel_id）或放弃
- `CONFLICT_TITLE_EXISTS` 响应体含 `existing_novel_id` 供用户参考

### R6.3 强制创建
用户可带 `?force=true` 覆盖去重检查，允许创建同名 Novel。

---

## R7. 幂等性

### R7.1 上传幂等键
- 客户端可在 `Idempotency-Key` header 传一次性 UUID
- 服务端记录 `(idempotency_key, team_id) → novel_id`，24h 过期
- 重复提交返回原 novel_id + 200

### R7.2 下载/抓取 job 幂等
- `job_id` 等于 `hash(team_id + url + date)`，同日同 URL 重复请求返回同 job_id

---

## R8. Step Functions 编排

### R8.1 IngestionStateMachine（扩展 U1 骨架）
骨架 `UpdateJobRunning → EnqueueWorker → UpdateJobSucceeded`，U2 填充的 worker 任务：
- `Parse`（格式解析）
- `SplitChapters`（章节切分；confidence < 0.6 时调用 LLM）
- `WriteS3`（保存 raw.md + chapters/）
- `WriteDynamo`（Novel + Chapter 元数据）
- `EmitEvent`（`novel.ingested`）

---

## R9. 可观测

### R9.1 关键 metric
- `IngestionDurationMs{format}` — 按原始格式
- `IngestionChapterCount{format}` — 切分质量
- `LlmChapterSplitInvoked` — 启发式失败率
- `RobotsTxtBlocked{host}` — 合规拒绝统计
- `SearchEngineDownloadRequested{source}` — Baidu/Bing 下载触发次数（审计关键）
- `CrawlTierDowngraded{host}` — URL 抓取从 Tier 1 降级到 Browser 的次数
- `SearchTierDowngraded{source}` — 搜索源从 Tier 1 降级到 Browser 的次数
- `BrowserSessionCount{source}` — AgentCore Browser 会话使用数（成本相关）

### R9.2 审计
- U1-F4=A 原本只对 Admin 操作审计。U2 扩展：
  - **搜索引擎下载（Baidu/Bing）强制 audit**：记录 user、team、查询词、目标 URL、结果
  - 即使 audit 由非 Admin 触发

---

## R10. 错误处理

| 错误 | Code | HTTP |
|---|---|---|
| 文件过大 | `VALIDATION_FILE_TOO_LARGE` | 413 |
| 不支持格式 | `VALIDATION_UNSUPPORTED_FORMAT` | 415 |
| 解析失败 | `UPSTREAM_PARSE_FAILED` | 422 |
| robots.txt 禁止 | `FORBIDDEN_ROBOTS_DISALLOWED` | 403 |
| 标题冲突 | `CONFLICT_TITLE_EXISTS` | 409 |
| 源站不可达 | `UPSTREAM_SOURCE_UNREACHABLE` | 502 |
| 搜索无结果 | `NOT_FOUND_PUBLIC_DOMAIN` | 404 |
