# 工作单元（Unit of Work）— 小说仿写生成应用

**版本**：1.0
**日期**：2026-04-27
**Unit Count**: 7（UG1=A）
**Repo Strategy**: monorepo + workspace（UG4=B）
**Verification**: 严格自动化 AC 覆盖（UG5=A）

---

## Unit 清单

| ID | Name | Type | 复杂度 | 主要所有者 |
|---|---|---|---|---|
| U1 | Platform & Infrastructure | Platform | 高 | Platform Team |
| U2 | Ingestion Service | Service | Medium | Backend Team A |
| U3 | Understanding Agents | Agent Service | 高 | AI Team |
| U4 | Generation Agents | Agent Service | 高 | AI Team |
| U5 | Critic, Consistency & Moderation | Agent Service | Medium | AI Team |
| U6 | Frontend (User) + BFF | Frontend | 高 | Frontend Team |
| U7 | Admin (Frontend + API) | Frontend + Service | Medium | Full-Stack Team |

---

## U1 — Platform & Infrastructure

### Purpose
提供所有其他 Unit 所需的基础设施、跨切面能力与共享库。

### Components
- C-13 WorkflowOrchestrator（Step Functions 状态机骨架）
- C-15 AuthAdapter（Cognito + AgentCore Identity 封装）
- C-16 StorageAdapter（S3 / DynamoDB / 可选 Redis 抽象）
- C-17 ObservabilityAdapter（日志 / metrics / trace 封装）
- C-12 MemoryFacade（骨架，具体实现随 U3 完善）

### 交付物
- **CDK 基础设施**（Python CDK）
  - VPC + Subnets + NAT + VPCE
  - Cognito User Pool + Identity Pool + Google/GitHub IdP 集成
  - ECS Cluster + Task Execution Roles + Task Definitions 基类
  - ALB + Target Groups 基类
  - CloudFront + WAF + Route53
  - DynamoDB 基础表（users, teams, jobs, model_configs, audit_events）
  - S3 buckets（novels-raw, generations, exports）
  - Neptune Cluster
  - OpenSearch Serverless Collection
  - SQS 队列（5 个）+ DLQ
  - EventBridge default bus + rules
  - Step Functions IAM roles
  - AgentCore Memory / Gateway / Browser / Observability / Identity / Runtime 配置
  - Secrets Manager（Claude Opus/Sonnet 模型 id、Bedrock Region 配置）
- **Python Shared Libraries**（monorepo workspace 内）
  - `packages/auth-adapter`
  - `packages/storage-adapter`
  - `packages/observability-adapter`
  - `packages/memory-facade`（骨架）
  - `packages/shared-types`（pydantic models）
- **TypeScript Shared Libraries**
  - `packages/api-client`（OpenAPI → TS）
  - `packages/shared-types`（TS）
  - `packages/ui`（shadcn/ui + 业务组件）
- **CI/CD**
  - GitHub Actions 工作流：lint、test、build、deploy-dev、deploy-prod
  - CodePipeline 桥接（可选）
- **多租户渗透测试脚本**（NFR US-NFR-03）

### 覆盖 Stories
- US-NFR-03 多租户强隔离
- US-NFR-05 全链路可观测
- 为所有其他 Unit 提供底座（部分）

### 前置条件
- AWS 账号已具备 Bedrock、AgentCore、Neptune、OpenSearch Serverless 访问权限
- 目标区域已开通 Claude Opus 4.7 / Sonnet 4.6 / Sonnet 4.7 / Haiku 4.5

### 退出标准
- `cdk deploy` 成功拉起所有基础设施
- 健康检查端点（/healthz）返回 200
- 渗透测试脚本通过
- AgentCore 6 个服务可通过 SDK 连接

---

## U2 — Ingestion Service

### Purpose
负责小说采集：上传、格式转换、公版书搜索下载、URL 抓取。

### Components
- C-06 IngestionModule（属于 ApiService）
- C-04 ApiService 的 /novels 子路由
- 与 AgentCore Browser 的集成

### 交付物
- **Python Package**：`services/ingestion/`
  - FastAPI router for `/api/v1/novels/*`
  - 格式解析器（TXT / EPUB / PDF / DOCX / Markdown → 统一 Markdown）
  - 章节切分器（启发式 + LLM 辅助）
  - S3 / DynamoDB 落盘
- **Step Functions**：`novel-download-workflow`（Browser 触发）
- **AgentCore Gateway 工具定义**：`fetch_public_domain`, `crawl_url`
- **单元测试 + 集成测试**

### 覆盖 Stories
- US-02-01 上传本地文件
- US-02-02 公版书搜索
- US-02-03 URL 抓取
- US-02-04 小说库列表

### 前置条件
- U1 完成（S3、DynamoDB、AgentCore Browser、Step Functions 基础）
- StorageAdapter + AuthAdapter 可用

### 退出标准
- 所有 Q3=D 指定格式（TXT/EPUB/PDF/DOCX/Markdown）解析通过
- 50MB EPUB 在 30s 内完成上传与入库
- US-02-01~04 的自动化 AC 测试通过

---

## U3 — Understanding Agents

