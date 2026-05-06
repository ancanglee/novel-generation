# U1 Platform & Infrastructure — 非功能设计计划

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Design
**日期**：2026-04-27

---

## 上下文摘要
上一阶段已确定：
- **SLA 99.5%**、单区多 AZ、不做 DR
- **全按需 serverless**（DynamoDB on-demand / Neptune Serverless / OpenSearch Serverless / Fargate + Spot）
- **不限流 + metric 告警**（CloudWatch → SNS）
- **CloudWatch + AgentCore Observability**（不引入 X-Ray / OTel）
- **手动部署**（GitHub Actions 只跑 lint/test/build）

本阶段把这些决策落实为具体的**设计模式 + 逻辑组件**。剩余澄清点聚焦于模式选型的实现细节。

---

## Part 1 — NFR Design 澄清问题

### Question U1-D1 — DynamoDB 单表设计的具体范式
选定单表设计后，如何组织 PK / SK？

A) **严格单表**：所有实体同一张表 `novelgen`，用 GSI 覆盖跨实体查询；遵循 Rick Houlihan 单表模式 ✓
B) **按领域分表**（稍偏离"单表"概念）：3-4 张表（tenancy_table、job_table、audit_table、config_table）
C) A + 独立的 audit 表（审计表独立便于 IAM 策略锁定写入）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-D2 — 多租户隔离的 IAM 强化
除应用层守卫外，是否在 IAM 层做 team_id 隔离？

A) **Session Tag + S3 bucket policy**：ECS Task Role 携带 `aws:RequestTag/team_id`，S3 bucket policy 要求 key 前缀匹配 tag（深度防御）✓
B) **仅应用层守卫**（简单）
C) A + DynamoDB 条件策略（IAM dynamodb:LeadingKeys），更严格但实现复杂
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-D3 — ConcurrencyState 存储
AD6=F 动态并发状态需要跨 Worker 共享。上一阶段决定不用 Redis：

A) **DynamoDB 专用项**（`PK=CONCURRENCY#{job_id}`）+ conditional update 做 CAS ✓
B) **DynamoDB + Streams 触发 Worker 订阅变化**
C) **引入 ElastiCache Serverless（Redis）**（突破上阶段决策，适合需要毫秒级共享状态）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-D4 — 健康检查与容器生命周期
ECS Task 的优雅停止（shutdown）策略：

A) **SIGTERM → 30s 优雅窗口 → SIGKILL**：接收信号后停止接收新请求，等待在途请求完成 ✓
B) **简单重启**：收到 SIGTERM 立即退出
C) **长窗口**：90s 优雅窗口（生成任务可能较长）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-D5 — 跨 Unit 共享库的版本控制
monorepo 中共享库（如 packages/auth-adapter）如何被其他 Unit 消费？

A) **路径依赖**（`uv workspace`）：直接引用本地路径，编译时一并打包 ✓
B) **版本号 + 私有 PyPI**：每次共享库发布新版本；消费方锁定版本
C) **Git tag / submodule**：较重
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-D6 — Step Functions 错误处理策略
任务失败时是否自动恢复？

A) **Task-level Retry + Catch**：每 Task 内置 3 次指数退避；彻底失败则 Catch 到 Fail 状态 ✓
B) **全工作流 Retry**：整个 workflow 失败后重试一次
C) **无自动重试**，失败直接 FAIL（依靠用户手动重试）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-D7 — SSE 长连接保活策略
ApiService 的 SSE 端点如何防 CloudFront/ALB idle 超时？

A) **周期心跳事件**（每 15s 发 `event: heartbeat`）+ ALB idle timeout 设 600s ✓
B) **客户端定期 ping**（浏览器侧主动拉一次健康检查）
C) **WebSocket 替代**（已被 AD4=A 否决）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-D8 — CloudWatch Metric 发射策略
成本相关 metric（token 消耗、cross_team_denied）如何发射？

A) **EMF 格式写入 CloudWatch Logs**（0 额外调用成本）+ Log Metric Filter 抽取 ✓
B) **直接 PutMetricData API**（每调用 $0.01 / 1000 metric），延迟低但成本高
C) A + B 混合：高频指标用 EMF，低频关键指标用 PutMetricData
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-D9 — 可观测数据存储位置
Token 消耗指标的查询接口：

A) **CloudWatch Metric Math + GetMetricData API**（Admin UI 查询时实时 query） ✓
B) **ETL 到 DynamoDB 聚合表**（admin 预聚合成本报表）
C) **S3 + Athena**（历史分析）
D) A + B：实时看 CloudWatch，历史报表看预聚合表
E) Other (please describe after [回答]： tag below)

[回答]： D

### Question U1-D10 — Secrets 管理
哪些类型的 secret 放 Secrets Manager？

A) **全部 secret**：Cognito app client secret、社交 IdP OAuth secret、Bedrock 特定配置、数据库密钥、第三方 API Key ✓
B) **仅敏感 secret**（OAuth secret、API Key），非敏感配置用 SSM Parameter Store
C) **SSM Parameter Store 全覆盖**（含 SecureString）
D) Other (please describe after [回答]： tag below)

[回答]： B

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U1D-1: 生成 `nfr-design-patterns.md`
- [x] Step U1D-2: 生成 `logical-components.md`
- [x] Step U1D-3: 更新 aidlc-state.md

---

## Part 3 — 我的推荐

- **U1-D1 = A** 严格单表 + GSI
- **U1-D2 = A** Session Tag + S3 bucket policy（深度防御，实施成本低）
- **U1-D3 = A** DynamoDB conditional update（延续上阶段不引入 Redis 决策）
- **U1-D4 = A** 30s 优雅窗口（Worker 长任务不在 ECS Task 内长阻塞，任务状态存 DynamoDB）
- **U1-D5 = A** 路径依赖（monorepo 最佳实践）
- **U1-D6 = A** Task-level Retry + Catch（Step Functions 标准做法）
- **U1-D7 = A** 15s 心跳 + 600s timeout
- **U1-D8 = A** EMF（成本最优）
- **U1-D9 = A** 实时 Metric Math query（避免预聚合维护）
- **U1-D10 = A** 全部放 Secrets Manager（简单统一）
