# 用户故事（User Stories）— 小说仿写生成应用

**版本**：1.1
**日期**：2026-04-27
**Organization**: 按用户旅程分阶段（S1=A）
**验收标准**: Given-When-Then + Checklist 混合（S2=C）
**Granularity**: 中粒度（S3=A，目标 30 个 Story）
**NFR Stories**: 关键 NFR 单独（S4=C）
**Personas**: 4 角色 — RegularUser, TeamMember, Admin, ContentModerator
**Traceability**: 完整 FR/NFR 引用（S7=A）
**优先级**：P0=V1 Must / P1=V1 Should / P2=V1 Could（S8=B）

> **Changelog v1.1**：根据用户反馈移除 Guest persona。注册/登录相关 Story 的 Persona 统一归属 RegularUser（涵盖其首次登录到日常使用的完整旅程）。旅程阶段 0 改名为"注册与入场"。

---

## 旅程阶段概览

| # | 旅程阶段 | Story 数 |
|---|---|---|
| 0 | 注册与入场 | US-00-01 ~ US-00-02 (2) |
| 1 | 身份与团队协作 | US-01-01 ~ US-01-04 (4) |
| 2 | 小说采集（上传/下载） | US-02-01 ~ US-02-04 (4) |
| 3 | 小说理解与分析 | US-03-01 ~ US-03-05 (5) |
| 4 | 生成配置 | US-04-01 ~ US-04-03 (3) |
| 5 | 大纲审核 | US-05-01 ~ US-05-02 (2) |
| 6 | 章节生成、Critic 与人工审阅 | US-06-01 ~ US-06-05 (5) |
| 7 | 导出与分享 | US-07-01 ~ US-07-02 (2) |
| 8 | 管理后台（Admin） | US-08-01 ~ US-08-04 (4) |
| 9 | 内容审核（ContentModerator） | US-09-01 ~ US-09-02 (2) |
| N | 非功能性关键 Story | US-NFR-01 ~ US-NFR-05 (5) |

**合计**：33 个 Story（28 业务 + 5 NFR）

---

## 旅程阶段 0：注册与入场

### US-00-01｜浏览产品首页（登录前）
- **As a** RegularUser（尚未登录的潜在用户）
- **I want** 在登录页之前快速了解产品核心能力与合规声明
- **So that** 在注册前对平台价值与风险有清晰认知
- **Priority**: P1
- **Traceability**: FR-9.1
- **Persona**: RegularUser
- **Unit**: U6
- **验收标准 (Checklist)**:
  - [ ] 首页展示产品核心功能（采集、理解、仿写、续写、审核、导出）
  - [ ] 首页明显位置展示"用户自行承担版权责任"合规声明
  - [ ] 首页显示示例分析报告的概览截图（人物卡片、风格雷达图、地图简图）
  - [ ] 首页展示示例生成章节的摘要/截图（不暴露完整章节）
  - [ ] 提供"注册"与"登录"入口

### US-00-02｜注册与登录
- **As a** RegularUser
- **I want** 通过 Cognito 或 Google/GitHub 完成注册与登录
- **So that** 获取个人/团队工作区
- **Priority**: P0
- **Traceability**: FR-10.1
- **Persona**: RegularUser
- **Unit**: U1, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 我尚未登录
  - **When** 我点击"用 Google 登录"并完成授权
  - **Then** 系统应在 Cognito User Pool 创建新账户（如首次登录），并默认加入一个独立 team（teamId = userId）
  - **And** 跳转到个人仪表盘
  - **And** 失败时返回明确错误信息（如 IdP 拒绝、网络异常）

---

## 旅程阶段 1：身份与团队协作

### US-01-01｜查看个人仪表盘
- **As a** RegularUser
- **I want** 看到"我的小说"、"进行中任务"、"最近生成结果"
- **So that** 快速恢复工作上下文
- **Priority**: P0
- **Traceability**: FR-9.2
- **Persona**: RegularUser, TeamMember
- **Unit**: U6
- **验收标准 (Checklist)**:
  - [ ] 显示当前用户所属 team 名称
  - [ ] 展示"我的小说"列表（最近 10 条）
  - [ ] 展示"进行中任务"及进度百分比
  - [ ] 展示"最近生成结果"链接
  - [ ] 所有列表支持点击跳转详情

