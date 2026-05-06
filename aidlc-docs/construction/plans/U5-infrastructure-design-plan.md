# U5 Critic & Consistency — 基础设施设计计划

**Unit**：U5 Critic & Consistency
**阶段**：Infrastructure Design
**日期**：2026-04-28

---

## 上下文摘要
U5 绝大部分资源复用 U1 预建（critic-queue / consistency-queue / worker-critic / worker-consistency / moderation-queue 作为 V2 占位）。Infrastructure Design 主要聚焦：
- CDK 代码组织方式
- 新增 1 条 EventBridge Rule（consistency-trigger-to-queue）
- 4 条 CloudWatch Alarms
- 3 条 SSM Parameters
- 4 个 API 端点在哪里实现（复用 ApiService vs 新容器）
- 架构图数量

澄清面极窄 —— 4 个问题。

---

## 第 1 部分 — 澄清问题（4 个）

### Question U5-I1 — CDK 组织方式
沿用哪种模式向 U1 Stack 注入 U5 资源（EventBridge Rule、SSM、Alarms）？

A) **`shared_constructs/u5_extensions.py`**（对齐 U2 / U3 / U4 风格，在 U1 Stack 构造函数里调用 `apply_u5_extensions(stack, props)`）✓
B) 直接修改 U1 stacks（侵入性强）
C) 独立 U5 Stack（只为 1 个 Rule + 4 Alarms 新建 Stack 过重）
D) 其他
[回答]：A

### Question U5-I2 — Critic / Consistency Report API 端点的部署形态
`GET /api/v1/generations/{gid}/chapters/{n}/critique`、`GET /api/v1/.../consistency-reports`、`POST /api/v1/conflicts/{cid}/ignore`、`POST /api/v1/conflicts/{cid}/rewrite` 4 个端点：

A) **在现有 `api-service` Fargate Task 内追加路由**（单容器，router 模块化，部署简单）✓
B) **独立 `api-critic` 容器**（按 Unit 拆 Service，运维成本↑）
C) 用 Lambda + API Gateway（与 U4 SSE 架构冲突）
D) 其他
[回答]：A

### Question U5-I3 — `consistency.trigger` Rule 的放置位置
ChapterAgent 发 `consistency.trigger` 事件（U4 Worker 内）→ EventBridge Rule → `consistency-queue`（U1 预建）。这条 Rule 属于：

A) **U5（`u5_extensions.py` 新建），event bus = U1 的 `novelgen-default-bus`**（新事件类型归 U5 管理）✓
B) U1 预建（需修改 U1 stacks）
C) U4 管理（因为事件源在 ChapterAgent）
D) 其他
[回答]：C

### Question U5-I4 — 架构图数量
A) **2 张**：U5 数据流图 + U5 增量部署图 ✓
B) **3 张**：加一张 Critic + Consistency + Rewrite 时序图
C) **1 张**
D) 其他
[回答]：B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U5I-1: 生成 `infrastructure-design.md`（CDK 组织、资源清单、IAM、SSM、Alarms、API 路由）
- [x] Step U5I-2: 生成 `deployment-architecture.md`（架构图按 I4 决定）
- [x] Step U5I-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **I1=A** `shared_constructs/u5_extensions.py`（完全对齐 U2/U3/U4，最低风险）
- **I2=A** 复用现有 `api-service`（U4 已是多路由容器，新增 4 个 handler 与 SSE 同进程共享 DDB/Publisher，部署一次到位）
- **I3=A** Rule 归 U5 所有（`u5_extensions.py` 声明，事件走 U1 的 default bus，不修改 U1 stacks）
- **I4=A** 2 张图（U5 资源增量极少，3 张图会冗余）
