# U6 Frontend + BFF — 基础设施设计计划

**Unit**：U6 Frontend + BFF
**阶段**：Infrastructure Design
**日期**：2026-04-30

---

## 上下文摘要
U6 基础设施与 U1 已有底座高度复用：Cognito User Pool、CloudFront distribution、ALB、ECS Cluster、S3 buckets 都已存在。U6 增量聚焦：
- 新增 1 个 ECS Fargate Service（bff-user）
- 复用/新增 1 个 S3 静态 Bucket
- CloudFront 追加 3 behaviors
- ALB 追加 2 listener rules（/api/*/stream 独立规则）
- 1 个 Secrets Manager secret（BFF session 签名密钥）
- 4+1 CloudWatch Alarms（NFR Design 已定）

---

## 第 1 部分 — 澄清问题（4 个）

### Question U6-I1 — CDK 组织方式
沿用哪种模式：

A) **`shared_constructs/u6_extensions.py`**（对齐 U2/U3/U4/U5 风格）✓
B) 新建独立 `u6_frontend_stack.py`
C) 直接改 U1 stacks
D) 其他
[回答]：A

### Question U6-I2 — 静态资源托管
前端构建产物（Vite build）放哪里？

A) **复用 U1 预建 `novels-raw` bucket 下的 `/frontend/` 前缀**（省资源）
B) **新建 `novelgen-frontend-{env}` 专用 bucket + CloudFront OAC**（职责清晰，便于回滚与版本化）✓
C) 直接放 CloudFront 内联（不可行）
D) 其他
[回答]：A

### Question U6-I3 — BFF 部署形态
BFF 部署选型：

A) **ECS Fargate Service（2 task × 0.25 vCPU / 0.5 GB mem, 同 U1 ECS Cluster）**✓
B) **Lambda + API Gateway**（SSE 需 streaming response，AWS Lambda Response Streaming 支持但复杂）
C) **EC2 自建**（运维重）
D) 其他
[回答]：A

### Question U6-I4 — 架构图数量
A) **2 张**：U6 前后端数据流 + 部署拓扑 ✓
B) **3 张**：加 CloudFront/ALB 路由流
C) **1 张**
D) 其他
[回答]：B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U6I-1: 生成 `infrastructure-design.md`（CDK、资源清单、IAM、Cookie 密钥、ALB/CloudFront）
- [x] Step U6I-2: 生成 `deployment-architecture.md`（架构图按 I4=B 3 张）
- [x] Step U6I-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **I1=A** `u6_extensions.py`（对齐 U2-U5）
- **I2=B** 独立 `novelgen-frontend-{env}` bucket（版本化 + 回滚一键切，CloudFront OAC 简单）
- **I3=A** ECS Fargate（SSE 流式在 Fargate 最稳定；Lambda streaming 虽可但连接时限与冷启动复杂）
- **I4=A** 2 张图（U6 资源增量 ~10 个，3 张会冗余）
