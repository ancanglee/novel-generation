# U5 Critic & Consistency — 非功能需求计划

**Unit**：U5 Critic & Consistency
**阶段**：NFR Requirements
**日期**：2026-04-28

---

## 上下文摘要
U5 继承 U1/U2/U3/U4 的 NFR 基础（区域、SLA、加密、按需 serverless、metric 告警）。聚焦 U5 特有项。Moderation 已移除，本阶段澄清项相应减少。

---

## 第 1 部分 — 澄清问题（5 个）

### Question U5-N1 — Critic 延迟目标
Critic Agent（Opus 4.7）单章评审：

A) **P95 < 30 秒**（Opus 4.7 处理 3-4k input + 1k output 可达）✓
B) **P95 < 60 秒**（宽松）
C) **P95 < 15 秒**（严格，需要降级到 Sonnet 4.7）
D) 其他
[回答]： B

### Question U5-N2 — Consistency 延迟目标
每 10 章触发一次的全局扫描：

A) **P95 < 2 分钟**（10 章 + 30 facts + get_character 调用）✓
B) **P95 < 4 分钟**（宽松）
C) **P95 < 1 分钟**（严格）
D) 其他
[回答]： B

### Question U5-N3 — Critic 失败时的行为
Opus 4.7 Throttle / 超时：

A) **SFN Retry 3 次，耗尽写 minimal report (score=0 issue='critic_failed')，Chapter 状态仍 GENERATED**（业务继续） ✓
B) **失败则阻断 Chapter 状态停留在 GENERATED 之前**（用户必须等 Critic 成功才能看章节）
C) 其他
[回答]： A

### Question U5-N4 — U5 单 Generation 成本
50 章 Generation 的 U5 部分预算：

A) **~$30 上限**（Critic 50 × $0.6 = $30，Consistency 5 × $0.2 = $1，合计 ~$31）
B) **~$15 上限**（Critic 降级为 Sonnet 4.7 ~$0.3/章）
C) 无硬上限，依赖 U1 token metric 告警 ✓
D) 其他
[回答]： C

### Question U5-N5 — ConflictItem UI 交互 SLA
用户点 Ignore / Rewrite 后响应时间：

A) **Ignore 立即返回**；Rewrite 202 Accepted 返回 job_id ✓
B) **Rewrite 等待新章节完成才返回**（阻塞用户 60+ 秒）
C) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U5N-1: 生成 `nfr-requirements.md`
- [x] Step U5N-2: 生成 `tech-stack-decisions.md`
- [x] Step U5N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- N1=A Critic P95 < 30 秒
- N2=A Consistency P95 < 2 分钟
- N3=A 失败不阻断
- N4=C 无硬上限，依赖 U1 token 告警
- N5=A Ignore 立即，Rewrite 异步 202
