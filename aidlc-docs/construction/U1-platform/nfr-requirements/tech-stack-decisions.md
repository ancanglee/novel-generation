# U1 Tech Stack Decisions

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Requirements
**日期**：2026-04-27

本文记录 U1 层的技术选型决策，作为 Infrastructure Design 与 Code Generation 的输入。

---

## 1. 基础设施即代码（IaC）

| 方向 | 决策 | 理由 |
|---|---|---|
| IaC 工具 | **AWS CDK (Python)** | requirements.md 指定；Python 与后端同语言，类型安全 |
| CDK 版本 | **v2** (aws-cdk-lib) | v1 已 EOL |
| 构造库 | 官方 + aws-solutions-constructs | 社区经过验证 |
| 项目布局 | 单 CDK App，多 Stack | Network / Data / Compute / Edge / Observability |

---

## 2. 计算（Compute）

| 方向 | 决策 | 理由 |
|---|---|---|
| API/BFF/Worker 运行时 | **ECS Fargate**（requirements.md 指定） | 按需计费、免服务器运维 |
| Fargate 类型 | **Fargate + Fargate Spot 混合**（Clarify 1=B） | Worker 用 Spot 节省；API 全 Fargate（可用性优先） |
| 镜像仓库 | **Amazon ECR** | 与 ECS 最佳集成 |
| 容器编排 | **ECS Service** + Application Auto Scaling | 简单、与 CDK 集成好 |

**为什么不用 Lambda**：
- Worker 长时任务（单章 60s）超 API Gateway 30s 超时约束
- 流式 SSE 的长连接需求
- Strands Agents 的初始化开销较大，不适合冷启动

---

## 3. 存储

### 3.1 元数据与状态
| 方向 | 决策 | 理由 |
|---|---|---|
| 主元数据存储 | **DynamoDB**（requirements.md 指定） | 多租户 PK 前缀天然隔离、性能稳定 |
| 容量模式 | **on-demand** | Clarify 1=B 全按需 |
| 设计模式 | **单表设计** + GSI | 一表多实体，减少跨表事务 |
| 备份 | **PITR 启用** | 35 天回溯 |

### 3.2 对象存储
| 方向 | 决策 | 理由 |
|---|---|---|
| 原文与生成稿 | **S3**（requirements.md 指定） | 大文件存储首选 |
| 存储类 | **Intelligent-Tiering** | 自动冷热分层 |
| 版本化 | **启用** | 防误删 |
| 加密 | **SSE-S3**（AWS managed） | U1-N6=A |

### 3.3 知识图谱
| 方向 | 决策 | 理由 |
|---|---|---|
| 图数据库 | **Amazon Neptune Serverless**（AD1=A, Clarify 1=B 按需） | 1-128 NCU 自动伸缩，空闲成本可控 |
| 查询语言 | **openCypher**（主）+ Gremlin（备） | openCypher 更直观 |
| 驱动 | `requests` + `aws-sigv4` | Neptune Serverless 用 IAM 签名认证 |

### 3.4 向量检索
| 方向 | 决策 | 理由 |
|---|---|---|
| 向量存储 | **OpenSearch Serverless (Vector Search Collection)**（AD2=A） | kNN + 混合检索 |
| 最小容量 | **2 OCU 搜索 + 2 OCU 索引** | 入门门槛 |
| 嵌入模型 | **Amazon Titan Embeddings V2** | 与 Bedrock 同栈、成本低 |
| 维度 | **1024**（Titan V2 默认） | 性能与精度平衡 |

### 3.5 缓存
| 方向 | 决策 | 理由 |
|---|---|---|
| L1（进程内）| **cachetools.TTLCache** | 适合 JWKs、ModelConfig |
| L2（共享）| **不引入 Redis/ElastiCache（V1）** | 降低运维复杂度；ConcurrencyState 用 DynamoDB 替代 |

---

## 4. 身份与认证

| 方向 | 决策 | 理由 |
|---|---|---|
| 用户池 | **Amazon Cognito User Pool** | AWS 原生、与 IAM/ECS 集成 |
| 社交登录 | **Google + GitHub IdP**（Q20=B） | 通过 Cognito Hosted UI |
| Token 格式 | **OIDC id_token (JWT)** | 标准化 |
| JWKs 缓存 | 进程内 15 min TTL | 满足 NFR-3.1 p99 200ms |
| Workload Identity | **AgentCore Identity**（Clarify 2 from AD = A） | Agent → 外部工具 token |

---

## 5. 异步编排

| 方向 | 决策 | 理由 |
|---|---|---|
| 工作流引擎 | **AWS Step Functions Standard**（AD5=A） | 长时任务（1 年）+ 可视化 + 内置重试 |
| 消息队列 | **Amazon SQS**（5 个队列 + DLQ） | Step Functions 派发 |
| 事件总线 | **Amazon EventBridge default bus** | Worker → ApiService SSE 事件 |
| 定时调度 | **EventBridge Scheduler** | 一致性校验兜底 |

---

## 6. Agent 框架

| 方向 | 决策 | 理由 |
|---|---|---|
| Agent 框架 | **Strands Agents + AgentCore Runtime**（AD7=B） | 用户选择；Strands 编排 + AgentCore 托管执行 |
| LLM 调用 | **Bedrock Converse API**（含 Stream） | 统一 API，支持流式 |
| LLM 模型 | **Claude Opus 4.7 / Sonnet 4.6/4.7 / Haiku 4.5** | requirements.md 指定 |
| 记忆 | **AgentCore Memory**（结构化 + 语义） | 平台原生 |
| 工具网关 | **AgentCore Gateway** | 统一对接外部 API |
| 浏览器 | **AgentCore Browser** | 公版书搜索 + URL 抓取 |

