# U2 Ingestion Service — 非功能需求计划

**Unit**：U2 Ingestion Service
**阶段**：NFR Requirements
**日期**：2026-04-27

---

## 上下文摘要
U2 继承 U1 的 NFR 基础（us-east-1 / 99.5% SLA / AWS managed 加密 / 无 API 限流 / token metric 告警护栏 / 按需 serverless）。本阶段聚焦 U2 特有的非功能性问题。

---

## 第 1 部分 — 澄清问题（仅 U2 相关）

### Question U2-N1 — 采集延迟目标
单次上传/抓取到 Novel.status=INGESTED 的完成时间：

A) **P95 < 30 秒**（200MB 文件解析 + 章节切分），抓取 URL P95 < 60 秒 ✓
B) **P95 < 2 分钟**（宽松）
C) **P95 < 10 秒**（严格，需并行解析）
D) 其他
[回答]： B

### Question U2-N2 — Tier 2 Browser 降级比例预期
何时触发告警？

A) **降级率 > 30%（5min 窗口）** → SNS 告警，说明反爬加剧 ✓
B) **降级率 > 50%** → 告警（宽松）
C) **任何降级都告警**（噪声过大，不推荐）
D) 其他
[回答]： A

### Question U2-N3 — 解析超时
单文件解析的最大时长：

A) **60 秒**（多数格式够用；超时则 Job FAILED）✓
B) **3 分钟**（允许大 PDF 的 OCR）
C) **5 分钟**（宽松）
D) 其他
[回答]： B

### Question U2-N4 — Parser 依赖策略
第三方解析库（ebooklib, pypdf, pdfplumber, python-docx, trafilatura）的依赖策略：

A) **锁定版本**（uv.lock），每季度评估更新 ✓
B) **~=x.y**（minor 自动升级）
C) **latest**（激进）
D) 其他
[回答]： B

### Question U2-N5 — 抓取缓存大小
R5.6 的 crawl-cache S3 前缀的生命周期：

A) **24h TTL**（匹配抓取缓存语义）✓
B) **7d TTL**（更长时间避免重复爬取）
C) **不过期**（持久归档 URL → content）
D) 其他
[回答]： B

### Question U2-N6 — 搜索引擎关键词过滤
为避免明显涉及盗版的搜索词（如包含"免费下载"、"全本"），是否在搜索前做关键词过滤？

A) **不过滤**（由用户自担责任）
B) **软过滤**：触发关键词时 UI 显示警告，用户确认后仍可搜索 ✓
C) **硬过滤**：命中关键词直接拒绝
D) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U2N-1: 生成 `nfr-requirements.md`
- [x] Step U2N-2: 生成 `tech-stack-decisions.md`
- [x] Step U2N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- U2-N1=A（P95 30s 上传 / 60s 抓取）
- U2-N2=A（降级率 > 30% 告警）
- U2-N3=A（60 秒解析超时）
- U2-N4=A（锁定版本）
- U2-N5=A（24h 缓存）
- U2-N6=B（软过滤 + 用户确认）
