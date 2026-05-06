# U3 Understanding Agents — 基础设施设计计划

**Unit**：U3 Understanding Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28

---

## 上下文摘要
U3 几乎完全基于 U1 预建资源：
- analysis-queue + AnalysisStateMachine → 填充 U1 骨架
- worker-analysis ECS Service → 复用 U1（仅更新镜像）
- Neptune / OpenSearch → U1 已创建
- 仅新增：AgentCore 配置填充、IAM 扩展、SSM 参数、Alarm、可选 Lambda

澄清点仅 4 个。

---

## 第 1 部分 — 澄清问题

### Question U3-I1 — CDK 组织方式
类似 U2，U3 扩展是否通过 helper？

A) **`shared_constructs/u3_extensions.py`**（对齐 U2 风格）✓
B) **直接修改 U1 stacks/*.py**
C) **独立 U3 Stack**
D) 其他
[回答]： A

### Question U3-I2 — AgentCore Registration 方式
U3 需要注册 Strands Agent 到 AgentCore Runtime：

A) **CDK Custom Resource**（AwsCustomResource 调用 AgentCore Control API，部署时注册）✓
B) **CI Pipeline**（GitHub Actions 在 cdk deploy 后跑一次注册脚本）
C) **Worker 启动时自动注册**（运行时自检）
D) 其他
[回答]： C

### Question U3-I3 — Neptune SigV4 签名实现
openCypher HTTP 请求需要 SigV4 签名：

A) **自写签名**：用 `botocore.auth.SigV4Auth` 手工签 HTTP request ✓
B) **引入社区库**（`aws-neptune-gremlin` 或 `langchain-community` 的 Neptune adapter）
C) 其他
[回答]： A

### Question U3-I4 — 架构图需求
U3 架构图：

A) **2 张**：U3 数据流图（Supervisor + 6 sub-agent + 3 存储） + U3 对 U1 增量图 ✓
B) **3 张**：加一张 MemoryFacade 三后端写入流程图
C) **1 张**：仅总览
D) 其他
[回答]： B

---

## 第 2 部分 — 执行清单

- [x] Step U3I-1: 生成 `infrastructure-design.md`
- [x] Step U3I-2: 生成 `deployment-architecture.md`（3 张架构图）
- [ ] Step U3I-3: `shared_constructs/u3_extensions.py`（代码生成阶段 Phase H 处理）
- [x] Step U3I-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- I1=A（对齐 U2 风格）
- I2=A（CDK Custom Resource，声明式）
- I3=A（自写 SigV4，避免引入重型库）
- I4=A（2 张图足够）
