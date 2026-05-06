# 需求文档（Requirements Document）— 小说仿写生成应用 (Novel Generation App)

**版本**：1.0
**日期**：2026-04-27
**项目类型**：新建项目
**深度级别**：详尽

---

## 1. 意图分析摘要 (Intent Analysis Summary)

| 维度 | 判断 |
|---|---|
| **User Request** | 构建小说仿写生成应用：下载/上传原始小说 → 多维度理解 → 仿写/续写新小说 |
| **Request Type** | New Project |
| **Scope** | Cross-system（前端 SPA + Node.js BFF + Python Agent 后端 + 6 个 AgentCore 服务 + 多存储） |
| **Complexity** | Complex |
| **Depth** | 详尽 |

---

## 2. 业务目标 (Business Goals)

1. **G1 风格复制**：给定一本原始小说，系统能够学习其写作风格、类型特征、世界观，生成一本风格一致但情节全新的小说（全新仿写）或合理延续原作的新章节（续写）
2. **G2 可配置生成**：用户可自由选择风格维度、章节数、字数、参与审核的粒度
3. **G3 多类型可扩展**：系统支持多种小说类型（修仙、武侠、穿越、言情、悬疑、科幻、历史、都市…），且类型体系可由 admin 持续演进
4. **G4 前后一致性**：生成过程中保障人物、地点、时间线、修为等级等元素前后一致
5. **G5 多租户协作**：普通用户按 team/organization 隔离数据，admin 拥有全局视图

---

## 3. 角色 (Personas Summary)

| 角色 | 描述 | 核心能力 |
|---|---|---|
| **普通用户 (Regular User)** | 创作者、小说爱好者 | 上传/下载小说、触发分析、配置生成、审阅大纲与章节、导出成品 |
| **团队成员 (Team Member)** | 与创作者同属一个 team | 共享 team 内的小说与生成结果 |
| **Admin** | 系统管理员 | 所有用户数据只读查看、用户/团队/额度管理、模型配置、分析模板 (Schema) 管理、全局监控 |

---

## 4. 功能性需求 (Functional Requirements)

### FR-1. 小说采集 (Acquisition)
- **FR-1.1** 支持用户上传 TXT、EPUB、PDF、DOCX、Markdown 等多种格式，预处理统一转为 Markdown 存储
- **FR-1.2** 支持按书名搜索自动下载 **公版书库**（Project Gutenberg、中国哲学书电子化计划等），通过 AgentCore Browser 执行
- **FR-1.3** 支持用户粘贴 URL，由 AgentCore Browser 抓取单页正文并整理章节
- **FR-1.4** 版权合规由用户自行承担；系统在上传页面展示合规提示文案
- **FR-1.5** 原文按章节切分并存储到 S3；章节索引、元数据存 DynamoDB

### FR-2. 小说理解 (Understanding)
采用两阶段 + 章节增量的理解策略：
- **FR-2.1 粗读阶段**：抽样章节（首、尾、等间距中间章节）把握整体类型、主线、世界观
- **FR-2.2 细读阶段**：逐章处理，增量更新"全书记忆" (running memory)
- **FR-2.3 类型鉴别**：多标签分类（如"修仙+穿越+系统流"），LLM 自由生成标签；admin 可审核、合并、沉淀到标准类型库
- **FR-2.4 分析模板 (Schema) 机制**：每种小说类型对应一份模板（如修仙：境界列表、宗门、功法；言情：CP 线、情感节点）；LLM 先按模板骨架填充，再动态补充；admin 在后台维护与新增模板
- **FR-2.5 人物角色分析**：
  - Profile 卡片：姓名、性格、外貌、关键行为、与其他人物关系
  - 章节状态快照：每 N 章记录该人物的修为/心情/所处地点等
  - 人物关系图：师父/敌人/恋人/亲属等关系
- **FR-2.6 地图与路线分析**：
  - 线性足迹列表（包含所有出场角色，不限于主角）
  - 地点间关系（邻近/远近/所属国家/所属势力）+ 每个地点首次/最后出场章节
  - 知识图谱（节点 = 地点/人物/事件，边 = 关系），由 AgentCore Memory + Amazon Neptune 承载