### US-01-02｜加入/切换团队
- **As a** RegularUser
- **I want** 加入一个现有 team 或切换到其他我所属的 team
- **So that** 与同事共享作品
- **Priority**: P1
- **Traceability**: FR-10.2
- **Persona**: RegularUser, TeamMember
- **Unit**: U1, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 我已登录
  - **When** 我输入 team 邀请码（或 admin 邀请）
  - **Then** 系统把我的 userId 加入该 teamId 成员列表
  - **And** 切换 team 后，仪表盘与数据全部切换到新 team 范围
  - **And** 仅显示当前 team 的小说和任务（跨 team 数据不可见）

### US-01-03｜Team 内共享可见性
- **As a** TeamMember
- **I want** 看到 team 内其他成员上传的小说和创建的任务
- **So that** 协作开展仿写工作
- **Priority**: P0
- **Traceability**: FR-10.2, NFR-4
- **Persona**: TeamMember
- **Unit**: U1, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 我与同事 A 属于同一 team T
  - **When** 同事 A 上传小说 N 或创建生成任务 J
  - **Then** 我在 team T 的仪表盘看到 N 与 J
  - **And** 我能打开 N 和 J 的查看页
  - **And** 我在另一个 team T' 时，看不到 N 和 J

### US-01-04｜跨租户隔离（反例验证）
- **As a** RegularUser 属于 team A
- **I want** 我的数据在 team B 用户视角下完全不可见
- **So that** 保障隐私与商业机密
- **Priority**: P0
- **Traceability**: NFR-4, FR-10.2
- **Persona**: RegularUser
- **Unit**: U1
- **验收标准 (Given-When-Then)**:
  - **Given** team A 的用户 U_A 创建了小说 N_A
  - **When** team B 的用户 U_B 以合法 JWT 调用任意 API 请求 N_A（包括猜测 ID）
  - **Then** 后端返回 403 Forbidden
  - **And** S3 对象与 DynamoDB 记录永远不会被 team B 读到
  - **And** 审计日志记录该访问尝试

---

## 旅程阶段 2：小说采集

### US-02-01｜上传本地文件
- **As a** RegularUser
- **I want** 上传 TXT / EPUB / PDF / DOCX / Markdown 文件
- **So that** 作为参考原作进行分析
- **Priority**: P0
- **Traceability**: FR-1.1, FR-1.5
- **Persona**: RegularUser
- **Unit**: U2, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 我在"采集"页
  - **When** 我上传一本 50 MB 以内的 EPUB 文件
  - **Then** 前端显示上传进度条
  - **And** 上传完成后，后端预处理统一转为 Markdown 并存入 S3（path: `teams/{teamId}/novels/{novelId}/raw.md`）
  - **And** 章节索引与元数据写入 DynamoDB
  - **And** 我在 30 秒内收到"处理完成"提示
  - **边界**：> 50 MB 报错提示；损坏文件报错并给出解析失败原因

### US-02-02｜按书名搜索公版书
- **As a** RegularUser
- **I want** 输入书名（例如《红楼梦》）自动从公版书库下载
- **So that** 无需自己准备文件
- **Priority**: P1
- **Traceability**: FR-1.2, FR-8.4
- **Persona**: RegularUser
- **Unit**: U2
- **验收标准 (Given-When-Then)**:
  - **Given** 我在"采集"页输入书名"红楼梦"
  - **When** 我点击"搜索公版书库"
  - **Then** AgentCore Browser 访问 Project Gutenberg / 中国哲学书电子化计划等公版源
  - **And** 列出候选结果（作者、版本、字数）
  - **And** 我选择一个版本后，系统下载并转为 Markdown 存入 S3
  - **失败路径**：源站不可达时提供友好错误；无匹配结果时提示"未找到公版"并建议上传文件

