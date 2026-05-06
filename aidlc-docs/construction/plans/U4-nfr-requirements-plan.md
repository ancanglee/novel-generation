# U4 Generation Agents — 非功能需求计划

**Unit**：U4 Generation Agents
**阶段**：NFR Requirements
**日期**：2026-04-28

---

## 上下文摘要
U4 继承 U1/U2/U3 的 NFR 基础（区域、SLA、加密、按需 serverless、Tool Use）。聚焦 U4 特有项：流式延迟、Cancel 响应时间、并发 Generation 数、重写上限等。

---

## 第 1 部分 — 澄清问题（6 个）

### Question U4-N1 — 单章流式延迟（NFR-1 已定 60s；本题定细节）
流式推送的关键指标：

A) **首字节 < 3s + 单章 P95 < 60s + 整章 P99 < 90s** ✓
B) **首字节 < 5s + 单章 P95 < 90s**（宽松）
C) **首字节 < 1s + 单章 P95 < 40s**（严格，需 Opus→Sonnet 下放）
D) 其他
[回答]： A

### Question U4-N2 — Cancel 响应时间
用户点 Cancel 到 Worker 真正关闭 stream 的最大延迟：

A) **≤ 5 秒**（对齐 R6 TTLCache 5s 读 DDB）✓
B) **≤ 10 秒**（宽松，减少 DDB 读）
C) **≤ 1 秒**（严格，需移除 TTLCache 每次实时读 DDB）
D) 其他
[回答]： B

### Question U4-N3 — 单 Generation 最大并发数
平台允许的同时生成中 Generation 数量：

A) **无全局限制**（依赖 Bedrock RPS 自适应）
B) **团队级限制**：每 team 最多 3 个同时 GENERATING ✓
C) **用户级限制**：每 user 最多 1 个同时
D) 其他
[回答]： A

### Question U4-N4 — 大纲 LLM 校验延迟（F3=B）
F3=B 异步校验的 SLA：

A) **P95 < 30s**（Sonnet 4.6 快速校验） ✓
B) **P95 < 2 分钟**（宽松）
C) 其他
[回答]： B

### Question U4-N5 — 重写上限
rewrite_count 上限（R10）：

A) **5 次**（默认）✓
B) **10 次**
C) **3 次**
D) admin 可配置（默认 5）

[回答]： A

### Question U4-N6 — 章节 S3 版本保留
重写保留多少历史版本？

A) **全部保留**（S3 版本化默认）✓
B) **保留最近 10 个版本**
C) **仅保留最新**（无历史）
D) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U4N-1: 生成 `nfr-requirements.md`
- [x] Step U4N-2: 生成 `tech-stack-decisions.md`
- [x] Step U4N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- N1=A（TTFT < 3s / P95 < 60s / P99 < 90s）
- N2=A（对齐 R6 TTLCache 5s）
- N3=B（team 级 3 个并发，平衡 Bedrock 配额与用户体验）
- N4=A（Sonnet 4.6 < 30s）
- N5=D（admin 可配，默认 5）
- N6=A（S3 版本化默认全量保留，配 Lifecycle 30 天后降冷）
