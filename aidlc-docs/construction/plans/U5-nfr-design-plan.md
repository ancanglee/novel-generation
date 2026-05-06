# U5 Critic & Consistency — 非功能设计计划

**Unit**：U5 Critic & Consistency
**阶段**：NFR Design
**日期**：2026-04-28

---

## 上下文摘要
U5 范围为 Critic（Opus 4.7 复核）+ Consistency（Sonnet 4.6 增量扫描）。澄清面窄，3 个问题。

---

## 第 1 部分 — 澄清问题（3 个）

### Question U5-D1 — Consistency 触发机制
SSM `consistency-interval` 默认 10。ChapterAgent 每章完成时如何触发 Consistency？

A) **ChapterAgent 发事件 `consistency.trigger`（当 idx % N == 0），EventBridge Rule → consistency-queue** ✓
B) **EventBridge Rule 直接订阅 `chapter.completed` + Input Transformer 过滤 idx % N**（SFN 层）
C) **独立 Lambda 定时扫描**（cron，不实时）
D) 其他
[回答]： A

### Question U5-D2 — 重写循环保护计数器位置
"同一 ConflictItem 连续 3 次 rewrite → 冻结"（NFR-2.3）的计数器存储：

A) **ConflictItem.rewrite_attempts 字段**（每次 rewrite 自增）✓
B) **独立 DDB 项 `CONFLICT_LOOP#{conflict_id}`** 带 TTL
C) **进程内 Counter**（会丢失）
D) 其他
[回答]： A

### Question U5-D3 — 跨章节 summary 来源
Critic Layer-2 需要"最近 5 章 summary"（R1.2）。来源：

A) **直接读最近 5 章完整文本**（S3 5 次 GetObject，但 prompt token 压力大）
B) **从 Outline.items[].summary 读**（便宜且已有）✓
C) **每次由 LLM 先做 summary**（昂贵）
D) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U5D-1: 生成 `nfr-design-patterns.md`
- [x] Step U5D-2: 生成 `logical-components.md`
- [x] Step U5D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- D1=A ChapterAgent 发 `consistency.trigger` 事件（简单清晰）
- D2=A ConflictItem.rewrite_attempts 字段（数据近邻，天然跟随 Conflict 生命周期）
- D3=B 直接用 Outline.items[].summary（零额外 LLM 成本）