- **FR-2.7 风格分析**：抽取多维度风格向量（基调、节奏、描写密度、对话占比、情感强度、世界观宏大度）
- **FR-2.8** 所有理解结果持久化到 AgentCore Memory（结构化记忆） + DynamoDB（元数据） + Neptune（图）

### FR-3. 生成模式 (Generation Modes)
- **FR-3.1 全新仿写 (Clean-Room)**：沿用原作的风格与类型特征，但人物、地名、情节均为全新
- **FR-3.2 续写 (Continuation)**：基于原作世界观、已有角色和地图，生成延续性章节
- 用户在前端自由切换两种模式

### FR-4. 风格控制 (Style Control)
- **FR-4.1 多维度风格向量**：用户可在前端调整基调、节奏、描写密度、对话占比、情感强度、世界观宏大度等滑块
- **FR-4.2 混合参考**：用户可上传多本小说作为风格参考，设置混合权重（例如 70% 作品 A + 30% 作品 B）
- **FR-4.3** 系统基于原作统计给出推荐风格向量初值

### FR-5. 生成编排 (Generation Orchestration)
- **FR-5.1 大纲阶段**：先生成全书大纲（人物表、主线、章节主题），用户审核通过后进入章节生成
- **FR-5.2 章节生成**：按大纲逐章生成，每章输出后可供用户审阅、编辑、打回重写
- **FR-5.3 AI 审核双层**：
  - Layer-1 **Self-Critique**：生成 Agent 内嵌自检，产出初版 + 改进点
  - Layer-2 **独立 Critic Agent**（可配置 Opus 4.7）：对章节做质量/一致性评审，输出"修改建议清单"
  - 最终由用户 Review & 确认
- **FR-5.4 章节数与字数**：用户自定义，系统基于原作统计给出推荐值（平均每章字数 × 总章节数）
- **FR-5.5 流式返回**：章节生成过程通过 SSE 实时推送到前端

### FR-6. 一致性保障 (Consistency)
- **FR-6.1 Memory 约束**：每章生成前从 AgentCore Memory 检索相关事实（涉及人物、地点、事件），作为 prompt 的一部分
- **FR-6.2 Self-Critique**：生成 Agent 自检并修正
- **FR-6.3 全局一致性校验**：每生成 N 章（可配置，如每 10 章）执行一次全书级别的一致性扫描，发现矛盾生成"修订建议"供用户审查
- **FR-6.4** 生成期间新增的人物/地点/事件同步写回 Memory 与知识图谱

### FR-7. 模型与 Agent 配置 (Model Config)
- **FR-7.1** Admin 可在后台为每个任务阶段独立配置 Bedrock 模型：
  - 类型鉴别、人物提取、地图提取、风格分析、大纲生成、章节生成、self-critique、Critic Agent、全局一致性校验
- **FR-7.2** 可选模型：Claude Opus 4.7、Claude Sonnet 4.6、Claude Sonnet 4.7、Claude Haiku 4.5（所有 Claude 4.x 家族）
- **FR-7.3** 提供每个任务阶段的默认推荐（参见附录 A）

### FR-8. AgentCore 服务编排
使用 AgentCore **全家桶**（6 个服务，≥ 3 的要求）：
- **FR-8.1 Runtime**：承载所有 Agent 流程（理解 Agent、大纲 Agent、章节 Agent、Critic Agent、一致性校验 Agent）
- **FR-8.2 Memory**：短期 + 长期记忆，存储小说结构化理解（人物 Profile、章节状态快照、事实图）
- **FR-8.3 Gateway**：对外工具统一网关（公版书下载器、EPUB/PDF/DOCX 解析器、翻译 API、向量检索等）
- **FR-8.4 Browser**：自动访问公版书库（A）+ 用户粘贴 URL 抓取（B）
- **FR-8.5 Observability**：全链路 tracing、token 用量、分阶段延迟指标
- **FR-8.6 Identity**：Workload identity，代理 Agent 访问下游工具的 token 获取与刷新（与 Cognito 分工清晰）

