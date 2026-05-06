# U2 Ingestion Service — 基础设施设计计划

**Unit**：U2 Ingestion Service
**阶段**：Infrastructure Design
**日期**：2026-04-27

---

## 上下文摘要
U2 的 Infrastructure 几乎完全基于 U1：
- ingestion-queue + DLQ → 扩展 U1 `MessagingStack`
- worker-ingestion ECS Service → 扩展 U1 `ComputeStack`
- IngestionStateMachine ASL 填充 → 修改 U1 `MessagingStack`
- S3 Lifecycle + SSM Parameters → 扩展 U1 `DataStack`
- Alarms → 扩展 U1 `ObservabilityStack`

几乎无独立新 Stack；澄清点仅 3 个。

---

## 第 1 部分 — 澄清问题

### Question U2-I1 — CDK Stack 归属
U2 新资源是否放独立 Stack？

A) **全部在 U1 对应 Stack 内扩展**（Messaging/Compute/Data/Observability），保持分层一致 ✓
B) **新建 `U2IngestionStack`** 独立部署
C) 部分混合：worker-ingestion 独立 Stack，其他扩展 U1
D) 其他
[回答]： A

### Question U2-I2 — Browser 并发与成本控制
AgentCore Browser 会话如何管控？

A) **应用层 Semaphore**：Worker 内 `asyncio.Semaphore(3)` 限制单 Task 并发 Browser 数 ✓
B) **全局 DynamoDB 计数器**：跨所有 Worker 共享计数器，上限 10
C) A + B 组合
D) 其他
[回答]： B

### Question U2-I3 — IngestionStateMachine 架构
最终 ASL 结构：

A) **单状态机处理 3 种触发**（upload / download / crawl），内部 Choice state 分支 ✓
B) **每种触发一个独立状态机**（IngestionUpload / IngestionDownload / IngestionCrawl）
C) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后执行）

- [x] Step U2I-1: 生成 `infrastructure-design.md`
- [x] Step U2I-2: 生成 `deployment-architecture.md`
- [x] Step U2I-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- I1=A（扩展 U1 Stack，保持分层一致）
- I2=A（应用层 Semaphore 3 并发，简单有效；全局计数器增加复杂度，V1 无需）
- I3=A（单状态机 + Choice state，运维简单）
