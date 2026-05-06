# 组件清单（Components）— 小说仿写生成应用

**版本**：1.0
**日期**：2026-04-27

---

## 组件概览

| # | 组件 | 类型 | 所属 Unit | 部署形态 |
|---|---|---|---|---|
| C-01 | WebFrontend (User) | UI | U6 | Docker on ECS Fargate |
| C-02 | WebFrontend (Admin) | UI | U7 | Docker on ECS Fargate（独立子应用）|
| C-03 | NodeBff | BFF | U6 | Docker on ECS Fargate（同容器）|
| C-04 | ApiService | Backend | U1/U2/U4/U7 | Docker on ECS Fargate |
| C-05 | WorkerService | Backend | U3/U4/U5 | Docker on ECS Fargate（SQS driven）|
| C-06 | IngestionModule | Module | U2 | 属于 ApiService |
| C-07 | UnderstandingAgent | Agent | U3 | 属于 WorkerService |
| C-08 | GenerationAgent | Agent | U4 | 属于 WorkerService |
| C-09 | CriticAgent | Agent | U5 | 属于 WorkerService |
| C-10 | ConsistencyAgent | Agent | U5 | 属于 WorkerService |
| C-11 | ModerationAgent | Agent | U5 | 属于 WorkerService |
| C-12 | MemoryFacade | 抽象层 | U3/U4/U5 | 库，嵌入 WorkerService |
| C-13 | WorkflowOrchestrator | 基础设施 | U1 | AWS Step Functions |
| C-14 | AdminModule | Module | U7 | 属于 ApiService |
| C-15 | AuthAdapter | 抽象层 | U1 | 库，嵌入 ApiService/WorkerService |
| C-16 | StorageAdapter | 抽象层 | U1 | 库 |
| C-17 | ObservabilityAdapter | 抽象层 | U1 | 库 |

---

## C-01 WebFrontend (User)

**Purpose**: 面向 RegularUser / TeamMember / ContentModerator 的 React SPA。

**Responsibilities**:
- 登录后仪表盘、小说库、分析报告查看、生成配置、大纲/章节审阅、导出
- 通过 Cognito Hosted UI 登录，取得 id_token 并交给 BFF 换 HttpOnly Cookie
- 通过 BFF 的 SSE 中继接收章节流式文本
- 内容审核员的段落级高亮与批注视图

**Interfaces (consumer)**:
- REST: `/api/v1/...`（经 BFF 反代）
- SSE: `/api/v1/jobs/{id}/stream`

**Tech**: React 18 + TS + Vite + Tailwind + shadcn/ui + TanStack Query + Zustand + @tanstack/react-router

---

## C-02 WebFrontend (Admin)

**Purpose**: 面向 Admin 的独立 React 子应用（AD3=B）。

**Responsibilities**:
- 用户/团队 CRUD、任务阶段-模型配置、类型与分析模板管理、全局监控仪表盘
- 审计日志查询、告警阈值配置

**独立原因**：
- 安全边界：独立子路径 `/admin`，独立 IAM 与 Cognito Group 校验
- 打包体与发布节奏独立
- 与 User SPA 共享 UI 组件包（npm workspace）

**Tech**: 同 C-01

---

## C-03 NodeBff

**Purpose**: 前端与后端之间的 Thin BFF（AD9=A）。

**Responsibilities**:
- 静态资源服务（Vite 构建产物）
- Cognito 会话：接收 id_token，签发 HttpOnly Session Cookie，刷新 token
- API 代理：将 `/api/*` 反代到 ApiService（携带 Cognito JWT）
- SSE 中继：把后端 SSE 透传给浏览器（保持长连接）
- 安全：CSRF token、CSP、HSTS 等

**非责任**（明确排除）：
- 业务逻辑（保持 Thin）
- 跨端数据聚合（至多只对仪表盘做极轻量合并）

**Interfaces**:
- HTTP: 对外端口 3000
- 依赖: ApiService（HTTP）、Cognito User Pool（OIDC）

**Tech**: Node.js LTS + Express + http-proxy-middleware + openid-client + cookie-session

---

## C-04 ApiService

**Purpose**: Python FastAPI 单体，REST 入口（AD8=C 的 API 端）。

**Responsibilities**:
- 认证：验证 Cognito JWT；映射 userId/teamId/roles 到 request context
- 授权：基于 teamId 的多租户隔离守卫
- 业务 REST 端点：小说管理、任务管理、配置管理、审计查询
- 触发长时任务：向 Step Functions 提交 execution，返回 jobId
- SSE 端点：从 SQS/Redis 订阅事件流并推送给 NodeBff

