# 需求验证问题（Requirements Verification Questions） - 小说仿写生成应用

请逐一回答下列问题。在每个问题的 `[回答]：` 后面填写你选择的字母（A/B/C/...）。如果没有合适选项，请选择最后一项 "Other" 并在 `[回答]：` 后面描述你的具体需求。

完成所有答案后，请告诉我"done"或"已完成"，我将继续下一步。

---

## 一、合规与数据来源（CRITICAL）

### Question 1
自动下载网络小说涉及版权风险（例如起点中文网等平台的商业作品）。本项目对小说数据来源的合规策略是什么？

A) **仅支持公版书（public domain）**：只下载 Project Gutenberg、中国哲学书电子化计划、古腾堡中文等公版来源的小说（如《红楼梦》《西游记》《水浒传》等），完全合规
B) **仅支持用户本地上传**：不做任何网络爬虫，只允许用户上传自有正版副本或自己创作的文稿作为"风格样本"
C) **提供爬虫能力，但由用户自行承担版权责任**：系统提供下载能力（配置为可接入多个站点的适配器），产品条款中明确告知用户须确保合法授权
D) **先公版书 + 用户上传（作为 MVP），后续再评估商业 API 接入**：MVP 阶段只做 A+B，后期可通过授权 API（如番茄、晋江的官方内容授权）扩展
E) Other (please describe after [回答]： tag below)

[回答]： C。 目前为纯技术研究，版权问题你不用考虑，我会人工处理。

### Question 2
用户上传的原始小说内容（可能很长，几十万至几百万字），你倾向如何存储？

A) 整本原文存 S3，摘要/章节索引/结构化信息存 DynamoDB
B) 全部存 DynamoDB（按章节分片），便于快速查询
C) S3 存原文，AgentCore Memory 存理解后的结构化记忆，DynamoDB 存元数据
D) Other (please describe after [回答]： tag below)

[回答]： C。 

### Question 3
对于用户上传的小说，是否需要支持常见格式？

A) 仅支持 TXT
B) 支持 TXT + EPUB
C) 支持 TXT + EPUB + PDF + DOCX
D) 支持所有格式，通过预处理统一转为 Markdown
E) Other (please describe after [回答]： tag below)

[回答]： D

---

## 二、小说分析与理解

### Question 4
"小说类型鉴别"功能的实现方式：

A) **预定义固定类型体系**：系统内置一组类型（修仙、武侠、穿越、言情、悬疑、科幻、历史、都市...），LLM 只能从中选择
B) **LLM 自由判定 + 人工校准**：LLM 自由生成类型标签，admin 可以审核和合并相似标签，逐步沉淀一套标准类型体系
C) **多标签分类**：一本小说可有多个类型标签（例如"修仙 + 穿越 + 系统流"），便于混合风格生成
D) B + C 组合：自由生成多标签 + admin 校准
E) Other (please describe after [回答]： tag below)

[回答]： D

### Question 5
"修为等级体系"、"宗派势力"等**小说类型专属分析维度**，如何管理？

A) 每种小说类型对应一份**分析模板（Analysis Schema）**，由 admin 在后台维护（例如修仙模板有"境界列表、宗门、功法"，言情模板有"CP 线、情感节点"），系统按类型选用模板
B) 全部由 LLM 动态推断，不预定义 schema
C) A + B：预定义模板提供骨架，LLM 补充填充；新类型由 admin 逐步新增模板
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question 6
对于长篇小说（百万字级），"理解"过程的做法：

A) 一次性让 LLM 读完整本（不可行，超出 context window）
B) **章节级分批理解 + 增量摘要**：逐章处理，维护一份持续更新的"全书记忆" (running memory)
C) **两阶段**：先粗读（抽样章节）把握整体框架，再细读（重点章节）补充细节
D) B + C 组合
E) Other (please describe after [回答]： tag below)

[回答]： D

### Question 7
"地图路线理解"要记录的粒度：

A) 仅记录主角到过的地点清单（线性列表）
B) 记录地点 + 地点间的关系（邻近/远近/所属国家）+ 每个地点的首次/最后出场章节
C) 构建**知识图谱**（节点 = 地点/人物/事件，边 = 关系），用 AgentCore Memory + 图数据库（Neptune）存储
D) B 即可，不引入图数据库
E) Other (please describe after [回答]： tag below)