### US-02-03｜URL 抓取
- **As a** RegularUser
- **I want** 粘贴 URL 让系统抓取网页正文
- **So that** 快速采集网络上的公开文章或开源小说章节
- **Priority**: P2
- **Traceability**: FR-1.3, FR-8.4
- **Persona**: RegularUser
- **Unit**: U2
- **验收标准 (Checklist)**:
  - [ ] 支持粘贴单个 URL
  - [ ] AgentCore Browser 抓取主正文（去除导航、广告）
  - [ ] 如果页面是多章节目录，识别并逐页抓取
  - [ ] 产物归档到 S3 并生成 DynamoDB 元数据
  - [ ] 失败时返回错误原因（403/404/robots.txt 禁止等）
  - [ ] 显示合规提示：由用户确认内容合法可采集

### US-02-04｜查看我的小说库
- **As a** RegularUser
- **I want** 列表查看 team 内所有已采集的小说
- **So that** 选择一本开始分析或生成
- **Priority**: P0
- **Traceability**: FR-9.3, FR-10.2
- **Persona**: RegularUser, TeamMember
- **Unit**: U6
- **验收标准 (Checklist)**:
  - [ ] 显示列表：书名、作者（如有）、章节数、字数、上传时间、上传人、分析状态
  - [ ] 支持按书名搜索与按时间排序
  - [ ] 点击进入小说详情页
  - [ ] 只显示当前 team 的小说

---

## 旅程阶段 3：小说理解与分析

### US-03-01｜触发小说分析
- **As a** RegularUser
- **I want** 点击"开始分析"按钮让系统执行两阶段理解
- **So that** 得到类型、人物、地图、风格等完整报告
- **Priority**: P0
- **Traceability**: FR-2.1, FR-2.2, FR-8.1, FR-8.2
- **Persona**: RegularUser
- **Unit**: U3
- **验收标准 (Given-When-Then)**:
  - **Given** 我已采集小说 N（> 0 章节）
  - **When** 我在详情页点击"开始分析"
  - **Then** 后端启动 Step Functions 工作流：粗读 → 细读（逐章）→ Memory 写入
  - **And** 前端通过 SSE 显示进度（当前阶段、完成百分比、预计剩余时间）
  - **And** 任务元数据（jobId、status、progress）持久化到 DynamoDB，可断线重连
  - **And** 分析完成后状态变为 ANALYZED

### US-03-02｜查看类型鉴别结果
- **As a** RegularUser
- **I want** 查看该小说被识别的多标签类型
- **So that** 确认系统理解方向是否正确
- **Priority**: P0
- **Traceability**: FR-2.3
- **Persona**: RegularUser
- **Unit**: U3, U6
- **验收标准 (Checklist)**:
  - [ ] 显示所有识别出的标签（如"修仙、系统流、穿越"）+ 置信度
  - [ ] 用户可手动增删标签（覆盖 AI 判断）
  - [ ] 标签变动触发分析模板重选

### US-03-03｜查看人物报告
- **As a** RegularUser
- **I want** 查看所有主要人物的 Profile + 状态快照 + 关系图
- **So that** 理解作品人物体系
- **Priority**: P0
- **Traceability**: FR-2.5
- **Persona**: RegularUser
- **Unit**: U3, U6
- **验收标准 (Checklist)**:
  - [ ] 人物列表：按出场频次排序
  - [ ] 每个人物的卡片：姓名、性格、外貌、关键行为、所属宗门（或其他类型专属字段）
  - [ ] 章节状态快照时间线（每 N 章的修为/心情/位置）
  - [ ] 人物关系图可视化（支持缩放、点击节点查看详情）

### US-03-04｜查看地图与路线
- **As a** RegularUser
- **I want** 查看所有地点、角色足迹、地点关系知识图谱
- **So that** 把握世界观空间结构
- **Priority**: P1
- **Traceability**: FR-2.6
- **Persona**: RegularUser
- **Unit**: U3, U6
- **验收标准 (Checklist)**:
  - [ ] 地点列表：首次出场章节、最后出场章节、出场次数
  - [ ] 支持按角色筛选其足迹
  - [ ] 知识图谱可视化（节点=地点/角色/事件）
  - [ ] 地点关系（邻近/所属国家/所属势力）