### Purpose
小说理解 Agent 群的实现：粗读 + 细读 + 分类/人物/地图/风格分析 + Memory 写入。

### Components
- C-07 UnderstandingAgent（含 6 个 sub-agent）
- C-12 MemoryFacade 完整实现（AgentCore Memory + Neptune + OpenSearch）
- C-05 WorkerService 的 analysis-queue 消费者

### 交付物
- **Python Packages**：
  - `services/worker-analysis/`（SQS 消费、Strands Agents 编排、AgentCore Runtime 集成）
  - `packages/memory-facade/`（完整版：remember/recall/upsertGraph/searchSimilar/hybridSearch）
- **Step Functions**：`analysis-workflow`（粗读 → 并行分析 → 细读 Map state → Memory 写入）
- **Analysis Schema 管理**（类型模板骨架，供 admin 管理）
- **动态并发控制器**（AD6=F：默认 20 + admin 可配 + 按 throttle 自适应）
- **Agent Prompts**：系统 prompt 模板、few-shot 示例
- **单元测试 + 集成测试 + 端到端测试**（100 万字样本）

### 覆盖 Stories
- US-03-01 触发分析
- US-03-02 类型鉴别
- US-03-03 人物报告
- US-03-04 地图与路线
- US-03-05 风格雷达图
- US-NFR-01 性能：100 万字 < 15 分钟

### 前置条件
- U1 完成（Neptune、OpenSearch、AgentCore Memory/Runtime、SQS）
- U2 完成（需采集好的 Markdown 作为输入）

### 退出标准
- 100 万字端到端分析 p95 ≤ 15 分钟
- 抽样 AC 自动化测试通过
- Memory 写入幂等性验证通过

---

## U4 — Generation Agents

### Purpose
小说生成 Agent 群：大纲生成、章节流式生成、Self-Critique、两种模式（仿写/续写）。

### Components
- C-08 GenerationAgent（Outline / Chapter / SelfCritique / ModeRouter）
- C-05 WorkerService 的 generation-queue 消费者

### 交付物
- **Python Package**：`services/worker-generation/`
- **Step Functions**：`outline-workflow`, `chapter-workflow`
- **流式输出实现**：Bedrock Converse Stream → EventBridge → ApiService SSE
- **Cancel 机制**：DynamoDB cancel flag + Worker 轮询
- **风格注入模块**：StyleVector → prompt 片段
- **Memory 召回模块**：生成前检索相关事实并注入 prompt
- **API 端点**：`/generations`、`/jobs/{id}/stream`、`/jobs/{id}/cancel`（属于 ApiService）
- **单元测试 + 集成测试**

### 覆盖 Stories
- US-04-01 / US-04-02 / US-04-03 生成配置
- US-05-01 / US-05-02 大纲
- US-06-01 流式生成
- US-06-02 Memory 约束
- US-06-04 编辑/打回
- US-NFR-02 单章 < 60 秒

### 前置条件
- U1、U3 完成（Memory 必须可用）

### 退出标准
- 单章 3000 字 ≤ 60 秒（p95）
- 流式首字节 ≤ 3 秒
- 取消功能验证
- 抽样 AC 自动化测试通过

---

## U5 — Critic, Consistency & Moderation

### Purpose
三类后处理 Agent：独立章节 Critic、周期性全局一致性校验、敏感内容预标。

### Components
- C-09 CriticAgent
- C-10 ConsistencyAgent
- C-11 ModerationAgent
- C-05 WorkerService 的 critic-queue / consistency-queue / moderation-queue 消费者

### 交付物
- **Python Packages**：
  - `services/worker-critic/`
  - `services/worker-consistency/`
  - `services/worker-moderation/`
- **Step Functions**：`consistency-workflow`（每 N 章触发）
- **API 端点**：`/critiques/{chapter_id}`, `/consistency/{novel_id}`, `/reviews/*`
- **事件处理**：监听 `generation.chapter.completed` 事件自动入队
- **ContentModerator UI 数据接口**
- **单元测试 + 集成测试**

### 覆盖 Stories
- US-06-03 双层 Critic
- US-06-05 周期性一致性
- US-09-01 审核队列
- US-09-02 段落级打回

### 前置条件
- U1、U3、U4 完成

### 退出标准
- 每章 Critic 在 30 秒内完成（Opus 4.7）
- 一致性校验（10 章规模）在 2 分钟内完成
- 抽样 AC 自动化测试通过

---

## U6 — Frontend (User) + BFF

### Purpose
普通用户与 Team 成员使用的 React SPA + Node.js BFF。

### Components
- C-01 WebFrontend (User)
- C-03 NodeBff

### 交付物
- **React SPA**（`apps/frontend-user/`）
  - 登录/注册流程（Cognito Hosted UI）
  - 仪表盘、小说库、采集页、分析报告页（含人物关系图、风格雷达图、地图可视化）
  - 生成配置页、大纲审核页、章节生成与审阅页（含 SSE 流式）
  - Critic 建议面板
  - 导出页与在线阅读器
- **Node.js BFF**（`apps/bff-user/`）
  - Cognito 会话/Cookie
  - API 反代
  - SSE 中继