**模块划分**（router 级）：
- `/api/v1/auth` — 轻量（主要由 BFF+Cognito 处理）
- `/api/v1/novels` — IngestionModule
- `/api/v1/analyses` — 触发+查询分析任务
- `/api/v1/generations` — 触发+查询生成任务、大纲、章节
- `/api/v1/reviews` — 章节/段落审核
- `/api/v1/admin` — AdminModule（需 Admin 角色）

**Tech**: Python 3.12 + FastAPI + pydantic v2 + boto3 + AWS Lambda Powertools Logging

---

## C-05 WorkerService

**Purpose**: Python Worker，承载所有长耗时 Agent 任务（AD8=C 的 Worker 端）。

**Responsibilities**:
- 从 SQS 队列消费任务消息
- 调用 Strands Agents 框架（AD7=B）编排 Agent 链
- 执行 Agent（UnderstandingAgent / GenerationAgent / CriticAgent / ConsistencyAgent / ModerationAgent）
- 与 AgentCore Runtime 通信（Agent 执行托管）
- 通过 AgentCore Memory 读写 Agent 记忆
- 通过 AgentCore Gateway 调用外部工具（爬虫/解析器/翻译）
- 通过 AgentCore Browser 做公版书搜索与 URL 抓取
- 输出事件到 EventBridge/SNS，ApiService 的 SSE 端点订阅后转发给前端

**队列划分**：
- `analysis-queue`（理解任务）
- `generation-queue`（大纲+章节+Self-Critique）
- `critic-queue`（独立 Critic Agent）
- `consistency-queue`（周期性一致性校验）
- `moderation-queue`（敏感预标）

**Tech**: Python 3.12 + Strands Agents + AgentCore SDK + boto3 + asyncio

---

## C-06 IngestionModule

**Purpose**: 小说采集模块，属于 ApiService。

**Responsibilities**:
- 接收 multipart 上传（TXT/EPUB/PDF/DOCX/Markdown），调用格式解析器
- 触发 Browser-based 公版书搜索任务
- 触发 URL 抓取任务
- 章节切分（基于启发式 + LLM 辅助）
- 写入 S3 + DynamoDB

**Interfaces (provided)**:
- `POST /api/v1/novels/upload`
- `POST /api/v1/novels/download` — 公版书搜索下载
- `POST /api/v1/novels/crawl` — URL 抓取
- `GET /api/v1/novels` / `GET /api/v1/novels/{id}`
- `DELETE /api/v1/novels/{id}`

**依赖**: StorageAdapter, WorkflowOrchestrator（对 Browser 爬取触发 Step Functions）

---

## C-07 UnderstandingAgent

**Purpose**: 小说理解 Agent 群，属于 WorkerService。

**Sub-Agents**:
- **ClassificationSubAgent**：多标签类型鉴别（基于粗读样本）
- **CharacterSubAgent**：人物 Profile + 章节状态快照 + 关系图
- **MapSubAgent**：地点、足迹、知识图谱三元组
- **StyleSubAgent**：6 维度风格向量
- **RoughReadSubAgent**：粗读抽样（首/尾/等间距中间章）
- **DeepReadSubAgent**：细读逐章处理（并发受 AD6=F 控制）

**编排**: Strands Agents 以 Graph Pattern 组织——RoughRead → parallel(Classification, Character, Map, Style) → DeepRead(并行, 动态并发)。

**输出**: 事实三元组与结构化记忆 → MemoryFacade

---

## C-08 GenerationAgent

**Purpose**: 生成 Agent 群。

**Sub-Agents**:
- **OutlineAgent**：全书大纲（人物表、主线、章节主题）
- **ChapterAgent**：单章流式生成
- **SelfCritiqueAgent**：Layer-1 自检（与 ChapterAgent 串联）
- **ModeRouter**：根据"全新仿写 / 续写"选择不同的 prompt 骨架

**支持**:
- 流式输出（通过 Bedrock Converse Stream API）
- Memory 约束 prompt 构造（FR-6.1）
- 风格向量注入 prompt
- 可配置模型（通过 admin 配置映射，不同 sub-agent 可用不同模型）

---

## C-09 CriticAgent

**Purpose**: Layer-2 独立章节评审（FR-5.3）。

**Responsibilities**:
- 输入一章文本 + Memory 事实快照 + 风格向量
- 输出结构化"修改建议清单"：逻辑问题、人物走样、风格偏移、一致性违规
- 默认模型：Opus 4.7（admin 可改）

---

