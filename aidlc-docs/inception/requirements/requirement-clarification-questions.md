# 需求澄清问题（Requirements Clarification Questions） - 小说仿写生成应用

在你之前的回答中发现了 2 个技术冲突 + 1 个关键歧义需要澄清。请回答下列问题后告知我"done"或"已完成"。

---

## 冲突 1：前端技术栈与部署架构

你在 **Q17 选了 A（React + Vite + Tailwind + shadcn/ui）** —— Vite 构建输出纯静态文件（HTML/JS/CSS），传统上用 S3+CloudFront 静态托管即可，不需要 Node.js 运行时。

但你在 **Q19 选了 C（ECS Fargate）** 并补充"**前端使用 node.js**" —— 这通常意味着需要一个 Node.js 进程持续运行。

### Clarification Question 1
你希望的前端架构形态是下面哪一种？

A) **Vite SPA + Node.js BFF**：Vite 构建静态产物 + Node.js/Express 作为 Backend-for-Frontend 层（处理 SSR 的 index.html 注入、API 代理、Session Cookie 转发、静态资源服务），整体打包为 Docker 容器部署到 ECS Fargate
B) **改用 Next.js（纯 SSR/SSG）**：放弃 Vite，改为 Next.js（App Router）+ Tailwind + shadcn/ui，在 Node.js 运行时上 SSR，部署到 ECS Fargate（同时保留 Q17 希望的 shadcn/ui 组件风格）
C) **Vite SPA 静态托管 + 独立 Node.js API Gateway 层**：前端走 S3+CloudFront（静态），另有独立的 Node.js 服务（例如认证代理、聚合 API）跑在 ECS Fargate，两者分开部署
D) Other (please describe after [回答]： tag below)

[回答]： A

---

## 冲突 2：用户认证方案的分工

你在 **Q20 选了 B（Cognito + 社交登录）**，在 **Q15 选了 C（包含 AgentCore Identity）**。

AgentCore Identity 的主要用途是**让 Agent 代表用户去访问下游系统时安全地获取 token**（workload identity），它本身不替代用户面的登录。Cognito 负责用户登录/会话管理。两者可并存，但需要确认分工。

### Clarification Question 2
你希望的分工方式是？

A) **Cognito 管用户登录，AgentCore Identity 管 agent-to-tool 的 workload identity**（推荐）：用户通过 Cognito + Google/GitHub 登录获取 JWT；Agent 在调用 AgentCore Gateway 上的外部工具（如爬虫、翻译 API）时，由 AgentCore Identity 代理获取相应的下游 token
B) **全部使用 AgentCore Identity**（Cognito 不用）：如果 AgentCore Identity 足以覆盖用户面登录
C) **Cognito + 社交登录已足够，取消 AgentCore Identity**：AgentCore 只用 Runtime + Memory + Gateway + Browser + Observability（5 个服务，仍满足 3+）
D) Other (please describe after [回答]： tag below)

[回答]： A

---

## 歧义 3：Q13 的"AI 审核建议 + 人工 review"含义

你在 **Q13 回答"BC，同时结合 AI 审核总结的建议，然后再让人工 review 与确认"**。我想确认审核 agent 的定位。

### Clarification Question 3
"AI 审核"具体如何实现？

A) **独立的 Critic Agent**：用一个专门的审核 agent（可配置用 Opus 4.7）对生成章节做质量/一致性评审，输出"修改建议清单"给用户，用户决定是否采纳
B) **在章节生成流程中内嵌 self-critique**：同一个 agent 先生成，再自我审视并给出改进点，与 A 的区别是不走独立 agent
C) **A + B 组合**：生成时自检 + 独立 Critic Agent 做章节级和全书级的两层审核
D) Other (please describe after [回答]： tag below)

[回答]： C

---

## （可选）其他你想补充的约束

如果你在思考答案过程中想到还有什么新的约束（预算、交付时间、是否允许使用 Neptune 图数据库、是否需要 OpenSearch 向量检索、是否需要对外提供 API 等），请在这里补充：

[Additional Notes]: 
