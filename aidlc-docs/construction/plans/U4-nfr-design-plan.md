# U4 Generation Agents — 非功能设计计划

**Unit**：U4 Generation Agents
**阶段**：NFR Design
**日期**：2026-04-28

---

## 上下文摘要
U4 的 NFR 已确定（TTFT<3s / P95<60s / Cancel ≤10s / 串行 / 10 版本保留 / 5 次重写）。本阶段落实为设计模式 + 逻辑组件。澄清面较窄。

---

## 第 1 部分 — 澄清问题（5 个）

### Question U4-D1 — SSE 端点路径
ApiService 的 SSE 端点路径选择：

A) **per-job**：`/api/v1/jobs/{job_id}/stream`（通用，U1 已定）✓
B) **per-chapter**：`/api/v1/generations/{gid}/chapters/{n}/stream`
C) A + B 并存
D) 其他
[回答]： C

### Question U4-D2 — EventBridge Archive
是否启用 EventBridge Archive 支持 Last-Event-ID 重放（NFR-4.1）？

A) **启用 Archive 保留 7 天**：支持跨进程重放 ✓
B) **不启用 Archive**：仅用进程内 ring buffer（单实例 SSE，不支持 ALB 切流）
C) 其他
[回答]： A

### Question U4-D3 — ChapterStateMachine Map state 并发
严格串行 (F8=A) 如何在 SFN 层面表达？

A) **Map state + MaxConcurrency=1**（简单）✓
B) **显式循环 Choice 状态**（Map state 的 concurrency=1 是硬约束在 SFN ASL 中易错，显式循环更清晰）
C) 其他
[回答]： B

### Question U4-D4 — OutlineReviewAgent 触发方式
F3=B 异步校验触发：

A) **SQS 独立 review-queue**：由 review-worker 消费；新增基础设施开销
B) **复用 generation-queue**：通过 message kind 区分，同 Worker 处理 ✓
C) **Lambda 直接触发**（冷启动可接受）
D) 其他
[回答]： A

### Question U4-D5 — 样本风格参考 Memory 召回（F7=C）
风格注入的 Memory 召回次数策略：

A) **每章调用 hybrid_search**：每章重新召回 3 段，可能因章节主题差异召回不同风格 ✓
B) **Generation 启动时召回一次缓存**：避免重复调用，但章节间无差异
C) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U4D-1: 生成 `nfr-design-patterns.md`
- [x] Step U4D-2: 生成 `logical-components.md`
- [x] Step U4D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- D1=A per-job（通用，与 U1 一致）
- D2=A 启用 Archive
- D3=A Map state + MaxConcurrency=1
- D4=B 复用 generation-queue（省基础设施）
- D5=B 启动时缓存（减少 LLM 成本与延迟）
