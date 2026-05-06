# 工作单元依赖（Unit of Work Dependency）— 小说仿写生成应用

**版本**：1.0
**日期**：2026-04-27
**Parallel Strategy**: UG2=A 最大并行（U1 完成后 U2-U7 全部可并行）
**AI-DLC Processing Order**: UG3=A 按 Unit 编号顺序串行（U1→U2→U3→U4→U5→U6→U7）

---

## 1. 依赖矩阵

> 行 = 依赖方，列 = 被依赖方。`✓` = 强依赖（必须先完成）；`△` = 弱依赖（可 mock 并行开发）。

| | U1 | U2 | U3 | U4 | U5 | U6 | U7 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **U1** | — |   |   |   |   |   |   |
| **U2** | ✓ | — |   |   |   |   |   |
| **U3** | ✓ | △ | — |   |   |   |   |
| **U4** | ✓ |   | △ | — |   |   |   |
| **U5** | ✓ |   |   | △ | — |   |   |
| **U6** | ✓ | △ | △ | △ | △ | — |   |
| **U7** | ✓ |   | △ | △ | △ |   | — |

**说明**：
- **U1 是所有 Unit 的强依赖**（基础设施 + 共享库 + 认证 + 存储抽象）
- U2 与 U3：U3 通常需要 U2 采集的 Markdown 作为输入，但可用固定样本 fixture 并行开发
- U3 与 U4：U4 需要 U3 写入的 Memory，但可 mock MemoryFacade 并行
- U4 与 U5：U5 监听 U4 的 chapter.completed 事件，可 mock 事件并行
- U6/U7 与后端：前端可基于 OpenAPI mock server 先行开发，待 API 真实可用时集成

---

## 2. 关键路径

基于强依赖（✓）的拓扑排序：

```
                ┌──────────────┐
                │  U1 Platform │
                │   & Infra    │
                └──────┬───────┘
                       │
       ┌───────┬───────┼───────┬──────┬──────┐
       ▼       ▼       ▼       ▼      ▼      ▼
    ┌────┐  ┌────┐  ┌────┐  ┌────┐ ┌────┐ ┌────┐
    │ U2 │  │ U3 │  │ U4 │  │ U5 │ │ U6 │ │ U7 │
    └────┘  └────┘  └────┘  └────┘ └────┘ └────┘
        （U1 完成后全部可并行）
```

**关键路径**（纯强依赖）：**U1 → 任意其他 Unit**

---

## 3. 并行开发策略（UG2=A）

### 阶段 1：U1 独立完成
人力：2-3 人（Platform Team）
- 搭建 CDK 基础设施
- 实现 4 个共享 Adapter（Auth / Storage / Observability / MemoryFacade 骨架）
- 搭建 monorepo + CI/CD
- 初始化 Cognito、DynamoDB schema、S3、Neptune、OpenSearch、AgentCore 6 服务
- 多租户渗透测试脚本

### 阶段 2：U2-U7 全部并行启动
人力：6-10 人（按 Unit 分组）

| Unit | 团队规模 | 可并行的 Mock |
|---|---|---|
| U2 Ingestion | 1-2 人 | — |
| U3 Understanding | 2-3 人 | U2 Mock fixture（几个预置 Markdown 样本） |
| U4 Generation | 2-3 人 | U3 Mock MemoryFacade 返回预置 Facts |
| U5 Critic/Consistency/Moderation | 2 人 | U4 Mock chapter_completed 事件 |
| U6 Frontend + BFF | 2-3 人 | U2-U5 OpenAPI Mock server（msw / prism） |
| U7 Admin | 1-2 人 | U3/U4/U5 Mock Metrics 数据 |

### 阶段 3：集成测试
所有 Unit 完成后进入 Build and Test 阶段，做端到端集成。

---

## 4. AI-DLC 工作流处理顺序（UG3=A）

**Construction 阶段**严格按 Unit 编号顺序串行处理：

```
U1: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U2: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U3: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U4: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U5: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U6: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
U7: Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation
  ↓
Build and Test（ALWAYS）
```

每个 Unit 内每个阶段完成后都需用户批准才能进入下一阶段。

**UG2（最大并行）与 UG3（串行处理）的协调**：
- **AI-DLC 阶段**：按 UG3 串行生成设计与代码（这是 AI 工作流的推荐顺序）
- **实施阶段**：代码生成完毕后，团队按 UG2 最大并行策略实际部署与联调

---

## 5. 通信契约依赖

### 5.1 OpenAPI 契约
U6/U7 前端依赖 U2/U3/U4/U5/U7-API 的 OpenAPI 规范。契约优先策略：
1. U1 在共享库中定义 OpenAPI **骨架**（基于 components.md 的 REST 列表）
2. 每个后端 Unit 在 Functional Design 阶段完善自己的 OpenAPI 部分
3. U6/U7 前端基于 OpenAPI 生成 TS client（可用 mock server 先行）

### 5.2 Event Schema
`shared/events/*.schema.json` 定义跨 Unit 事件：
- `novel.analysis.*`（U3 发布，U6 订阅）
- `generation.*`（U4/U5 发布，U6 订阅）
- `moderation.*`（U5 发布，U6/U7 订阅）

### 5.3 DynamoDB Schema
集中定义在 U1 `packages/shared-types-py/` 中。任何 Unit 新增表/字段必须 PR 到 U1。

---

## 6. 依赖风险与缓解

| 风险 | 影响 Unit | 缓解 |
|---|---|---|
| U1 延期导致全部阻塞 | ALL | U1 最小可用集（MVP CDK + 基础 adapter）优先交付；逐步补全 |
| AgentCore 服务区域不支持 | U3/U4/U5 | U1 在最早阶段验证；如不支持则降级计划（自实现 Memory、弃用 Browser 改用 Lambda 爬虫） |
| Bedrock 配额不足导致 U3 性能不达标 | U3 | U1 提前申请配额提升；AD6=F 动态自适应兜底 |
| OpenAPI 契约变更破坏前端 | U6/U7 | OpenAPI 向后兼容原则 + 自动化契约测试（在 U1 CI 中运行） |
| Memory 语义不明确 | U3/U4/U5 | U1 与 U3 协作定义 Memory 数据 schema（packages/shared-types-py）|
| 前端 SSE 在 CloudFront/ALB 下超时 | U6 | U1 在 Infra 阶段配置合理 idle timeout（600s+）|

---

## 7. 关键里程碑

| 里程碑 | Unit 覆盖 | 交付验证 |
|---|---|---|
| M1: 基础设施就绪 | U1 | cdk deploy 成功、健康检查通过、渗透测试通过 |
| M2: 采集闭环 | U1 + U2 | 可上传 EPUB → 看到 S3/DDB 记录 |
| M3: 分析闭环 | U1+U2+U3 | 100 万字样本分析 < 15 min，报告可查询 |
| M4: 生成 MVP | U1+U2+U3+U4 | 可生成大纲 + 3 章，流式推送工作 |
| M5: 质量闭环 | U1+U2+U3+U4+U5 | Critic + 一致性 + Moderation 均打通 |
| M6: 用户 SPA 上线 | + U6 | 核心 P0 Story E2E 全绿 |
| M7: Admin 后台上线 | + U7 | Admin 功能 E2E 全绿 |
| M8: V1 GA | ALL | Build and Test 全绿，性能/安全指标达标 |
