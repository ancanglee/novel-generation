# 应用设计计划（Application Design Plan） — 小说仿写生成应用

## Purpose
本计划定义 Application Design 阶段的执行步骤、方法论，以及 6 个延后决策点 + 若干新澄清问题。请在文档底部的 `[回答]：` 处填写答案后回复"done"。

---

## Part 1 — 决策澄清问题

> **说明**：这些问题是 Workflow Planning 阶段记录的"延后决策"（D-1~D-6）加上 Application Design 发现的新关键选择。我的推荐会标注 ✓。

### Question AD1 — 知识图谱存储（D-1）
Q7 要求"节点=地点/人物/事件，边=关系"的知识图谱。考虑到成本与复杂度：

A) **Amazon Neptune**（专业图数据库，Gremlin/openCypher 查询）✓
  - 优点：查询表达力强，支持复杂路径/关系推理
  - 缺点：成本高（最小实例 ~$0.35/h），运维复杂
B) **DynamoDB 自建轻量图**（PK=节点ID，SK=边）
  - 优点：成本低，运维简单，与其他表同栈
  - 缺点：复杂图查询需要应用层实现
C) **Neo4j on EC2** 或 **Neo4j Aura 托管**（第三方）
  - 优点：生态成熟
  - 缺点：不如 Neptune 原生集成
D) **两阶段**：MVP 用 B（DynamoDB 自建），V2 评估后迁移到 A
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question AD2 — 向量检索（D-2）
一致性召回、风格向量检索、参考片段召回等需要向量检索：

A) **Amazon OpenSearch Serverless + kNN** ✓
  - 优点：AWS 托管、支持混合检索（BM25 + vector）、弹性伸缩
  - 缺点：基础消费门槛（2 OCU 起）
B) **Amazon Aurora PostgreSQL + pgvector**
  - 优点：与关系数据共库，事务友好
  - 缺点：向量性能不如专用引擎
C) **Amazon Bedrock Knowledge Bases**（内置向量能力，直接对接 S3）
  - 优点：集成度最高，零运维
  - 缺点：灵活性较低，费用按查询计
D) **AgentCore Memory 内置语义检索**（如果 AgentCore Memory 支持语义召回，则复用）
  - 优点：零额外存储组件
  - 缺点：取决于 AgentCore Memory 能力边界
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question AD3 — Admin UI 形态（D-3）
admin 后台（US-08-01~04）的形态：

A) **嵌入主 SPA，按角色路由隔离** ✓
  - 优点：单一前端仓库，复用登录/BFF/组件库
  - 缺点：admin 代码与用户代码混在一起，打包体略大（可 code splitting 缓解）
B) **独立的 admin React 子应用**（独立域名或 /admin 子路径）
  - 优点：职责分离、独立部署、独立安全边界
  - 缺点：两套前端工程，组件库需共享包
C) **纯 API + 临时用 Retool / AppSmith**（低代码 admin）
  - 优点：零前端开发成本
  - 缺点：依赖第三方，定制能力有限
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question AD4 — 流式推送协议（D-4）
章节生成的流式返回（US-06-01）：

A) **Server-Sent Events (SSE)** ✓
  - 优点：HTTP 单向、简单、自动重连（通过 lastEventId）、对 CloudFront 友好
  - 缺点：只能服务端→客户端（足够生成场景）
B) **WebSocket**
  - 优点：双向、可发送用户取消指令
  - 缺点：部署/代理复杂，需额外处理 keepalive
C) **Long Polling**
  - 缺点：性能差、代码丑
D) **SSE + REST（取消用 REST）** ✓（另一种组合）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question AD5 — 异步编排（D-5）
长时任务（分析、章节批量生成、一致性校验）的编排：

A) **AWS Step Functions（标准工作流）** ✓
  - 优点：可视化、可重试、内置错误处理、状态持久化一年
  - 缺点：每次状态转换费用（但长时任务可忽略）
B) **纯 SQS + ECS Worker + DynamoDB 状态机**
  - 优点：最灵活、无状态转换费用
  - 缺点：自行实现重试/补偿/可视化
C) **Step Functions（Express）+ SQS 混合**：短任务用 Express Workflow，长任务用 Standard Workflow
D) **AgentCore Runtime 自带的工作流编排**（如果提供）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question AD6 — 细读阶段并发上限（D-6）
细读阶段按章节并行处理受 Bedrock 配额约束。默认每账号 Claude Sonnet 的并发 RPS 有限（根据区域不同）。

A) **固定并发 = 10**（保守，几乎不会触发限流）
B) **固定并发 = 20** ✓（平衡性能与配额）
C) **固定并发 = 50**（激进，需申请提升配额）
D) **动态自适应**：从 10 起步，根据 throttle 错误率动态调节（推荐但实现复杂）
E) **admin 可配置**（默认 50，可改）
F) Other (please describe after [回答]： tag below)

[回答]： F. 

### Question AD7 — Agent 实现方式
Agent 框架选择：

A) **直接使用 AgentCore Python SDK + Bedrock Converse API** ✓
  - 优点：最贴近平台、开销小
  - 缺点：多 Agent 协作需自行编排
B) **Strands Agents / LangGraph / CrewAI 等开源框架**
  - 优点：社区 Agent 模式丰富
  - 缺点：与 AgentCore 的集成需适配