### FR-9. 前端界面 (Frontend)
- **FR-9.1** 登录/注册页（Cognito Hosted UI 或自研）
- **FR-9.2** 仪表盘（概览：我的小说数量、生成任务进度、团队共享内容）
- **FR-9.3** 小说上传/下载页（拖拽上传 + URL 抓取 + 公版书搜索）
- **FR-9.4** 分析结果查看页（类型标签、人物卡片、关系图可视化、地图路线图、风格雷达图）
- **FR-9.5** 生成配置页（模式选择：仿写/续写；风格滑块；章节数/字数；审核粒度）
- **FR-9.6** 生成结果查看/编辑/导出页（在线阅读、逐章编辑、Critic 建议面板、导出 TXT/EPUB/Markdown）
- **FR-9.7** Admin 后台：
  - 用户与团队管理、额度管理（预留，MVP 无限制）
  - 每任务阶段模型配置
  - 类型与分析模板管理
  - 全局监控（从 AgentCore Observability 聚合）

### FR-10. 多用户与权限 (Multi-Tenancy)
- **FR-10.1** 认证方式：Amazon Cognito User Pool + 社交登录（Google / GitHub）
- **FR-10.2** Domain = **团队级 (team/organization)**；每个普通用户归属一个 team；team 成员共享 team 内小说与生成结果
- **FR-10.3** Admin 可跨 team 查看所有数据
- **FR-10.4** AgentCore Identity 负责 Agent → 外部工具的 workload identity（与 Cognito 用户登录分工清晰）
- **FR-10.5** MVP 阶段不做用量配额（未来通过 DynamoDB 记账预留扩展点）

---

## 5. 非功能性需求 (Non-Functional Requirements)

### NFR-1. 性能
- **分析**：< 15 分钟 完成 100 万字小说的全量分析（粗读 + 细读）
- **大纲生成**：< 5 分钟
- **单章生成**（~3000 字）：< 60 秒
- **一致性校验**（每 N 章）：< 2 分钟
- **实现手段**：多线程/asyncio + 多 Agent 并行（人物/地图/风格三条分析流水线并行；章节生成可按大纲并行多章）

### NFR-2. 可扩展性
- 分析模板 (Schema) 可由 admin 动态新增，新类型不需要代码变更
- Agent 流程为插件化结构，新增 Agent 角色无需修改编排骨架

### NFR-3. 可靠性
- 长时任务（分析、生成）通过 Step Functions + SQS 异步编排，失败可从最近 checkpoint 重试
- AgentCore Memory 作为事实单一来源，重试不造成数据污染

### NFR-4. 安全与权限
- 所有 API 调用强制 Cognito JWT 验证
- 数据按 team 隔离（DynamoDB 的 PK 携带 teamId、S3 按 teamId 做前缀 + IAM 策略）
- Bedrock 调用由 Agent 角色代理，用户不直接获取 Bedrock API 权限

### NFR-5. 可观测性
- AgentCore Observability 采集全链路 tracing、token 用量、分阶段延迟
- CloudWatch 告警：Bedrock 异常率、单任务超时、Memory 写入失败

### NFR-6. 部署与区域
- **区域**：AWS 海外区（us-east-1 或 us-west-2，确保 Bedrock + AgentCore 完全可用）
- **加速**：CloudFront 全球分发，中国用户访问经边缘节点
- **IaC**：全部资源通过 AWS CDK 定义（Python CDK），一键部署

### NFR-7. 合规免责
- 产品条款页面展示合规声明：用户需自行确保上传 / 爬取内容的版权合规
- 系统不存储、不保留任何明确涉嫌侵权的抓取来源（基于黑名单可选扩展）

---

## 6. 技术栈 (Tech Stack)

| 层 | 技术 |
|---|---|
| **前端** | React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui + TanStack Query + Zustand |
| **前端中间层 (BFF)** | Node.js (LTS) + Express + SSE 流式；打包为 Docker 镜像 |
| **后端** | Python 3.12 + FastAPI + pydantic；Agent 代码基于 AgentCore Python SDK |
| **LLM** | Amazon Bedrock — Claude Opus 4.7 / Sonnet 4.6 / Sonnet 4.7 / Haiku 4.5 |
| **Agent 平台** | AgentCore Runtime / Memory / Gateway / Browser / Observability / Identity |
| **存储** | S3（原文 + 生成稿） · DynamoDB（元数据、用户、团队、模板） · Amazon Neptune（知识图谱） · OpenSearch Serverless（章节向量检索，用于一致性召回） |
| **认证** | Amazon Cognito User Pool + 社交 IdP（Google、GitHub） |
| **编排** | AWS Step Functions + SQS（长时任务） |
| **容器** | ECS Fargate（前端 BFF + Python 后端 API） |
| **CDN** | CloudFront |
| **IaC** | AWS CDK (Python) |
| **CI/CD** | GitHub Actions → CodePipeline |

