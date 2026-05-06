# U3 Understanding Agents — 非功能设计计划

**Unit**：U3 Understanding Agents
**阶段**：NFR Design
**日期**：2026-04-28

---

## 上下文摘要
上一阶段确定了 U3 关键 NFR 与技术栈。本阶段落实为具体设计模式与逻辑组件；澄清面较窄。

---

## 第 1 部分 — 澄清问题（6 个）

### Question U3-D1 — Supervisor Prompt 结构
Opus 4.7 接收的 system prompt 结构：

A) **工具清单 + 推荐路径 + 硬约束（50 步/15min/禁止循环）**，Supervisor 自由决策 ✓
B) A + ReAct 模板（强制每步输出 "Thought/Action/Observation"）
C) A + few-shot 示例（给 3 个历史成功决策序列）
D) 其他
[回答]： C

### Question U3-D2 — MemoryFacade 批量写入策略
细读每章产生 ~20 facts + 10 nodes + 20 edges。如何 flush 到 3 个后端？

A) **每章结束立即 flush**：简单直观，延迟均摊 ✓
B) **累积 5 章批量 flush**：减少 Neptune/OpenSearch 请求数，但崩溃丢失风险高
C) **分级：AgentCore Memory 立即，Neptune/OpenSearch 批量**：混合策略
D) 其他
[回答]： A

### Question U3-D3 — Neptune 查询语言
openCypher 和 Gremlin 混用的边界：

A) **全用 openCypher**（更接近 SQL 风格，维护简单）✓
B) **写用 openCypher，复杂图遍历用 Gremlin**（性能略优但两套语法）
C) 全用 Gremlin
D) 其他
[回答]： A

### Question U3-D4 — OpenSearch 索引粒度
`facts-{team_id}` 还是 `facts-{team_id}-{novel_id}`？

A) **每 team 一个索引**（已定，节省索引数）✓
B) **每 novel 一个索引**（删除时直接 drop 索引，但索引数可能爆炸）
C) **单一索引 + 多租户 filter**（所有 team 共享，仅靠字段过滤）
D) 其他
[回答]： A

### Question U3-D5 — Strands Agent 代码组织
每个 sub-agent 作为独立模块还是聚合到一个文件？

A) **每 sub-agent 一个模块**（`agents/rough_read.py`, `agents/classification.py`, ...），清晰但文件多 ✓
B) **全部在一个 `agents.py` 文件**（紧凑但大）
C) 按层级分组（`agents/global/*.py`, `agents/chapter/*.py`）
D) 其他
[回答]： A

### Question U3-D6 — JSON Schema 校验失败处理
`extract_chapter_all` 返回的 JSON 不符合 schema：

A) **提示+重试**：prompt 附加错误示例，再试 1 次；仍失败标记 partial ✓
B) **强制 Claude Tool Use**：用 Bedrock Converse API 的 toolConfig 让 Claude 自动遵守 schema
C) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U3D-1: 生成 `nfr-design-patterns.md`
- [x] Step U3D-2: 生成 `logical-components.md`
- [x] Step U3D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- D1=A（清单 + 推荐路径 + 硬约束，最简单）
- D2=A（每章 flush，简单）
- D3=A（全 openCypher）
- D4=A（team 级索引，维持原计划）
- D5=A（模块化）
- D6=B（Tool Use 更稳定，消除 schema 校验失败）