### US-03-05｜查看风格雷达图
- **As a** RegularUser
- **I want** 查看原作的多维度风格向量
- **So that** 作为生成配置的参考初值
- **Priority**: P1
- **Traceability**: FR-2.7, FR-4.3
- **Persona**: RegularUser
- **Unit**: U3, U6
- **验收标准 (Checklist)**:
  - [ ] 雷达图显示 6 维度：基调、节奏、描写密度、对话占比、情感强度、世界观宏大度
  - [ ] 每维度显示具体数值（0-100）与解释文案
  - [ ] 提供"用此风格作为生成初值"一键按钮

---

## 旅程阶段 4：生成配置

### US-04-01｜选择生成模式
- **As a** RegularUser
- **I want** 在"全新仿写"和"续写"之间选择
- **So that** 按需求产出内容
- **Priority**: P0
- **Traceability**: FR-3.1, FR-3.2
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 已分析完成的小说 N
  - **When** 我打开"生成配置"页
  - **Then** 页面提供两个模式：
    - **全新仿写**：复用风格与类型，但人物/地名/情节全新
    - **续写**：沿用原作世界观与现有角色、地图
  - **And** 选择不同模式时，UI 显示对应的配置项（续写模式可选起始章节）

### US-04-02｜调节风格向量 + 混合参考
- **As a** RegularUser
- **I want** 调节 6 维风格滑块，并上传多本参考小说设置权重
- **So that** 精确控制生成风格
- **Priority**: P1
- **Traceability**: FR-4.1, FR-4.2
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Checklist)**:
  - [ ] 6 个滑块（基调/节奏/描写密度/对话占比/情感强度/世界观宏大度）
  - [ ] 支持添加多本已分析的小说作为参考，权重总和需 = 100%
  - [ ] 预览"示例段落"（基于当前配置生成 200 字预览）

### US-04-03｜配置章节数与字数
- **As a** RegularUser
- **I want** 自定义章节数与每章字数，并看到系统推荐
- **So that** 控制生成规模
- **Priority**: P0
- **Traceability**: FR-5.4
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Checklist)**:
  - [ ] 显示系统基于原作统计的推荐值（例如"原作平均 3200 字/章 × 800 章 → 推荐 50 章 × 3200 字"）
  - [ ] 允许用户覆盖
  - [ ] 显示预估 token 与预估耗时

---

## 旅程阶段 5：大纲审核

### US-05-01｜生成与查看大纲
- **As a** RegularUser
- **I want** 先生成全书大纲（人物表、主线、章节主题）再决定是否开始章节生成
- **So that** 避免在错误方向上浪费时间
- **Priority**: P0
- **Traceability**: FR-5.1
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 已完成生成配置
  - **When** 我点击"生成大纲"
  - **Then** 大纲 Agent（默认 Opus 4.7）产出：人物表、世界观概述、主线、每章主题
  - **And** 前端展示大纲页，支持按章节浏览
  - **And** 耗时 ≤ 5 分钟（NFR-1）

### US-05-02｜编辑与批准大纲
- **As a** RegularUser
- **I want** 修改大纲内容（增删人物、调整章节主题）再批准
- **So that** 确保生成方向符合预期
- **Priority**: P0
- **Traceability**: FR-5.1, FR-5.2
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Checklist)**:
  - [ ] 大纲内容可编辑（富文本）
  - [ ] "重新生成大纲"按钮（保留上一版历史）
  - [ ] "批准并开始章节生成"按钮
  - [ ] 批准后大纲锁定，不可继续修改（除非走"返回大纲"）

---

## 旅程阶段 6：章节生成、Critic 与人工审阅

### US-06-01｜流式生成章节
- **As a** RegularUser
- **I want** 实时看到章节文本逐段生成
- **So that** 提早发现问题并节省等待时间
- **Priority**: P0
- **Traceability**: FR-5.2, FR-5.5
- **Persona**: RegularUser
- **Unit**: U4, U6
- **验收标准 (Given-When-Then)**:
  - **Given** 我已批准大纲
  - **When** 系统开始生成第 N 章
  - **Then** 前端通过 SSE 实时接收文本片段并逐段显示
  - **And** 单章（3000 字）生成耗时 ≤ 60 秒（NFR-1）
  - **And** 连接断开时可恢复（通过 lastEventId）

