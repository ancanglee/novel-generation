# 工作单元计划（Unit of Work Plan）— 小说仿写生成应用

## Purpose
本计划将 17 个组件分解为可独立交付的 Unit，并定义依赖顺序、并行策略、Story→Unit 映射。Workflow Planning 已预览了 7 个 Unit，本计划做最终确认，只包含必要的澄清问题。

---

## Part 1 — 关键澄清问题

> 说明：execution-plan.md 已预览 U1-U7 的划分，components.md 已标注组件-Unit 映射。本阶段的澄清问题聚焦于：边界微调、并行策略、与 Story 的映射偏好。

### Question UG1 — Unit 数量与粒度
Workflow Planning 预览的 7 个 Unit 是否满足你的需求？

A) **保持 7 个 Unit**：U1 Platform / U2 Ingestion / U3 Understanding / U4 Generation / U5 Critic&Consistency&Moderation / U6 Frontend(User+BFF) / U7 Admin(Frontend+API)
B) **合并为 5 个 Unit**：合并 U3+U4+U5 为一个 "Agents" Unit；合并 U6+U7 为一个 "Frontend" Unit
C) **拆分为 9 个 Unit**：把 U5 拆成 U5a Critic、U5b Consistency、U5c Moderation；把 U7 拆成 U7a Admin-Frontend、U7b Admin-API
D) **8 个 Unit**：保持 7 个，新增 U8 "Shared Libraries"（MemoryFacade + AuthAdapter + StorageAdapter + ObservabilityAdapter 独立为一个 shared Unit）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question UG2 — 并行开发策略
完成 U1（Platform）后，哪些 Unit 可以并行开发？

A) **最大并行**：U1 完成后，U2/U3/U4/U5/U6/U7 全部并行（需要较多人力）
B) **两批次并行**：U1 → {U2, U6 前端骨架, U7 骨架} → {U3, U4} → {U5, U7 完整功能}
C) **严格顺序**：U1 → U2 → U3 → U4 → U5 → U6 → U7（适合小团队）
D) **按优先级并行**：以 P0 Story 为先，优先交付 U1 → 端到端 MVP（U2 + U3 简化版 + U4 简化版 + U6 基础页面）→ 再补齐 U5、U7、完整风格向量等
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question UG3 — Unit 交付顺序偏好
每个 Unit 的构建阶段（Functional Design → NFR → Infra → Code Generation）需要一个处理顺序。

A) **按 Unit 编号顺序串行**：U1 所有阶段完成 → U2 所有阶段完成 → …（最稳但慢）
B) **按"基础设施优先"**：U1 完整完成；其他 Unit 先集体完成 Infrastructure Design，再分别进入 Functional Design + Code Generation
C) **按"端到端 MVP 优先"**：先跑完 U1 + U2（简化）+ U3（仅类型鉴别）+ U4（仅大纲）+ U6（核心页面）的最小闭环，再迭代补全
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question UG4 — Unit 内部模块打包
每个 Unit 最终交付为：

A) **独立 git repo（per-unit repo）**：每个 Unit 一个 repo，便于独立版本管理与 CI/CD
B) **单 monorepo + 多 package**（推荐）：一个 repo，按 Unit 分 workspace（例如 pnpm workspace / uv workspace），共享依赖与工具链
C) **单 monorepo + 扁平目录**：一个 repo，扁平放置，简单但依赖不清
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question UG5 — Story 覆盖校验
33 个 Story 到 7 个 Unit 的映射已在 stories.md 矩阵中给出。是否需要增加校验机制？

A) **严格覆盖校验**：构建阶段的"任务阶段完成"需要 Story 的 AC 全部映射为自动化测试
B) **抽样校验**：每个 Unit 挑选 3-5 个 P0 Story 的 AC 作为验收测试
C) **仅文档追溯**：只要求 stories.md 的映射矩阵完整，不强制自动化
D) Other (please describe after [回答]： tag below)

[回答]： A

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U1: 根据 UG1 答案确定 Unit 清单
- [x] Step U2: 生成 `unit-of-work.md`（每 Unit 的定义、职责、组件、交付物、所有者、预计复杂度）
- [x] Step U3: 生成 `unit-of-work-dependency.md`（依赖矩阵、并行策略、关键路径）
- [x] Step U4: 生成 `unit-of-work-story-map.md`（Story → Unit 映射 + 反向校验）
- [x] Step U5: 校验：每个 Story 至少落在一个 Unit；每个组件至少落在一个 Unit；无孤岛
- [x] Step U6: 更新 aidlc-state.md

---

## Part 3 — 我的推荐

- **UG1=D**（8 个 Unit，含 Shared Libraries）：MemoryFacade/AuthAdapter/StorageAdapter/ObservabilityAdapter 被多个 Unit 共用，独立为 U8 可避免重复实现
- **UG2=B**（两批次并行）：平衡速度与依赖风险
- **UG3=B**（基础设施优先）：U1 + 其他 Unit 的 Infrastructure Design 集中完成后再进入代码，避免后期返工
- **UG4=B**（monorepo + workspace）：对于内部单团队交付最友好，也便于后续按需拆仓
- **UG5=B**（抽样校验）：对 V1 交付速度友好，P0 Story 保底质量

以上为建议，最终以你的答案为准。
