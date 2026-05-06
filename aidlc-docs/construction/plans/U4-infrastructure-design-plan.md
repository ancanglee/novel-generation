# U4 Generation Agents — 基础设施设计计划

**Unit**：U4 Generation Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28

---

## 上下文摘要
U4 基础设施沿用 U2/U3 模式：通过 `shared_constructs/u4_extensions.py` 扩展 U1 Stack，不新建独立 Stack。澄清面很窄。

---

## 第 1 部分 — 澄清问题（4 个）

### Question U4-I1 — CDK 组织方式
A) **`shared_constructs/u4_extensions.py`**（对齐 U2/U3 风格）✓
B) 直接修改 U1 stacks
C) 独立 U4 Stack
D) 其他
[回答]： A

### Question U4-I2 — SSE 端点实现形态
ApiService 的 SSE 端点在 FastAPI 中如何实现？

A) **`sse-starlette.EventSourceResponse`**（已在 NFR tech-stack 决定）✓
B) **自写 StreamingResponse + 手动 yield SSE 格式**
C) 其他
[回答]： A

### Question U4-I3 — EventBridge → SSE 中继拉取方式
ApiService 如何从 EventBridge 接收事件并中继给 SSE 客户端？

A) **EventBridge API Destinations → ApiService 内部 HTTP endpoint**（同步推送，需公网端点）
B) **EventBridge Rule → SQS 队列 → ApiService 消费**（缓冲，支持多 replica）✓
C) **EventBridge Rule → Lambda → invoke ApiService**（复杂）
D) 其他
[回答]： B

### Question U4-I4 — 架构图数量
A) **2 张**：U4 生成数据流 + 增量部署图 ✓
B) **3 张**：加一张 SSE 事件流时序图
C) **1 张**
D) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U4I-1: 生成 `infrastructure-design.md`
- [x] Step U4I-2: 生成 `deployment-architecture.md`（3 张架构图）
- [x] Step U4I-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- I1=A 扩展 U1（对齐 U2/U3）
- I2=A sse-starlette
- I3=B EventBridge → SQS → ApiService（最稳定、支持多 replica）
- I4=A 2 张图（避免文档膨胀）