### US-06-02｜Memory 一致性约束
- **As a** RegularUser
- **I want** 生成的新章节不与已有事实矛盾（人物状态、地点、时间线）
- **So that** 作品保持内部一致
- **Priority**: P0
- **Traceability**: FR-6.1, FR-6.4
- **Persona**: RegularUser
- **Unit**: U4, U5
- **验收标准 (Given-When-Then)**:
  - **Given** 先前章节已写明人物 A 在第 5 章死亡
  - **When** 生成第 12 章
  - **Then** Generation Agent 在 prompt 前缀中必定包含从 AgentCore Memory 检索到的"A 已死"事实
  - **And** 生成内容不应出现 A 作为在世角色的情节
  - **And** 新产生的人物/地点/事件自动写回 Memory（幂等）

### US-06-03｜Self-Critique + 独立 Critic Agent 双层审核
- **As a** RegularUser
- **I want** 每章生成后得到双层 AI 审核（自检 + 独立 Critic）的修改建议
- **So that** 在人工 review 前获得质量提示
- **Priority**: P0
- **Traceability**: FR-5.3
- **Persona**: RegularUser
- **Unit**: U4, U5
- **验收标准 (Checklist)**:
  - [ ] Layer-1（Self-Critique）：生成 Agent 完成后自检，输出初版 + 改进点
  - [ ] Layer-2（Critic Agent，默认 Opus 4.7）：独立评审章节质量（风格一致、情节逻辑、人物塑造）
  - [ ] 前端显示"Critic 建议清单"面板，按严重度分类
  - [ ] 用户可点"采纳"让 Agent 重写，也可点"忽略"

### US-06-04｜章节审阅、编辑、打回重写
- **As a** RegularUser
- **I want** 查看章节原文，逐段编辑，或一键打回重写
- **So that** 获得最终满意的内容
- **Priority**: P0
- **Traceability**: FR-5.2
- **Persona**: RegularUser, TeamMember
- **Unit**: U4, U6
- **验收标准 (Checklist)**:
  - [ ] 章节显示为可编辑富文本
  - [ ] 保存修改立即持久化到 S3（版本化）
  - [ ] "重写本章"按钮，可附带用户指令（如"增加战斗描写"）
  - [ ] 历史版本可查看与回滚
  - [ ] 多成员同时编辑时显示冲突提示（基于乐观锁）

### US-06-05｜周期性全局一致性校验
- **As a** RegularUser
- **I want** 每生成 N 章（如每 10 章）系统自动做全书一致性校验
- **So that** 早发现全局矛盾
- **Priority**: P1
- **Traceability**: FR-6.3
- **Persona**: RegularUser
- **Unit**: U5
- **验收标准 (Given-When-Then)**:
  - **Given** 已完成第 10、20、30… 章
  - **When** 到达校验间隔
  - **Then** 一致性 Agent 扫描所有章节 + Memory，产出"矛盾清单"（如"人物 B 在第 3 章发色为黑，在第 15 章变红，无过渡说明"）
  - **And** 结果保存到 DynamoDB 并在前端显示"修订建议"面板
  - **And** 用户可选"忽略"或"触发重写对应章节"

---

## 旅程阶段 7：导出与分享

### US-07-01｜导出多格式
- **As a** RegularUser
- **I want** 将生成的小说导出为 TXT / EPUB / Markdown
- **So that** 便于离线阅读或分享
- **Priority**: P0
- **Traceability**: FR-9.6
- **Persona**: RegularUser
- **Unit**: U6
- **验收标准 (Checklist)**:
  - [ ] 支持 TXT（UTF-8）
  - [ ] 支持 EPUB（封面、目录、元数据）
  - [ ] 支持 Markdown（YAML front matter + 章节）
  - [ ] 下载链接使用 S3 预签名 URL，30 分钟过期

### US-07-02｜在线阅读
- **As a** RegularUser
- **I want** 在线连续阅读生成结果
- **So that** 不用导出即可浏览
- **Priority**: P1
- **Traceability**: FR-9.6
- **Persona**: RegularUser, TeamMember
- **Unit**: U6
- **验收标准 (Checklist)**:
  - [ ] 阅读器支持章节导航与搜索
  - [ ] 字号/主题切换
  - [ ] 阅读进度记忆

