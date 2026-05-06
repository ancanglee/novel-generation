# U2 Ingestion Service — 功能设计计划

**Unit**：U2 Ingestion Service
**阶段**：Functional Design
**日期**：2026-04-27

---

## Unit Context

U2 负责**小说采集**（Stories US-02-01 上传、US-02-02 公版书搜索、US-02-03 URL 抓取、US-02-04 列表查看）。依赖 U1 的 StorageAdapter、AuthAdapter、AgentCore Browser、Step Functions 骨架。

## 第 1 部分 — 澄清问题

### Question U2-F1 — 格式解析策略（Q3=D 所有格式转 Markdown）
如何实现 TXT/EPUB/PDF/DOCX/Markdown → Markdown 的统一？

A) **每格式一个独立 parser 类**（TxtParser、EpubParser、PdfParser、DocxParser、MdParser），`IngestionService` 按 MIME type 派发 ✓
B) **单一适配器包裹第三方库**（用 `markitdown` 一把梭）
C) A + B：MarkItDown 为主，针对 EPUB/DOCX 失败时回落到独立 parser
D) 其他
[回答]： A

### Question U2-F2 — 章节切分算法
上传完毕后如何切分章节？

A) **启发式**：基于正则识别"第 N 章"、"Chapter N"、`#` Markdown heading 等标题模式 ✓
B) **启发式 + LLM 辅助**：启发式失败时调 Haiku 4.5 辅助识别
C) **纯 LLM**：全文交给 LLM 分段（成本高）
D) 其他
[回答]： B

### Question U2-F3 — 公版书搜索源
Q7=A+B+C 要求 AgentCore Browser 访问公版书。

A) **仅 Project Gutenberg**（英文为主，中文有限）
B) **Project Gutenberg + 中国哲学书电子化计划 (ctext.org) + Wikisource 中文** ✓
C) B + 开放百科（维基文库、豆瓣读书公版书单）
D) 其他
[回答]： D: C+ www.baidu.com,以及www.bing.com通过搜索引擎进行搜索和爬取。

### Question U2-F4 — 上传大小与超时
用户本地上传的单文件上限：

A) **50 MB**（约 500 万字 TXT 上限）✓
B) **200 MB**（PDF 可能较大）
C) **无上限**（分片上传）
D) 其他
[回答]： B

### Question U2-F5 — URL 抓取的合规处理
US-02-03 抓取单 URL 时：

A) **尊重 robots.txt**（违反则拒绝）✓
B) **忽略 robots.txt**（用户自担责任）
C) A + 每次抓取写 audit log
D) 其他
[回答]： A

### Question U2-F6 — 重复上传检测
同一用户重复上传同一本书（同内容或同标题）：

A) **不检测**，允许重复 novel_id
B) **基于 SHA-256 内容哈希去重**：二次上传返回已有 novel_id ✓
C) **基于标题去重**：同标题提示但允许创建
D) 其他
[回答]： C

---

## Part 2 — Execution Checklist（批准后执行）

- [x] Step U2F-1: 生成 `domain-entities.md`
- [x] Step U2F-2: 生成 `business-rules.md`
- [x] Step U2F-3: 生成 `business-logic-model.md`
- [x] Step U2F-4: 更新 aidlc-state.md

## 第 3 部分 — 推荐
- U2-F1=A、U2-F2=B（启发式 + LLM 辅助）、U2-F3=B、U2-F4=A、U2-F5=C、U2-F6=B
