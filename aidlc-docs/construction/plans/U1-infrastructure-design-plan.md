# U1 Platform & Infrastructure — 基础设施设计计划

**Unit**：U1 Platform & Infrastructure
**阶段**：Infrastructure Design
**日期**：2026-04-27

---

## 上下文摘要
NFR Design 已确定 ~80 个逻辑组件。本阶段的工作：
1. 填充最后未决的具体参数（VPC CIDR、域名、具体 ASL、IAM 策略 JSON）
2. 生成**部署架构图**（多张，Mermaid / ASCII）
3. 划分 CDK Stack
4. 输出 `infrastructure-design.md` 与 `deployment-architecture.md`

---

## Part 1 — Infrastructure 澄清问题

### Question U1-I1 — AWS 区域
目标区域（Bedrock + AgentCore + Neptune Serverless + OpenSearch Serverless 都要可用）：

A) **us-east-1**（N. Virginia，最全服务）✓
B) **us-west-2**（Oregon，AWS 首发区）
C) **ap-northeast-1**（Tokyo，亚洲用户延迟友好，但 Neptune Serverless/某些 AgentCore 特性可能滞后）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-I2 — 域名与 TLS
应用对外域名：

A) **使用你现有的域名 + 子域**（例如 `app.novelgen.example.com` / `admin.novelgen.example.com`，你已在 Route 53 有 Hosted Zone）
B) **临时使用 CloudFront 默认域名**（*.cloudfront.net，无自定义域名，用于内部测试）✓
C) **新购域名**（CDK 不管理购买，需要手动）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-I3 — CDK Stack 划分粒度
CDK Stack 如何组织？

A) **单 Stack**：所有资源在一个 stack 中（简单但部署慢，失败回滚影响大）
B) **分层 Stack**（推荐）✓：
  - `NetworkStack`（VPC/Subnets/VPCE/SG）
  - `DataStack`（DynamoDB/S3/Neptune/OpenSearch/Secrets）
  - `IdentityStack`（Cognito + IAM Roles）
  - `MessagingStack`（SQS/EventBridge/Step Functions）
  - `ComputeStack`（ECS Cluster/Services/ALB）
  - `EdgeStack`（CloudFront/WAF/Route 53）
  - `ObservabilityStack`（LogGroups/Alarms/SNS/Aggregator Lambda）
  - `AgentCoreStack`（AgentCore Memory/Gateway/Browser/Identity/Observability 配置）
C) **按 Unit 划分**（每 Unit 独立 stack，粒度过细 V1 不需要）
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-I4 — 环境数量
部署环境：

A) **仅 dev**（V1 内部试点，单环境） ✓
B) **dev + prod**（两环境）
C) **dev + staging + prod**（三环境，合规友好）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-I5 — 架构图要求
你希望的架构图：

A) **系统概览图**（1 张，所有组件关系）
B) **系统概览 + 数据流（分析/生成两条）**（3 张）
C) **系统概览 + 数据流 + 网络拓扑 + CDK Stack 依赖**（5 张）✓ 推荐
D) Other (please describe after [回答]： tag below)

[回答]： C

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U1I-1: 生成 `infrastructure-design.md`（含 VPC CIDR 分配、IAM Role 具体策略、Step Functions ASL 骨架、CloudFront 配置细节）
- [x] Step U1I-2: 生成 `deployment-architecture.md`（含架构图 × 5）
- [x] Step U1I-3: 生成 CDK Stack 划分清单与依赖关系
- [ ] Step U1I-4: 更新 aidlc-state.md

---

## Part 3 — 我的推荐

- I1=A（us-east-1 最稳）
- I2=B（CloudFront 默认域，V1 内部够用）
- I3=B（分层 Stack，最佳实践）
- I4=A（单 dev 环境，V1 试点）
- I5=C（5 张架构图）