---

## 旅程阶段 8：管理后台（Admin）

### US-08-01｜用户与团队管理
- **As a** Admin
- **I want** 管理所有用户与 team，包括新建、禁用、加入/移除成员
- **So that** 维护平台成员
- **Priority**: P0
- **Traceability**: FR-9.7, FR-10
- **Persona**: Admin
- **Unit**: U7
- **验收标准 (Checklist)**:
  - [ ] 用户列表，支持搜索/筛选（按 team、注册时间、状态）
  - [ ] team CRUD
  - [ ] 成员加入/移除操作
  - [ ] 操作写入审计日志

### US-08-02｜任务阶段-模型配置
- **As a** Admin
- **I want** 为每个任务阶段（类型鉴别、人物提取、大纲、章节生成、Critic…）独立配置 Claude 模型
- **So that** 按成本/质量需求调优
- **Priority**: P0
- **Traceability**: FR-7, FR-9.7
- **Persona**: Admin
- **Unit**: U7
- **验收标准 (Checklist)**:
  - [ ] 显示 9 个任务阶段的默认模型推荐（附录 A）
  - [ ] 每阶段可选：Claude Opus 4.7 / Sonnet 4.6 / Sonnet 4.7 / Haiku 4.5
  - [ ] 配置保存后立即在后续新任务生效
  - [ ] 正在进行的任务不受影响（冻结已用模型）

### US-08-03｜类型标签与分析模板管理
- **As a** Admin
- **I want** 审核 LLM 自由生成的新类型标签，合并相似标签，维护分析模板
- **So that** 沉淀平台类型体系
- **Priority**: P1
- **Traceability**: FR-2.3, FR-2.4, FR-9.7
- **Persona**: Admin
- **Unit**: U7
- **验收标准 (Checklist)**:
  - [ ] 待审核新标签队列（LLM 新产生的标签）
  - [ ] 合并标签（将"修真"合并到"修仙"）
  - [ ] 创建/编辑分析模板（例如修仙模板：境界列表、宗门、功法）
  - [ ] 模板生效后，新分析任务使用新模板

### US-08-04｜全局监控面板
- **As a** Admin
- **I want** 看到全局任务健康度、token 消耗、慢任务排行、错误率
- **So that** 运维与成本管理
- **Priority**: P0
- **Traceability**: NFR-5, FR-8.5, FR-9.7
- **Persona**: Admin
- **Unit**: U7
- **验收标准 (Checklist)**:
  - [ ] 聚合 AgentCore Observability 指标
  - [ ] 展示近 24h/7d/30d token 消耗（按模型、按 team、按任务阶段）
  - [ ] 慢任务 Top 10（按耗时）
  - [ ] 错误率与错误 Top 分类
  - [ ] 告警阈值配置

---

## 旅程阶段 9：内容审核（ContentModerator）

### US-09-01｜审核队列
- **As a** ContentModerator
- **I want** 看到待审核章节队列（AI 预标记敏感）
- **So that** 高效开展合规审查
- **Priority**: P1
- **Traceability**: NFR-7
- **Persona**: ContentModerator
- **Unit**: U5, U7
- **验收标准 (Checklist)**:
  - [ ] 队列按 AI 敏感度排序
  - [ ] 每条显示：章节标题、敏感类别、预标片段数
  - [ ] 点击进入段落级高亮视图

### US-09-02｜段落级审核与打回
- **As a** ContentModerator
- **I want** 对段落逐段判定"通过 / 修改 / 打回"
- **So that** 精确处理敏感内容
- **Priority**: P1
- **Traceability**: NFR-7
- **Persona**: ContentModerator
- **Unit**: U5, U7
- **验收标准 (Given-When-Then)**:
  - **Given** 我打开一个待审章节
  - **When** 我在某段落选择"打回"并写明原因
  - **Then** 章节状态变为 MODERATION_REJECTED
  - **And** 创建者收到通知
  - **And** 该段落被标注为需重写

---

## 非功能性关键 Story（NFR）