[回答]： ABC的功能我都需要，另外，不光是主角到过的地方，其他角色到过的地方也需要理解并记住。

### Question 8
"人物角色"信息的维护方式：

A) 每个人物一个 Profile 卡片：姓名、性格、外貌、关键行为、与其他人物关系
B) A + 人物在各章节的"状态快照"（例如第 10 章时该人物的修为、心情、所处地点）
C) A + 人物关系图（谁是谁的师父/敌人/恋人/亲属）
D) A + B + C 全量
E) Other (please describe after [回答]： tag below)

[回答]： D

---

## 三、生成策略与风格控制

### Question 9
"仿写一本全新小说"的含义是：

A) **同世界观新剧情**：沿用原作世界观、主要角色、已有地图，生成新的故事线（官方"同人"风格）
B) **同风格新世界**：只学习原作的**写作风格和类型特征**，但人物、地名、情节都是全新的（避免版权风险）
C) 由用户在前端选择 A 或 B
D) Other (please describe after [回答]： tag below)

[回答]： C。 需要注意的是,A功能为续写功能，即对原小说章节的续写。B功能为全新仿写，为一本全新的小说。续写功能与全新仿写功能我都需要，可让用户自由选择。

### Question 10
风格控制的粒度：

A) 仅提供"整体基调"选项（风趣/严肃/宏大/温情）
B) 多维度风格向量：基调 + 节奏（快/慢） + 描写密度（细腻/简洁） + 对话占比 + 情感强度 + 世界观宏大度
C) 除 B 外，还允许用户上传多本小说作为"风格参考"，混合权重
D) Other (please describe after [回答]： tag below)

[回答]： BC

### Question 11
新小说生成的章节间**一致性保障**（避免前后矛盾：人物死了又复活、地点顺序错乱等）：

A) **每章生成后，将关键事实写入 AgentCore Memory**，下一章生成前从 Memory 检索相关约束作为 prompt 的一部分
B) 每章生成后，LLM 自检（self-critique），发现矛盾则重写
C) A + B 组合：Memory 约束 + 自检
D) 每 N 章做一次全局一致性校验并生成"修订建议"供用户审查
E) C + D 组合
F) Other (please describe after [回答]： tag below)

[回答]： E

### Question 12
生成的章节数量与字数：

A) 用户自定义：总章节数（如 50）+ 每章字数（如 3000）
B) A + 系统根据原作统计给出推荐值（原作平均每章 3200 字、共 800 章，推荐生成 50 章 × 3200 字）
C) Other (please describe after [回答]： tag below)

[回答]： B

### Question 13
生成过程中的用户介入：

A) **全自动**：用户点击生成，等待所有章节一次性产出
B) **章节级人工审核**：每生成一章，用户可以审阅、编辑、打回重写
C) **大纲先审核，再逐章生成**：先生成全书大纲，用户批准大纲后开始逐章生成
D) B + C 组合：先大纲审核，再章节审核
E) Other (please describe after [回答]： tag below)

[回答]： BC，同时结合AI审核总结的建议，然后再让人工review与确认。

---

## 四、LLM 与 AgentCore 配置

### Question 14
Claude 模型选择策略：

A) 全局使用同一模型（默认 Sonnet 4.6，admin 可切换到 Opus 4.7）
B) **分级使用**：分析理解阶段用 Sonnet（性价比）、创作生成阶段用 Opus（质量优先），用户可覆盖
C) 按任务自由配置：admin 在后台为每个任务阶段（类型鉴别/人物提取/章节生成/一致性检查）单独配置模型
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question 15
必须使用 3+ 个 AgentCore 服务。以下哪种组合优先？

A) **Runtime + Memory + Gateway**：Runtime 跑 agent 流程、Memory 存小说结构化记忆、Gateway 统一对接外部工具（下载器/翻译/搜索）
B) **Runtime + Memory + Browser + Observability**：增加 Browser 自动访问公版书站点下载原文，增加 Observability 跟踪 agent 链路
C) **Runtime + Memory + Gateway + Browser + Observability + Identity**：全家桶，Identity 处理多用户 OAuth
D) Other (please describe after [回答]： tag below)

[回答]： C

### Question 16
AgentCore Browser 的用途（仅在选 B/C 时相关）：

