# U2 Ingestion Service — 非功能设计计划

**Unit**：U2 Ingestion Service
**阶段**：NFR Design
**日期**：2026-04-27

---

## 上下文摘要
U2 的 NFR Requirements 已经非常具体（P95 2min / Tier 2 30% 告警 / 解析 3min 超时 / 7d crawl-cache / ~=x.y 版本 / 不过滤搜索词）。本阶段把这些落实为设计模式与逻辑组件；澄清面小。

---

## 第 1 部分 — 澄清问题（仅 5 个）

### Question U2-D1 — Parser 调度并发
单文件解析可能耗时 3min（N3=B），Worker 一次并发多少个解析任务？

A) **单 Task 单文件**：Worker ECS task 内串行处理一个 SQS 消息 → 一次解析；靠 Auto Scaling 横向扩展 ✓
B) **单 Task 多文件**：asyncio 内并发 5 个解析任务
C) **大 PDF 独立队列**：普通格式串行，PDF 单独队列
D) 其他
[回答]： B

### Question U2-D2 — 搜索 5 源并行 vs 串行
候选列表返回的 5 个搜索源：

A) **全部并行**（asyncio.gather），取最快返回的先展示 ✓
B) **顺序执行**：先 Gutenberg 再 ctext... 最后 Baidu/Bing
C) **分组并行**：API 源（前 3 个）并行 → 搜索引擎（Baidu/Bing）并行
D) 其他
[回答]： C

### Question U2-D3 — Browser 降级触发位置
降级判定放在哪一层？

A) **Worker 代码层**：Worker 根据 Tier 1 响应特征自行决定降级 ✓
B) **Step Functions 层**：SFN Task 失败后 Catch 到 Browser Task
C) A + B：Worker 主决策，SFN Catch 作为兜底
D) 其他
[回答]： C

### Question U2-D4 — crawl-cache key 去隐私
`sha256(url)` 作为 S3 key 时，是否也对查询参数敏感？

A) **原始 URL 全 hash**：query string 变一个字符 cache miss（最稳妥）✓
B) **去除常见 tracking 参数后 hash**（utm_*、ref 等）：命中率更高
C) **仅 hash host + path**（完全忽略 query）：命中率最高但可能误合并
D) 其他
[回答]： B

### Question U2-D5 — Tier 2 Browser 请求鉴权
AgentCore Browser 发起的请求如何代表 NovelGen 身份？

A) **保留 AgentCore 默认 UA**（真实浏览器 UA，便于穿过反爬）✓
B) **覆盖为 NovelGenBot UA**（与 Tier 1 一致，可识别但反爬不过）
C) 先尝试 A，UA 仍被拦截时退回 B
D) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U2D-1: 生成 `nfr-design-patterns.md`
- [x] Step U2D-2: 生成 `logical-components.md`
- [x] Step U2D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- D1=A（单 Task 单文件 + Auto Scaling）
- D2=A（5 源全并行）
- D3=C（Worker 主决策 + SFN 兜底）
- D4=A（原始 URL 全 hash）
- D5=A（Browser 默认真实 UA 便于穿反爬）