### US-NFR-01｜性能：分析 100 万字 < 15 分钟
- **As a** RegularUser
- **I want** 分析任务在规定时间内完成
- **So that** 避免等待过久
- **Priority**: P0
- **Traceability**: NFR-1
- **Unit**: U3
- **验收标准 (Given-When-Then)**:
  - **Given** 一本 100 万字的小说
  - **When** 我触发分析
  - **Then** 端到端完成时间 ≤ 15 分钟
  - **And** 实现手段：asyncio + 多 Agent 并行（人物/地图/风格 3 条流水线并发）+ 细读按批并行

### US-NFR-02｜性能：单章生成 < 60 秒
- **As a** RegularUser
- **I want** 单章生成（3000 字）在 60 秒内完成
- **So that** 保持创作节奏
- **Priority**: P0
- **Traceability**: NFR-1
- **Unit**: U4
- **验收标准 (Checklist)**:
  - [ ] 从"开始生成"到"最后一段流式完成" ≤ 60 秒
  - [ ] Self-Critique 不阻塞主流程（可异步）
  - [ ] 流式首字节 ≤ 3 秒

### US-NFR-03｜多租户强隔离
- **As a** System
- **I want** team A 的任何 API 请求都无法访问 team B 的数据
- **So that** 保障商业机密
- **Priority**: P0
- **Traceability**: NFR-4, FR-10
- **Unit**: U1
- **验收标准 (Given-When-Then)**:
  - **Given** 两个不同 team（A、B）
  - **When** team A 用户以合法 JWT 尝试通过猜测 ID 访问 team B 资源
  - **Then** API 返回 403
  - **And** S3 IAM 策略基于 teamId 前缀拒绝访问
  - **And** DynamoDB 查询条件强制 PK 前缀匹配 teamId
  - **And** 渗透测试脚本（自动化）每次部署运行并通过

### US-NFR-04｜成本护栏（预留扩展点）
- **As a** Admin
- **I want** 单任务 token 消耗达到阈值时触发告警或熔断
- **So that** 避免成本失控
- **Priority**: P1
- **Traceability**: NFR-5（延伸）, FR-10.5
- **Unit**: U7, U8.5
- **验收标准 (Checklist)**:
  - [ ] 每个任务（分析/生成）有 token 预算上限（admin 可配置）
  - [ ] 超过 80% 阈值时前端显示警告
  - [ ] 超过 100% 时任务暂停并等待 admin 决策
  - [ ] 所有 token 用量持久化到 DynamoDB（后续可启用配额）

### US-NFR-05｜全链路可观测
- **As a** Admin
- **I want** 每个任务有完整 trace（从前端请求 → BFF → API → Step Functions → Agent → Bedrock）
- **So that** 快速定位慢链路或错误
- **Priority**: P0
- **Traceability**: NFR-5, FR-8.5
- **Unit**: U1, U7
- **验收标准 (Checklist)**:
  - [ ] AgentCore Observability 采集所有 Agent 调用
  - [ ] X-Ray 集成前后端
  - [ ] 每个任务可查询完整时序图（瀑布图）
  - [ ] Token/延迟/错误指标进 CloudWatch
  - [ ] 告警：Bedrock 错误率 > 2% / 单任务超时 / Memory 写入失败

---

## Story → Unit 映射矩阵