A) 自动访问公版书库（gutenberg.org 等），按书名搜索并下载
B) 配合用户手动粘贴的 URL，抓取单页正文
C) 用于生成后自动发布到用户指定平台（博客/自媒体）
D) 不使用 Browser
E) Other (please describe after [回答]： tag below)

[回答]： AB都需要支持。

---

## 五、前端 Web 界面

### Question 17
前端技术栈偏好：

A) React + TypeScript + Vite + Tailwind + shadcn/ui（现代主流，组件生态丰富）
B) Next.js + TypeScript + Tailwind（支持 SSR，部署到 Amplify/Vercel）
C) Vue 3 + TypeScript + Element Plus
D) 由你（AI）决定最合适的选项
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question 18
前端需要的核心页面（多选，请选出你最需要的选项组合，或选 F 全部）：

A) 登录/注册 + 仪表盘（概览）
B) 小说上传/下载页（输入书名 or 上传文件）
C) 分析结果查看页（类型、人物、地图、风格分析报告）
D) 生成配置页（风格、章节数、字数、是否先审大纲）
E) 生成结果查看/编辑/导出页（在线阅读、逐章编辑、导出 TXT/EPUB）
F) 以上全部
G) 以上全部 + admin 后台（用户管理、模型配置、分析模板管理、全局监控）
H) Other (please describe after [回答]： tag below)

[回答]： G

### Question 19
前端的部署方式：

A) S3 + CloudFront（静态托管）
B) AWS Amplify Hosting
C) ECS Fargate（如果有 SSR 需求）
D) 由你决定
E) Other (please describe after [回答]： tag below)

[回答]： C. 前端使用node.js 

---

## 六、多用户与权限

### Question 20
用户认证方式：

A) Amazon Cognito User Pool（邮箱 + 密码 + 可选 MFA）
B) Cognito + 社交登录（Google/GitHub）
C) 自建 JWT（不推荐，但如果有特殊需求）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question 21
"domain 内可见"的"domain"具体含义：

A) **个人级**：每个普通用户只能看到自己上传/生成的小说
B) **团队级**：用户属于某个 team/organization，team 成员间共享；admin 跨 team 可见
C) A 为默认，可选升级为 B（未来扩展）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question 22
免费额度与用量限制（Bedrock 调用成本可观）：

A) 无限制（MVP 阶段，内部使用）
B) 每用户每月 token 配额（DynamoDB 记账）+ 超限熔断
C) 分级付费计划（free/pro/enterprise）
D) Other (please describe after [回答]： tag below)

[回答]： A

---

## 七、非功能性需求

### Question 23
性能目标：

A) 分析一本 100 万字小说应在 **< 30 分钟**内完成；生成一章 3000 字应在 **< 2 分钟**内完成
B) 分析 < 1 小时，单章生成 < 5 分钟（宽松）
C) 分析 < 15 分钟，单章生成 < 60 秒（严格，需并行优化）
D) 由你给出合理目标
E) Other (please describe after [回答]： tag below)

[回答]： C。 请你进行并行优化, 例如使用多线程，多agent协同的方式。

### Question 24
部署环境与区域：

A) AWS 单区域（us-east-1 或 us-west-2）
B) AWS 单区域（中国用户推荐 AWS 中国 cn-north-1 或 cn-northwest-1，但 Bedrock 目前不支持中国区，需跨境）
C) 使用海外区 + CloudFront 加速
D) 由你根据中国用户需求给出推荐
E) Other (please describe after [回答]： tag below)

[回答]： C

---

## 八、范围与优先级

### Question 25
MVP（最小可用版本）范围定义：

A) **最小 MVP**：仅支持"上传 TXT → 分析一种类型（例如修仙）→ 生成 3 章 demo"的端到端闭环，证明可行性
B) **中等 MVP**：支持 2-3 种类型 + 前端完整页面 + 多用户基础权限 + 至少 3 个 AgentCore 服务
C) **完整 V1**：所有问题覆盖的功能全量实现，包括 admin 后台、模板管理、知识图谱等
D) 分两阶段交付：先 A 后 B
E) Other (please describe after [回答]： tag below)

[回答]： C

---

## （可选）补充说明

如果你对上述某个问题有更多细节想补充，或者有问卷未覆盖的重要约束（预算上限、时间节点、团队规模、已有资源等），请在此处写下：

[Additional Notes]: 
整个项目，需要完整的文档，包括产品设计文档，技术设计文档，技术细节说明文档，部署文档，使用文档，等等。