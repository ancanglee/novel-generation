# U2 Tech Stack Decisions

**Unit**：U2 Ingestion Service
**日期**：2026-04-27

U2 技术栈绝大部分继承 U1。本文仅记录 U2 新增的依赖。

---

## 1. 格式解析库（U2-F1=A 独立 parser）

| 格式 | 库 | 版本策略（U2-N4=B） | 备注 |
|---|---|---|---|
| TXT | 标准库 `chardet` | `chardet~=5.2` | 自动编码识别 |
| Markdown | 标准库 + `markdown-it-py` | `markdown-it-py~=3.0` | 透传 + heading 解析 |
| EPUB | `ebooklib` | `ebooklib~=0.18` | 成熟稳定 |
| PDF | `pypdf`（首选）+ `pdfplumber`（回退） | `pypdf~=5.0`, `pdfplumber~=0.11` | 双层 fallback |
| DOCX | `python-docx` | `python-docx~=1.1` | |
| HTML | `trafilatura` | `trafilatura~=1.12` | 同时用于 URL 抓取 |

**选择理由**：
- 纯 Python 库，无系统依赖，打包到 Docker 简单
- 皆为活跃维护项目，有清晰 CVE 披露
- ~=x.y minor 自动升级（Dependabot PR）

**不用的库**：
- ❌ `markitdown`：依赖较重，部分格式体验不如独立库
- ❌ `Apache Tika`：Java 依赖，增加 Docker 镜像体积
- ❌ OCR（pytesseract）：V1 不支持扫描版 PDF（超出 3 分钟预算）

---

## 2. HTTP 客户端（Tier 1 爬虫）

| 方面 | 决策 |
|---|---|
| 客户端 | `httpx~=0.27`（同步 + 异步）|
| robots.txt 解析 | `urllib.robotparser`（标准库）|
| retry | `tenacity~=9.0` |
| 连接池 | httpx 默认，每 host 最多 10 connection |

---

## 3. 抓取正文抽取

| 方面 | 决策 |
|---|---|
| 主库 | `trafilatura~=1.12` |
| 回退 | `readability-lxml~=0.8.1`（当 trafilatura 抽不出时） |
| DOM 解析 | `lxml~=5.3` |

---

## 4. AgentCore Browser 集成（Tier 2）

| 方面 | 决策 |
|---|---|
| SDK | `bedrock-agentcore` Python SDK（随 U1 打通） |
| 包装层 | `packages/agentcore-adapter` 或 `services/worker-analysis/lib/browser.py`（由 U2 实现，在 U3 使用时复用）|
| 会话模式 | 每 URL 新建会话，结束即关 |
| DOM 等待 | `domcontentloaded` 后再等 2s |

---

## 5. 幂等性与缓存

| 方面 | 决策 |
|---|---|
| Idempotency-Key | `uuid4` 由客户端生成；服务端用 `novelgen_jobs` 表 TTL 24h 存映射 |
| crawl-cache | S3 `teams/{team_id}/crawl-cache/sha256(url).html` + Lifecycle 7d（U2-N5=B） |

---

## 6. 章节切分（U2-F2=B）

| 方面 | 决策 |
|---|---|
| 启发式正则 | 纯 Python 代码 |
| LLM 辅助 | Bedrock Claude Haiku 4.5（由 U1 ModelConfig 默认，admin 可覆盖） |
| 触发条件 | 启发式 confidence < 0.6 |

---

## 7. 去重（U2-F6=C）

| 方面 | 决策 |
|---|---|
| 归一化 | `unicodedata.normalize('NFKC') + strip + lowercase` |
| 查询 | DynamoDB `novelgen_tenancy` 的 `query_by_sk_prefix("NOVEL#")` 过滤 |
| 覆盖 | `?force=true` 查询参数 |

---

## 8. Docker 镜像

- Base: `python:3.12-slim`
- 新增 apt 依赖：`libxml2`, `libxslt1-dev`（lxml 需要）、`poppler-utils`（pdfplumber 需要）
- 最终镜像大小预估：~ 250 MB（vs U1 api-service ~ 180 MB）

---

## 9. Worker 规格（继承 U1 ComputeStack）

在 U1 `compute_stack.py` 预定义的 `worker-analysis` TaskDefinition 上扩展：
- **U2 不单独创建 worker Service**，而是**扩展 `worker-analysis` 的职责**（还会处理 ingestion queue）
- 或者在 U1 基础设施上新增一个 `worker-ingestion` Service（TaskDef 与 analysis 共享规格 2048 CPU / 4096 MB）
- 决策：**新增 `worker-ingestion` Service**，职责隔离 + 独立 Auto Scaling

---

## 10. 与其他 Unit 的接口

- 向 **U1** 新增：
  - `worker-ingestion` ECS Service（在 ComputeStack 或 U2 独立 stack 添加）
  - `ingestion-queue` SQS + DLQ（在 MessagingStack 新增）
  - `IngestionStateMachine` 的完整 ASL（填充 U1 骨架）
- 被 **U3** 消费：
  - U3 UnderstandingAgent 读取 Novel.raw_s3_key 与 Chapter 元数据
  - 通过 EventBridge `novel.ingested` 事件触发分析
- 向 **U6** 提供：
  - REST API `/api/v1/novels/*`（上传 / 下载 / 抓取 / 列表 / 详情 / 删除）
