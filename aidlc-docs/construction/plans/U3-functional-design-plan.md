# U3 Understanding Agents — 功能设计计划

**Unit**：U3 Understanding Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## Unit Context

U3 承载小说理解的核心 Agent 群：粗读、类型鉴别、人物、地图、风格、细读 6 个 sub-agent，由 Strands Agents 编排（AD7=B）。关键 Stories：
- Primary：US-03-01 触发分析、US-03-02 类型鉴别、US-03-03 人物报告、US-03-04 地图路线、US-03-05 风格雷达、US-NFR-01 100 万字 < 15 min
- Collab：US-06-02 Memory 约束（为 U4 提供事实检索）、US-08-02/03 Admin 模型配置

U3 同时**填充 U1 的 MemoryFacade 骨架**，给出 AgentCore Memory + Neptune + OpenSearch 的具体实现。

---

## 第 1 部分 — 澄清问题

### Question U3-F1 — Strands Agent 编排模式
6 个 sub-agent 如何编排？

A) **Graph Pattern**：RoughRead → Parallel(Classification, Character, Map, Style) → DeepRead(Map state) → MemoryWrite，明确有向无环图 ✓
B) **Supervisor Agent**：一个顶层 supervisor agent 自己决定下一步调用哪个 sub-agent（更灵活但不可预测）
C) **Workflow (LangGraph 风格)**：显式状态机
D) 其他
[回答]： B

### Question U3-F2 — 粗读抽样策略
RoughReadSubAgent 如何选 sample？

A) **固定规则**：首 3 章 + 末 3 章 + 等间距中间 6 章 = 12 章抽样 ✓
B) **按字数固定 10%**：前 5% + 中 5%，保持总量有限
C) **LLM 自适应**：先看目录决定采样章节
D) 其他
[回答]： C

### Question U3-F3 — 类型鉴别的标签产出
ClassificationSubAgent 输出：

A) **多标签 + 置信度**（例如 [("修仙", 0.9), ("穿越", 0.7), ("系统流", 0.5)]），由 admin 合并 ✓
B) 单一最可能标签
C) 标签 + 子标签层级（例如 修仙 → 仙侠 → 玄幻仙侠）
D) 其他
[回答]： A

### Question U3-F4 — 人物抽取的触发粒度
CharacterSubAgent 的调用单位：

A) **粗读产出初稿 + 细读增量更新**（每章发现的新人物/新状态追加到 Memory）✓
B) 仅粗读一次，细读阶段不更新人物
C) 每章全量重建人物列表（昂贵）
D) 其他
[回答]： C

### Question U3-F5 — 地图知识图谱数据结构
地点知识图谱节点/边 schema：

A) **节点类型**：Place / Character / Event；**边类型**：visited(chr→place, chapter_range)、adjacent(place↔place)、located_in(place→place)、event_at(event→place) ✓
B) 简化：仅 Place 节点 + visited 边
C) A + 增加 faction（势力）节点
D) 其他
[回答]： C

### Question U3-F6 — 风格向量的 6 维度实现
StyleSubAgent 如何产出 6 维风格向量（基调/节奏/描写密度/对话占比/情感强度/世界观宏大度）？

A) **LLM 直接评分**：Claude 对样本评分 0-100，返回 6 个数值 + 解释 ✓
B) **统计 + LLM**：部分维度用统计（对话占比=引号比例、描写密度=句长均值），其他维度 LLM 打分
C) 纯统计（无 LLM）
D) 其他
[回答]： A

### Question U3-F7 — 细读章节的并发处理
DeepReadSubAgent 处理单章时：

A) **每章单次 LLM 调用**：一次 prompt 输出所有抽取结果（character updates + map updates + events + facts）✓
B) **每章多次 LLM 调用**：每个 sub-agent 独立处理该章（成本×4）
C) 其他
[回答]： B

### Question U3-F8 — Memory 写入失败的处理
MemoryFacade.remember 写入失败（Neptune 超时 / OpenSearch 限流）：

A) **分层降级**：AgentCore Memory 必须成功；Neptune/OpenSearch 失败则 warning 但继续 ✓
B) **任一失败整体失败**（job FAILED）
C) **全部失败才算失败**
D) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U3F-1: 生成 `domain-entities.md`
- [x] Step U3F-2: 生成 `business-rules.md`
- [x] Step U3F-3: 生成 `business-logic-model.md`
- [x] Step U3F-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- F1=A Graph Pattern（可预测性 + 可观测性最好）
- F2=A 固定规则（简单稳定）
- F3=A 多标签 + 置信度（符合 Q4=D 决策）
- F4=A 粗读初稿 + 细读增量
- F5=A 完整 schema
- F6=B 统计 + LLM 混合（节约成本）
- F7=A 单次 LLM 调用（节约 3-4x 成本）
- F8=A 分层降级（Memory 优先）