---

## 7. 附录 A：默认任务-模型映射（推荐，admin 可修改）

| 任务阶段 | 默认模型 | 理由 |
|---|---|---|
| 类型鉴别 | Haiku 4.5 | 轻量分类任务 |
| 人物提取 | Sonnet 4.6 | 平衡成本与召回 |
| 地图/事件提取 | Sonnet 4.6 | 需较好的结构化理解 |
| 风格分析 | Sonnet 4.7 | 需理解细腻风格 |
| 大纲生成 | Opus 4.7 | 需全局创造力 |
| 章节生成 | Sonnet 4.7 | 质量 × 速度最佳平衡 |
| Self-Critique | Sonnet 4.6 | 快速修订 |
| Critic Agent | Opus 4.7 | 质量优先，深度审查 |
| 一致性校验 | Sonnet 4.6 | 大量调用，成本敏感 |

---

## 8. MVP / 完整 V1 范围（基于 Q25=C）

交付目标为 **完整 V1**，包含所有上述功能。建议按 Units 分解为多个 Unit 并行交付（将在 Workflow Planning / Units Generation 阶段决定）。

---

## 9. 关键假设 (假设)

1. 用户自行承担数据版权合规，系统不对此做法律拦截
2. 生成的"仿写"作品版权归生成用户所有（须用户与其 team 约定）
3. Bedrock 上 Claude 4.x 家族在目标区域可用
4. 生成过程中成本主要由 Bedrock 消费驱动；MVP 不做用量配额，但预留记账字段
5. 单小说最大规模：500 万字（对应约 10000 章），超出需分册处理

---

## 10. 开放问题 (Open Issues — Tracked for Later Phases)

| # | 问题 | 阶段 |
|---|---|---|
| O-1 | 知识图谱是否用 Neptune 还是 DynamoDB 自建？ | Application Design |
| O-2 | 章节向量检索是否用 OpenSearch Serverless 还是 pgvector / Aurora？ | Application Design |
| O-3 | Admin 管理前端的复杂度（是否可共用主 UI 还是独立项目？） | Application Design |
| O-4 | SSE vs WebSocket：流式推送章节生成进度的选型 | NFR Design |
| O-5 | Step Functions vs 纯 SQS worker：长时任务编排粒度 | Infrastructure Design |

---

## 11. 需求追溯表 (Requirements Traceability)

| Q# | 答案 | 对应 FR/NFR |
|---|---|---|
| Q1 | C | FR-1.4, NFR-7 |
| Q2 | C | FR-1.5, FR-2.8 |
| Q3 | D | FR-1.1 |
| Q4 | D | FR-2.3 |
| Q5 | C | FR-2.4 |
| Q6 | D | FR-2.1, FR-2.2 |
| Q7 | A+B+C | FR-2.6 |
| Q8 | D | FR-2.5 |
| Q9 | C | FR-3.1, FR-3.2 |
| Q10 | B+C | FR-4 |
| Q11 | E | FR-6 |
| Q12 | B | FR-5.4 |
| Q13 | B+C+AI 审核 | FR-5.2, FR-5.3 |
| Q14 | C | FR-7 |
| Q15 | C | FR-8（全家桶） |
| Q16 | A+B | FR-1.2, FR-1.3, FR-8.4 |
| Q17 | A | Tech Stack (Frontend) |
| Q18 | G | FR-9 (全部页面 + admin) |
| Q19 | C | Tech Stack (BFF/Fargate) |
| Q20 | B | FR-10.1 |
| Q21 | B | FR-10.2 |
| Q22 | A | FR-10.5 |
| Q23 | C | NFR-1 |
| Q24 | C | NFR-6 |
| Q25 | C | Scope = Full V1 |
| Clarify 1 | A | Tech Stack (Vite SPA + Node BFF) |
| Clarify 2 | A | FR-10.1, FR-8.6 分工 |
| Clarify 3 | C | FR-5.3（双层审核） |

---