| Story | U1 Platform | U2 Ingestion | U3 Understanding | U4 Generation | U5 Critic | U6 Frontend+BFF | U7 Admin |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| US-00-01 | | | | | | ✓ | |
| US-00-02 | ✓ | | | | | ✓ | |
| US-01-01 | | | | | | ✓ | |
| US-01-02 | ✓ | | | | | ✓ | |
| US-01-03 | ✓ | | | | | ✓ | |
| US-01-04 | ✓ | | | | | | |
| US-02-01 | | ✓ | | | | ✓ | |
| US-02-02 | | ✓ | | | | | |
| US-02-03 | | ✓ | | | | | |
| US-02-04 | | | | | | ✓ | |
| US-03-01 | | | ✓ | | | | |
| US-03-02 | | | ✓ | | | ✓ | |
| US-03-03 | | | ✓ | | | ✓ | |
| US-03-04 | | | ✓ | | | ✓ | |
| US-03-05 | | | ✓ | | | ✓ | |
| US-04-01 | | | | ✓ | | ✓ | |
| US-04-02 | | | | ✓ | | ✓ | |
| US-04-03 | | | | ✓ | | ✓ | |
| US-05-01 | | | | ✓ | | ✓ | |
| US-05-02 | | | | ✓ | | ✓ | |
| US-06-01 | | | | ✓ | | ✓ | |
| US-06-02 | | | | ✓ | ✓ | | |
| US-06-03 | | | | ✓ | ✓ | | |
| US-06-04 | | | | ✓ | | ✓ | |
| US-06-05 | | | | | ✓ | | |
| US-07-01 | | | | | | ✓ | |
| US-07-02 | | | | | | ✓ | |
| US-08-01 | | | | | | | ✓ |
| US-08-02 | | | | | | | ✓ |
| US-08-03 | | | | | | | ✓ |
| US-08-04 | | | | | | | ✓ |
| US-09-01 | | | | | ✓ | | ✓ |
| US-09-02 | | | | | ✓ | | ✓ |
| US-NFR-01 | | | ✓ | | | | |
| US-NFR-02 | | | | ✓ | | | |
| US-NFR-03 | ✓ | | | | | | |
| US-NFR-04 | | | | | | | ✓ |
| US-NFR-05 | ✓ | | | | | | ✓ |

---

## 优先级统计

| 优先级 | 数量 | 说明 |
|---|---|---|
| **P0** | 19 | V1 Must — 核心端到端闭环 |
| **P1** | 11 | V1 Should — 增强体验 |
| **P2** | 3 | V1 Could — 可延后 |

---

## INVEST 校验总结

所有 33 个 Story 均经过 INVEST 校验：
- **Independent**：除 US-06-01 ~ US-06-05 存在自然序列依赖外，其余相互独立
- **Negotiable**：验收标准可协商
- **Valuable**：每个 Story 明确给出用户/系统价值
- **Estimable**：中粒度（1-3 天量）
- **Small**：无超大 Story
- **Testable**：所有 AC 均为可测试断言

---

## 需求追溯反向索引

| FR/NFR | 覆盖 Story |
|---|---|
| FR-1.1 | US-02-01 |
| FR-1.2 | US-02-02 |
| FR-1.3 | US-02-03 |
| FR-1.5 | US-02-01 |
| FR-2.1, 2.2 | US-03-01 |
| FR-2.3 | US-03-02, US-08-03 |
| FR-2.4 | US-08-03 |
| FR-2.5 | US-03-03 |
| FR-2.6 | US-03-04 |
| FR-2.7 | US-03-05 |
| FR-3.1, 3.2 | US-04-01 |
| FR-4.1, 4.2 | US-04-02 |
| FR-4.3 | US-03-05 |
| FR-5.1 | US-05-01, US-05-02 |
| FR-5.2 | US-05-02, US-06-01, US-06-04 |
| FR-5.3 | US-06-03 |
| FR-5.4 | US-04-03 |
| FR-5.5 | US-06-01 |
| FR-6.1, 6.4 | US-06-02 |
| FR-6.3 | US-06-05 |
| FR-7 | US-08-02 |
| FR-8.1, 8.2 | US-03-01 |
| FR-8.4 | US-02-02, US-02-03 |
| FR-8.5 | US-08-04, US-NFR-05 |
| FR-9.1 | US-00-01 |
| FR-9.2 | US-01-01 |
| FR-9.3 | US-02-04 |
| FR-9.6 | US-07-01, US-07-02 |
| FR-9.7 | US-08-01~04 |
| FR-10.1 | US-00-02 |
| FR-10.2 | US-01-02, US-01-03, US-02-04 |
| FR-10.5 | US-NFR-04 |
| NFR-1 | US-NFR-01, US-NFR-02, US-05-01, US-06-01 |
| NFR-4 | US-01-04, US-NFR-03 |
| NFR-5 | US-08-04, US-NFR-05 |
| NFR-7 | US-09-01, US-09-02 |

---