---

## 7. 前端

| 方向 | 决策 | 理由 |
|---|---|---|
| 用户 SPA | **React 18 + TypeScript + Vite + Tailwind + shadcn/ui**（Q17=A） | 现代主流 |
| Admin SPA | **独立子应用，同技术栈**（AD3=B） | 独立部署 |
| BFF | **Node.js LTS + Express**（AD9=A Thin BFF） | 轻量 |
| 数据请求 | **TanStack Query** | 缓存 + 重试 |
| 状态管理 | **Zustand**（小型）| 轻量 |
| 路由 | **@tanstack/react-router** | 类型安全 |
| 可视化 | Recharts（雷达图）+ React Flow（关系图）+ Leaflet（地图简图）| 各司其职 |

---

## 8. 后端语言与框架

| 方向 | 决策 | 理由 |
|---|---|---|
| 后端语言 | **Python 3.12**（requirements.md 指定） | |
| Web 框架 | **FastAPI** + **Uvicorn (standard)** | 异步 + pydantic + OpenAPI 自动生成 |
| 数据模型 | **pydantic v2** | 性能 + 类型 |
| AWS SDK | **boto3** + **aioboto3** | sync 在 API，async 在 Worker |
| 依赖管理 | **uv**（monorepo workspace）| 速度 + workspace 支持 |
| 测试 | **pytest** + **pytest-asyncio** + **moto** | moto mock AWS 资源 |
| 格式化 | **black** + **ruff** | |
| 类型检查 | **mypy --strict** | |

---

## 9. 网络与边缘

| 方向 | 决策 | 理由 |
|---|---|---|
| 前端托管 | **ECS Fargate**（承载 BFF + 静态文件）（Q19=C） | |
| CDN | **CloudFront** + **Origin Failover** | 全球加速；中国用户通过边缘 |
| WAF | **AWS WAF**（managed rule set） | 常见攻击防护 |
| DNS | **Route 53** | |
| TLS | **ACM 证书** | 自动续期 |
| VPC | **双 AZ，私有子网 + NAT**（ECS 在私网） | 安全隔离 |
| ALB | **Application Load Balancer** | 路径路由（/api, /admin）|

---

## 10. 可观测

| 方向 | 决策 | 理由 |
|---|---|---|
| Agent 链路 | **AgentCore Observability** | 平台原生，U1-N11=A |
| 基础设施 | **CloudWatch**（Logs、Metrics、Alarms） | U1-N11=A |
| 分布式追踪 | **不引入 X-Ray/OpenTelemetry**（V1 最简） | U1-N11=A；V2 可评估 |
| 结构化日志 | JSON + **aws-lambda-powertools.Logger**（通用版） | |
| 告警通知 | **SNS → Email** | 简单可靠 |
| 账单告警 | **AWS Cost Anomaly Detection** | |

---

## 11. 数据保护

| 方向 | 决策 | 理由 |
|---|---|---|
| 静态加密 | **AWS managed KMS keys**（U1-N6=A） | V1 足够 |
| 传输加密 | **TLS 1.2+** | CloudFront / ALB 强制 |
| Secret 管理 | **AWS Secrets Manager** | Cognito App secret、第三方 API key |
| IAM 原则 | **最小权限 + Session Tag**（team_id 传播） | 多租户守卫深度防御 |

---

## 12. CI/CD

| 方向 | 决策 | 理由 |
|---|---|---|
| VCS | **Git（GitHub）** | |
| CI | **GitHub Actions** | lint / test / build 自动化 |
| 自动部署 | **不启用**（U1-N10=A） | 手动 `cdk deploy` |
| 镜像构建 | **GitHub Actions → ECR push** | |
| 依赖扫描 | **Dependabot** + **pip-audit** | |
| 代码扫描 | **CodeQL**（GitHub 内置） | |

---

## 13. 决策影响矩阵（下游 Unit）

| 技术决策 | 影响 Unit | 影响说明 |
|---|---|---|
| 单表 DynamoDB | U2-U7 | 所有实体写入需用 Repository 抽象（U1 提供） |
| Step Functions Standard | U2-U5 | 长时任务必须用 SF execution |
| EventBridge 事件总线 | U3-U7 | 跨 Unit 通信用 EventBridge，不用直接 RPC |
| Strands Agents 框架 | U3/U4/U5 | Agent 代码基于 Strands + AgentCore Runtime SDK |
| Neptune Serverless | U3/U5 | 图查询用 openCypher，有冷启动 |
| OpenSearch Serverless | U3/U4 | 向量检索用 OpenSearch；kNN 查询 |
| Titan Embeddings V2 | U3/U4 | 所有嵌入用相同模型（1024 维） |
| 手动部署 | U1-U7 | CI 只跑测试，部署靠人手 |

---

## 14. 未决项（Infrastructure Design 解决）

- VPC CIDR 分配方案
- ECS Task 资源规格（CPU / Memory 初值）
- ALB 路径路由规则细节
- SQS 队列具体参数（Visibility Timeout, DLQ 策略）
- Step Functions 状态机的完整 ASL 定义
- IAM 角色与策略列表
- CloudWatch Alarm 完整清单
- Route 53 + ACM 证书域名
- Secrets Manager 中的 secret 清单

上述由 U1 Infrastructure Design 阶段完成。
