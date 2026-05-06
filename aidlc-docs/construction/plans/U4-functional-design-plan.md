# U4 Generation Agents — 功能设计计划

**Unit**：U4 Generation Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## Unit Context

U4 承载生成 Agent 群：大纲 / 章节 / Self-Critique / ModeRouter（仿写 vs 续写）。关键 Stories：
- Primary：US-04-01 模式选择、US-04-02 风格滑块、US-04-03 章节数/字数、US-05-01/02 大纲审核、US-06-01 流式章节、US-06-02 Memory 约束、US-06-04 编辑/打回、US-NFR-02 单章 < 60 秒
- Collab：US-06-03 双层 Critic（Layer-1 Self-Critique 属 U4；Layer-2 独立 Critic 在 U5）

U4 消费 U3 提供的 MemoryFacade 接口（recall / get_character / neighbors）。

---

## 第 1 部分 — 澄清问题（8 个）

### Question U4-F1 — 生成模式路由
FR-3.1/3.2 的"全新仿写" vs "续写"路由：

A) **Mode Enum + 两套 Prompt**：`Mode.CLEAN_ROOM` / `Mode.CONTINUATION`，分别使用不同的 system prompt ✓
B) **单一 Prompt + mode 参数**：让 LLM 自己根据参数调整风格
C) **Other

[回答]： A

### Question U4-F2 — 大纲粒度
OutlineAgent 产出的大纲详细到何种程度？

A) **章节级大纲**：每章一段话（~100 字）+ 涉及人物 + 地点 ✓
B) **粗略大纲**：仅主线 + 人物表
C) **段落级大纲**：每章分幕，每幕一段（太重）
D) 其他
[回答]： A

### Question U4-F3 — 用户大纲编辑后的处理
US-05-02 允许用户编辑大纲。编辑后：

A) **LLM 不重新校验**：直接存，生成章节时按用户大纲走 ✓
B) **LLM 校验一致性**：对比用户改动与原作风格，给出建议
C) 其他
[回答]： B

### Question U4-F4 — 章节生成的 Memory 召回
每章生成前调用 `MemoryFacade.recall`：

A) **固定 top_k=20** + hybrid_search（BM25 + kNN）✓
B) **动态 top_k**：按章节主题长度伸缩（10-50）
C) 仅 kNN（简单但召回面窄）
D) 其他
[回答]： A

### Question U4-F5 — Self-Critique 执行时机
Layer-1 Self-Critique：

A) **章节写完后再调一次 LLM**：同 chapter_all 模型，复盘本章 ✓
B) **在章节生成 prompt 中 inline**：让同一次调用先写再自评（省 1 次调用但输出结构变复杂）
C) 其他
[回答]： A

### Question U4-F6 — Cancel 语义（AD4 澄清 2=A 的落实）
`POST /jobs/{id}/cancel` 的具体行为：

A) **写 DDB cancel_requested=true** → Worker 每个 Bedrock stream token 回调检查 → 为 true 立即关闭 stream + 标记 CANCELED ✓
B) A + **每 5 秒 poll 一次**（减少 DDB 读取压力）
C) 其他
[回答]： A

### Question U4-F7 — 风格向量注入方式
NFR-4 (US-04-02) 风格滑块的 6 维向量如何进入 Prompt？

A) **系统 prompt 前缀**：固定模板展开 6 维数值 + 解释 ✓
B) **few-shot 示例**：为每种风格组合准备示例（维护成本高）
C) A + 运行时用 Memory 召回相似风格段落作为示例
D) 其他
[回答]： C

### Question U4-F8 — 章节并行生成
生成 50 章时是否并行？

A) **严格串行**：每章读前章状态，保证一致性 ✓
B) **分批并行**：每 5 章一批并行，批内允许小前后矛盾
C) **全量并行 + 事后一致性校验**（U5 负责修订）
D) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U4F-1: 生成 `domain-entities.md`
- [x] Step U4F-2: 生成 `business-rules.md`
- [x] Step U4F-3: 生成 `business-logic-model.md`
- [ ] Step U4F-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- F1=A Mode + 两套 prompt
- F2=A 章节级大纲
- F3=A 不重新校验（用户决策优先）
- F4=A 固定 top_k=20 hybrid
- F5=A 独立调用（便于模型独立配置）
- F6=A cancel_requested 实时检查
- F7=A 系统 prompt 前缀
- F8=A 严格串行（NFR-1 保障一致性，NFR-2 单章 60s 可达）