## C-10 ConsistencyAgent

**Purpose**: 周期性全局一致性校验（每 N 章一次）。

**Responsibilities**:
- 扫描所有已生成章节 + Memory 事实
- 识别矛盾：人物死亡/复活、时间线倒置、地点顺序错乱、修为等级反向
- 产出"修订建议"报告

---

## C-11 ModerationAgent

**Purpose**: 敏感内容预标记。

**Responsibilities**:
- 段落级扫描，标注涉及：色情/暴力/政治敏感/未成年人保护
- 推入 moderation-queue 让 ContentModerator 人工复核

---

## C-12 MemoryFacade

**Purpose**: 抽象封装多个记忆/检索组件。

**Responsibilities**:
- 统一 API 访问：AgentCore Memory（短期+长期）、Neptune（知识图谱）、OpenSearch Serverless（向量检索）
- 事实幂等写入（基于事实哈希）
- 读取时的多源聚合：例如"给我第 12 章生成前相关的所有事实"
- 多租户隔离（所有读写强制带 teamId 前缀）

**Interfaces (provided)**:
- `remember(teamId, novelId, facts)`
- `recall(teamId, novelId, query, top_k)`
- `upsertGraph(teamId, novelId, nodes, edges)`
- `searchSimilar(teamId, novelId, embedding, top_k)`
- `getCharacterSnapshot(teamId, novelId, characterId, chapter)`

**依赖**: AgentCore Memory SDK、Neptune gremlin client、OpenSearch python client、Bedrock Embeddings API

---

## C-13 WorkflowOrchestrator

**Purpose**: AWS Step Functions 工作流定义（AD5=A）。

**Workflows**:
- **AnalysisWorkflow**：粗读 → 并行(分类/人物/地图/风格) → 细读（Map 状态，动态并发）→ Memory 写入 → 完成
- **OutlineWorkflow**：获取配置 → OutlineAgent 调用 → Memory 写入 → 通知
- **ChapterWorkflow**：Memory 召回 → ChapterAgent 流式生成 → SelfCritique → 入 moderation-queue → 入 critic-queue
- **ConsistencyWorkflow**：触发器：每生成 N 章一次；扫描章节 → ConsistencyAgent → 报告写入 DynamoDB

**Tech**: AWS Step Functions Standard Workflow（状态持久化 1 年）

---

## C-14 AdminModule

**Purpose**: Admin 后台的 API 层。

**Responsibilities**:
- 用户/团队 CRUD
- 任务阶段-模型配置
- 类型与分析模板管理
- 审计日志查询
- 全局监控指标聚合（从 AgentCore Observability + CloudWatch）
- 告警阈值配置
- 细读并发上限配置（AD6=F 的 admin 端点）

**安全**: 所有端点要求 Cognito Group == `Admins`；独立 `/api/v1/admin/*` 前缀

---

## C-15 AuthAdapter

**Purpose**: 身份认证与授权统一封装。

**Responsibilities**:
- Cognito JWT 验证（JWKs 缓存）
- 解析 custom claims：teamId、roles
- AgentCore Identity 集成：为 Agent 获取下游工具的 workload token
- 多租户守卫装饰器：`@require_team_access`

---

## C-16 StorageAdapter

**Purpose**: S3 / DynamoDB / Redis 的统一抽象。

**Sub-Adapters**:
- **S3Adapter**：原文、生成稿、导出文件的 CRUD（按 teamId 前缀）
- **DynamoDBAdapter**：基于 pydantic 模型的 Repository 模式；所有表强制带 teamId PK
- **CacheAdapter**（可选）：ElastiCache/Redis 缓存 JWT、风格向量等

**多租户守卫**: 所有读写方法接收 teamId，禁止跨 team 访问（运行时断言）

---

## C-17 ObservabilityAdapter

**Purpose**: AgentCore Observability + X-Ray + CloudWatch 的统一门面。

**Responsibilities**:
- 结构化日志（JSON，含 teamId、jobId、agentId）
- Metrics 发射（token 用量、Agent 延迟、错误率）
- Trace 注入（X-Ray segment 传播到 Agent 调用）
- 为 admin 监控面板提供 QueryAPI

---

## 前端组件库（共享）

| 库 | 用途 |
|---|---|
| `@novelgen/ui` | shadcn/ui 二次封装 + 业务组件（风格雷达图、关系图、章节编辑器） |
| `@novelgen/api-client` | OpenAPI 生成的 TS 客户端（供 User SPA 与 Admin SPA 共用）|
| `@novelgen/types` | 共享 TypeScript 类型 |