- **共用 UI 组件库**（`packages/ui/`）
- **API Client 生成**（OpenAPI → TS）
- **Docker 镜像**（单容器，包含 BFF + 静态产物）
- **E2E 测试（Playwright）**

### 覆盖 Stories
- US-00-01 首页
- US-00-02 注册登录
- US-01-01 仪表盘
- US-01-02 / US-01-03 团队协作
- US-02-01~04 采集页（前端部分）
- US-03-02~05 分析报告查看
- US-04-01~03 生成配置
- US-05-01 / US-05-02 大纲
- US-06-01 / US-06-04 章节流式与编辑
- US-07-01 / US-07-02 导出与阅读

### 前置条件
- U1 完成（Cognito、CloudFront、ECS、共享 UI 库）
- ApiService 的 OpenAPI 规范（可先用 mock 并行开发）

### 退出标准
- Lighthouse 性能分 > 80
- 抽样 P0 AC E2E 测试通过
- CloudFront 部署 + BFF 容器运行

---

## U7 — Admin (Frontend + API)

### Purpose
Admin 独立后台（前端子应用 + API 模块）。

### Components
- C-02 WebFrontend (Admin)
- C-14 AdminModule（属于 ApiService 的 /admin 路由）

### 交付物
- **React Admin SPA**（`apps/frontend-admin/`，独立应用，独立域名/路径）
  - 用户/团队管理
  - 任务阶段-模型配置
  - 类型标签与分析模板管理
  - 全局监控面板（聚合 AgentCore Observability + CloudWatch）
  - 审计日志查询
  - 告警配置
  - 细读并发配置（AD6=F admin 端）
- **Python Admin API**（`services/api-admin/` or 嵌入 api-service 的 `/admin` 路由）
  - 所有 C-14 AdminModule 方法的实现
  - `@require_role("admin")` 守卫
- **Docker 镜像**
- **E2E 测试**

### 覆盖 Stories
- US-08-01 用户/团队管理
- US-08-02 模型配置
- US-08-03 类型与模板管理
- US-08-04 全局监控
- US-09-01 / US-09-02 审核（Admin 侧入口，ContentModerator 视角使用）
- US-NFR-04 成本护栏 admin 端配置

### 前置条件
- U1 完成（Cognito Admin Group、DynamoDB 配置表、ObservabilityAdapter）
- U3/U4/U5 完成（才能聚合监控指标与模板生效）

### 退出标准
- Admin SPA 独立部署可用
- 非 Admin 用户访问 403
- 抽样 AC 自动化测试通过

---

## 跨 Unit 共享规范

### 代码仓库
```
novel-generation/                 (monorepo 根)
├── apps/
│   ├── frontend-user/            (U6)
│   ├── frontend-admin/           (U7)
│   └── bff-user/                 (U6)
├── services/
│   ├── api/                      (U1/U2/U4/U7 共享 FastAPI 单体)
│   ├── worker-analysis/          (U3)
│   ├── worker-generation/        (U4)
│   ├── worker-critic/            (U5)
│   ├── worker-consistency/       (U5)
│   └── worker-moderation/        (U5)
├── packages/
│   ├── auth-adapter/             (U1)
│   ├── storage-adapter/          (U1)
│   ├── observability-adapter/    (U1)
│   ├── memory-facade/            (U1 骨架 + U3 实现)
│   ├── shared-types-py/          (U1)
│   ├── shared-types-ts/          (U1)
│   ├── api-client-ts/            (U1 generated)
│   └── ui/                       (U1)
├── infra/
│   └── cdk/                      (U1)
├── tests/
│   ├── e2e/                      (跨 Unit)
│   └── security/                 (U1 渗透测试)
└── .github/workflows/            (CI/CD)
```

### 代码标准
- Python：black + ruff + mypy + pytest
- TypeScript：biome + tsc --strict + vitest + playwright
- Commit：Conventional Commits
- PR：最小粒度，每个 PR 关联 Story ID
- 自动化 AC 映射（UG5=A）：每个 P0 Story 至少 1 个 E2E 测试引用其 Story ID

### 测试策略（UG5=A 严格覆盖）
- 单元测试 → 每模块
- 集成测试 → 每 Service
- 合同测试（OpenAPI schema 校验）→ API 层
- E2E 测试（Playwright）→ 每 P0 Story 至少一个
- 性能测试 → NFR Stories
- 安全/渗透测试 → US-NFR-03

---

## 复杂度估算

| Unit | 预计代码行 | 预计会话轮次（AI-DLC）|
|---|---|---|
| U1 | ~8000 LOC CDK + libs | 6-8 |
| U2 | ~2500 LOC | 3-4 |
| U3 | ~5000 LOC + prompts | 6-8 |
| U4 | ~4000 LOC + prompts | 5-7 |
| U5 | ~3000 LOC + prompts | 4-6 |
| U6 | ~8000 LOC（TS+Node）| 6-8 |
| U7 | ~4000 LOC（TS+Py）| 4-6 |
| **合计** | **~34,500 LOC** | **34-47 轮** |
