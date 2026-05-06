# U1 Platform & Infrastructure — 非功能需求计划

**Unit**：U1 Platform & Infrastructure
**阶段**：NFR Requirements
**日期**：2026-04-27

---

## 上下文摘要
U1 提供基础设施与共享库，是所有其他 Unit 的底座。其 NFR 重点：
- **可用性**：U1 故障会拖垮整个系统
- **多租户安全**：NFR-4 的核心承载者
- **可观测性**：NFR-5 的基础设施
- **成本底线**：Neptune、OpenSearch Serverless、Bedrock、AgentCore 都是成本敏感项
- **认证性能**：AuthAdapter JWT 验证是每请求路径的关键

---

## Part 1 — NFR 澄清问题

### Question U1-N1 — 预期用户规模（V1）
这将决定 DynamoDB 容量、ECS 副本数、Neptune/OpenSearch 实例规模：

A) **轻量**：< 50 活跃用户，< 10 并发分析，< 20 并发生成（内部试点）
B) **中等**：100-500 活跃用户，10-30 并发分析，30-100 并发生成 ✓
C) **大规模**：1000+ 活跃用户，50+ 并发分析，100+ 并发生成
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N2 — 可用性目标
U1 的可用性 SLA：

A) **99.5%**（每月允许 ~3.6 小时不可用，MVP 可接受）
B) **99.9%**（每月允许 ~43 分钟不可用） ✓
C) **99.95%**（每月允许 ~22 分钟，需要多 AZ + 严格容错）
D) **99.99%**（跨区域灾备，成本显著上升）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N3 — 灾备策略
灾难恢复（DR）要求：

A) **不做 DR**：依靠单区域多 AZ 高可用足够
B) **冷备**：每日快照备份，灾难发生时手动恢复（RTO 24h, RPO 24h）
C) **温备**：跨区域快照 + 基础设施预创建但不运行（RTO 4h, RPO 1h） ✓
D) **热备**：active-passive 双区域，DynamoDB Global Tables（RTO < 30min, RPO < 5min）
E) **双活**：active-active（最复杂，成本高）
F) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N4 — 认证性能目标
JWT 验证是每 API 请求的必经路径：

A) **p50 < 10ms, p99 < 50ms**（需要 JWKs 缓存 + 本地验证）✓
B) **p50 < 50ms, p99 < 200ms**（宽松）
C) **由你给出合理目标**
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-N5 — 数据保留策略
各类数据的保留时长：

A) **永久保留**（不删除）
B) **分级策略**：
  - 原文 + 生成稿：永久保留
  - Job 记录：90 天后归档到 S3 Glacier
  - 审计日志：7 年（法律合规）
  - CloudWatch Logs：30 天
  - AgentCore Observability：90 天 ✓
C) **用户可配置**：每 team 自定义保留时长
D) Other (please describe after [回答]： tag below)

[回答]： B

### Question U1-N6 — 加密要求
静态数据与传输中加密：

A) **AWS 默认加密**：S3/DynamoDB/Neptune 都用 AWS 托管 KMS key（aws/s3 等）；TLS 1.2+ 传输 ✓
B) **客户托管 KMS (CMK)**：U1 创建专用 KMS key，按 team 细分；更严格的密钥轮换策略
C) **字段级加密**：敏感字段（例如用户 email）在应用层二次加密
D) A + B（默认 A，敏感资源用 CMK）
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N7 — PII 合规
用户数据中的 PII（email、display_name、可能还有 IP）合规处理：

A) **无特殊要求**：常规存储
B) **GDPR 合规**：支持数据导出、删除、匿名化
C) **GDPR + PIPL（中国）**：双合规
D) **最小化存储**：只存 user_id，email 放 Cognito 由 AWS 托管 ✓
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N8 — 日志与 PII
日志中是否允许出现 PII？

A) **完全禁止 PII**：user_id 用 hash，email 永不出现
B) **仅 user_id 允许**，email/display_name 禁止 ✓
C) **允许但脱敏**（email 打码为 a***@b.com）
D) Other (please describe after [回答]： tag below)

[回答]： D. 允许明文存储。不用做任何处理。

### Question U1-N9 — API 限流（针对单个用户）
防止单用户过度调用：

A) **不限流**（MVP 阶段，内部试用）
B) **基础限流**：基于 Cognito user_id，每用户 100 RPS；超限返回 429 ✓
C) **分级限流**：按角色（admin 无限，regular 100 RPS，social login 50 RPS）
D) Other (please describe after [回答]： tag below)

[回答]： A.

### Question U1-N10 — CI/CD 部署策略
部署频率与策略：

A) **手动部署**（仅开发人员本地 cdk deploy）
B) **GitHub Actions 自动化 dev 部署 + 手动 prod 审批** ✓
C) **全自动蓝绿部署**（每次 merge 自动 prod）
D) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N11 — Observability 堆栈分工
U1 的可观测工具组合：

A) **AgentCore Observability only**（Agent 链路）+ **CloudWatch Logs/Metrics**（基础设施）✓
B) **A + X-Ray**（细粒度 trace）
C) **A + B + 开源堆栈**（OpenTelemetry + Jaeger/Tempo + Prometheus + Grafana）
D) **全开源**：完全用 OpenTelemetry + LGTM Stack，不用 CloudWatch
E) Other (please describe after [回答]： tag below)

[回答]： A

### Question U1-N12 — 成本预算（月度，V1 运行态）
大致的月度 AWS 账单预算（决定 Neptune/OpenSearch 实例规格与预留容量策略）：

A) **< $500/月**（超紧）
B) **$500-$2000/月**（MVP 合理区间） ✓
C) **$2000-$10000/月**（有余量）
D) **不设上限**（先跑起来再优化）
E) Other (please describe after [回答]： tag below)

[回答]： D

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U1N-1: 基于答案生成 `nfr-requirements.md`（可用性/性能/安全/保留/合规/限流/部署/预算）
- [x] Step U1N-2: 生成 `tech-stack-decisions.md`（U1 层技术选型与理由，对接 Application Design 的决策）
- [x] Step U1N-3: 更新 aidlc-state.md

---

## Part 3 — 我的推荐

- **U1-N1=B**（中等规模）：MVP 合理目标
- **U1-N2=B**（99.9%）：性价比最佳
- **U1-N3=C**（温备）：平衡 RTO/RPO 与成本
- **U1-N4=A**（严格认证延迟）
- **U1-N5=B**（分级保留）
- **U1-N6=A**（AWS 默认加密）：V1 足够
- **U1-N7=D**（最小化 PII 存储）：降低合规负担
- **U1-N8=B**（日志仅 user_id）
- **U1-N9=B**（基础限流 100 RPS）
- **U1-N10=B**（GHA + prod 审批）
- **U1-N11=A**（AgentCore Obs + CloudWatch，轻量）
- **U1-N12=B**（$500-2000/月）
