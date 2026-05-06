# 故事生成计划（Story Generation Plan）— 小说仿写生成应用

## Purpose
本计划定义了 User Stories 阶段的执行步骤、方法论，以及需要用户澄清的若干问题。请在文档底部的 `[回答]：` 处填写答案，完成后回复"done"。

---

## Part 1 — 规划问题（请回答）

### Question S1 — Story 组织方式
你希望 stories.md 按什么维度组织？

A) **按用户旅程 (User Journey)**：采集 → 理解 → 配置 → 大纲审核 → 章节生成与审核 → 导出 → 管理
B) **按角色 (Persona)**：先列 RegularUser 所有 Story，再列 TeamMember，再列 Admin
C) **按 Epic（大功能域）**：Epic 1 采集、Epic 2 理解、Epic 3 生成、Epic 4 协作、Epic 5 后台
D) **旅程 + Epic 双层**：顶层按 Epic，Epic 内部按旅程阶段排序（推荐）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question S2 — 验收标准格式
每条 Story 的 验收标准 采用什么格式？

A) **Given / When / Then**（Gherkin 风格，最适合自动化测试）
B) **Checklist**（每条 Story 下列若干条可勾选项）
C) **两者兼有**：高价值故事用 Given/When/Then；简单故事用 Checklist
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question S3 — 故事粒度
Story 的粒度大小？

A) **中等粒度**（建议）：每个 Story 可在 1-3 天内实现，约 25-35 个 Story 覆盖整个 V1
B) **细粒度**：每个 Story < 1 天，约 50-70 个 Story
C) **粗粒度（Epic 偏向）**：约 10-15 个大 Story，由开发团队在 Units Generation 阶段细分
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question S4 — 非功能性故事 (NFR Stories)
是否要为非功能性需求（性能、安全、可观测、成本护栏）单独写 Story？

A) **单独写**：为每个 NFR 组建一批 technical stories（例如"作为用户我希望单章生成在 60 秒内完成"）
B) **嵌入业务 Story 的验收标准**：不单独列，而是把性能/安全要求写入相关业务 Story 的 Given/When/Then
C) **关键 NFR 单独写**（性能、多租户隔离、成本护栏），其余嵌入
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question S5 — Persona 细节深度
personas.md 中每个 Persona 需要什么级别的细节？

A) **基础**：角色名、简短描述、主要目标
B) **标准**（推荐）：角色名 + 背景 + 目标 + 痛点 + 使用场景 + 所需能力
C) **深入**：标准 + 典型工作日 + 技术熟练度 + 代表性用户引语
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question S6 — 第三方 Persona
除 RegularUser、TeamMember、Admin 外，是否需要额外的 Persona？

A) **仅三角色**：RegularUser、TeamMember、Admin
B) **加 Guest (未登录访客)**：可看产品介绍页、登录前预览
C) **加 Content Moderator**：专职审核敏感内容的角色
D) **加 System Agent**：把 Agent 本身视为"内部 Persona"，用于描述 Agent 之间的协作
E) B + C
F) Other (please describe after [回答]： tag below)

[回答]： E

### Question S7 — Story 与需求追溯
是否需要在 stories.md 里维护与 requirements.md 的双向追溯？

A) **完整追溯**：每个 Story 标注 FR-X.Y / NFR-X 引用
B) **仅 Epic 级追溯**：Epic 层面注明覆盖哪些 FR，Story 内部不重复
C) **不追溯**：精简至 Story 自身
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question S8 — 故事优先级
是否为每个 Story 标注优先级？

A) **MoSCoW**（Must / Should / Could / Won't）
B) **P0/P1/P2**
C) **不标优先级**，由 Units Generation 阶段决定
D) Other (please describe after [回答]： tag below)

[回答]： B

---

## Part 2 — 执行步骤（Story Generation Plan Checklist）

**注：以下步骤将在用户批准本计划后逐一执行。**

- [x] Step G1: 加载 requirements.md 和 execution-plan.md，提取角色与流程
- [x] Step G2: 基于 Q S6 的 Persona 选择，生成 `personas.md`，详细度按 Q S5
- [x] Step G3: 基于 Q S1 的组织方式，搭建 `stories.md` 骨架
- [x] Step G4: 按照 Q S3 的粒度，为每个 Epic/旅程阶段生成 Story
- [x] Step G5: 为每个 Story 按 Q S2 的格式编写 验收标准
- [x] Step G6: 按 Q S4 处理 NFR Story
- [x] Step G7: 按 Q S7 添加需求追溯
- [x] Step G8: 按 Q S8 标注优先级
- [x] Step G9: 对每个 Story 进行 INVEST 校验（Independent / Negotiable / Valuable / Estimable / Small / Testable）
- [x] Step G10: 添加 Story → Unit 的初步映射（支撑 Units Generation）
- [x] Step G11: 更新 aidlc-state.md

---

## Part 3 — 故事分解方法（方法论说明）

**分解方法**（基于业界最佳实践）：
1. **从用户价值出发**：每个 Story 必须以"作为... 我希望... 以便..."句式表达用户价值
2. **INVEST 原则**：Independent（独立）/ Negotiable（可协商）/ Valuable（有价值）/ Estimable（可估）/ Small（小）/ Testable（可测）
3. **Given/When/Then 验收**（若 Q S2 选 A/C）：前置条件 → 操作 → 预期结果
4. **Happy Path + Edge Cases**：每个 Story 至少 1 条主路径 + 必要的异常场景

---

## Part 4 — 建议（供参考，不影响你的选择）

- **Q S1 → D**：双层组织最便于检索与追溯
- **Q S2 → A**：Gherkin 风格直接对应自动化验收测试
- **Q S3 → A**：25-35 个中等粒度最匹配 7 个 Unit 的规模
- **Q S4 → C**：关键 NFR（性能、多租户、成本护栏）单独写，便于专项验收
- **Q S5 → B**：标准细节足够驱动设计
- **Q S6 → A**：聚焦三角色即可
- **Q S7 → A**：完整追溯对后续验证有价值
- **Q S8 → A**：MoSCoW 对 V1 范围控制友好