C) **Amazon Bedrock Agents + AgentCore Runtime 混合**
  - 优点：Bedrock Agents 的 action groups / KB 开箱即用
  - 缺点：两套概念并存
D) Other (please describe after [回答]： tag below)

[回答]： B. 使用Strands Agents + AgentCore结合的方式。

### Question AD8 — 服务划分风格
Python 后端的内部服务划分：

A) **模块化单体 (Modular Monolith)** ✓
  - 一个 FastAPI 应用，按模块（ingestion/understanding/generation/critic/admin）分 routers
  - 优点：开发/调试/部署简单，模块边界清晰
  - 缺点：单点扩缩容
B) **微服务（每个领域独立 ECS 服务）**
  - 优点：独立扩缩容、独立发布
  - 缺点：运维复杂度 ×N、分布式事务痛
C) **混合**：admin + 用户 API 一个服务；Agent 执行层独立为 Worker 服务（由 SQS 驱动）
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question AD9 — BFF 的职责范围
Node.js BFF 做什么？

A) **Thin BFF**：仅 API 代理 + Cognito 会话/Cookie 管理 + SSE 转发 + 静态文件 ✓
  - 优点：逻辑简单，少出错
  - 缺点：某些聚合场景多跳调用
B) **Fat BFF**：A + 按页面聚合多个后端 API（减少前端请求数）
  - 优点：前端更简单
  - 缺点：BFF 容易变业务服务，膨胀难维护
C) **中间**：A 为主 + 仅为仪表盘页面做数据聚合
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question AD10 — 审计日志存储
所有管理/权限/审核操作的审计日志：

A) **DynamoDB 专用表**（按 teamId + timestamp 分区）✓
B) **CloudWatch Logs + OpenSearch 索引**
C) **S3（JSON Lines 按天分区）+ Athena 查询**
D) A + C：热数据 DynamoDB，冷数据归档 S3
E) Other (please describe after [回答]： tag below)

[回答]： A

---

## Part 2 — 执行 checklist（将在用户批准后执行）

- [x] Step A1: 基于答案确定组件列表
- [x] Step A2: 生成 `components.md`（组件定义 + 职责 + 接口）
- [x] Step A3: 生成 `component-methods.md`（方法签名，不含详细业务规则）
- [x] Step A4: 生成 `services.md`（服务编排模式）
- [x] Step A5: 生成 `component-dependency.md`（依赖矩阵 + 通信模式 + 数据流图）
- [x] Step A6: 校验设计完整性与一致性
- [x] Step A7: 更新 aidlc-state.md

---

## Part 3 — 预计组件列表（供参考）

基于需求和 Story，我预计会划分如下组件（最终以用户答案为准）：

| # | 组件 | 大致职责 | 所属 Unit |
|---|---|---|---|
| C-01 | **WebFrontend** | React SPA，用户与 admin 页面 | U6 |
| C-02 | **NodeBff** | Node.js BFF，Cognito 会话、API 代理、SSE 中继 | U6 |
| C-03 | **ApiService** | Python FastAPI，REST API 入口 | U1/U2/U4/U7 |
| C-04 | **IngestionService** | 文件上传、格式转换、Browser 下载、URL 抓取 | U2 |
| C-05 | **UnderstandingAgent** | 类型/人物/地图/风格分析编排 | U3 |
| C-06 | **GenerationAgent** | 大纲、章节、Self-Critique | U4 |
| C-07 | **CriticAgent** | 独立章节质量评审 | U5 |
| C-08 | **ConsistencyAgent** | 全局一致性扫描 | U5 |
| C-09 | **ModerationAgent** | 敏感内容预标记 | U5 |
| C-10 | **MemoryStore**（抽象层）| 封装 AgentCore Memory / Neptune / 向量检索 | U3/U4/U5 |
| C-11 | **WorkflowOrchestrator** | Step Functions 定义 + 触发器 | U1 |
| C-12 | **AdminService** | 用户/团队/模板/模型配置 | U7 |
| C-13 | **ObservabilityService** | 指标/trace/告警聚合 | U1/U7 |
| C-14 | **AuthService**（逻辑）| Cognito + AgentCore Identity 集成 | U1 |
| C-15 | **StorageAdapter**（逻辑）| S3/DynamoDB/OpenSearch 统一封装 | U1 |

---

## Part 4 — 推荐组合（供参考）

我的综合推荐：
- **AD1=D**（MVP 用 DynamoDB 自建图，后评估 Neptune）— 降低初期成本与复杂度
- **AD2=A**（OpenSearch Serverless）— 检索能力与弹性最匹配
- **AD3=A**（嵌入主 SPA 按角色路由）— V1 单仓快速交付
- **AD4=D**（SSE + REST 取消）— 生成场景最佳
- **AD5=A**（Step Functions 标准工作流）— 长时任务可视化与可靠性
- **AD6=E**（默认 20 + admin 可配）— 既保守又灵活
- **AD7=A**（AgentCore SDK + Bedrock Converse）— 原生性能最好
- **AD8=C**（混合：API 单体 + Worker 服务）— 解决生成任务的长耗时问题
- **AD9=A**（Thin BFF）— 避免业务逻辑泄漏到 BFF
- **AD10=D**（DynamoDB 热 + S3 归档）— 成本与查询平衡

以上是推荐，具体选择以你的答案为准。
