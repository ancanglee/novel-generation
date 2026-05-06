# U3 Understanding Agents — 非功能需求计划

**Unit**：U3 Understanding Agents
**阶段**：NFR Requirements
**日期**：2026-04-28

---

## 上下文摘要
U3 继承 U1+U2 的 NFR 基础（us-east-1 / 99.5% SLA / 按需 serverless / 无 API 限流 / token metric 告警）。

本阶段聚焦 U3 特有项：
- NFR-1（US-NFR-01）性能：100 万字分析 < 15 min — F4=A + F7=A 修订后已可达
- Bedrock 配额：~330 次/小说 × 多租户并发
- Neptune Serverless 性能基线
- OpenSearch 向量检索延迟
- Agent 可观测性细节

---

## 第 1 部分 — 澄清问题（7 个）

### Question U3-N1 — 分析延迟分层目标
100 万字小说分析目标已定（< 15 min, NFR-1）。分小说规模的 SLA：

A) **统一 < 15 min**（无论大小都用一套目标）
B) **分档**：
  - < 10 万字：< 3 min
  - 10-100 万字：< 15 min
  - 100-500 万字：< 45 min
  ✓
C) 其他
[回答]： A

### Question U3-N2 — Bedrock 配额策略
U3 预计 ~330 次/小说调用。假设 10 并发小说分析，瞬时 RPS 峰值 ~50：

A) **使用默认配额**：不主动申请提升，依靠 AD6=F 动态并发自适应应对 throttle ✓
B) **申请 Claude Sonnet 配额提升**：向 AWS Support 提工单，请求 RPS=100（至少 2×）
C) A 为 MVP 起步，后续根据实际数据决定是否申请
D) 其他
[回答]： A

### Question U3-N3 — Neptune Serverless 性能基线
图写入/查询的延迟目标：

A) **宽松**：节点/边 upsert p95 < 500ms；邻居查询（depth=1）p95 < 1s ✓
B) **严格**：upsert p95 < 200ms；查询 p95 < 300ms（可能需要配更大 NCU）
C) 其他
[回答]： B

### Question U3-N4 — OpenSearch 向量检索延迟
recall() 延迟目标：

A) **kNN p95 < 300ms**（top_k=20 常规查询）✓
B) **kNN p95 < 1s**（宽松）
C) 其他
[回答]： A

### Question U3-N5 — Agent 内存 Checkpoint
Supervisor 每 N 步写 checkpoint（用于 Spot 回收恢复）：

A) **每 5 步**（Flow 12 已定）✓
B) **每 10 步**（checkpoint 写入成本减半，但恢复损失更多步骤）
C) **不做 checkpoint**（接受失败重头跑）
D) 其他
[回答]： A

### Question U3-N6 — 文档嵌入模型选择
Titan Embeddings V2 有多种规格（256 / 512 / 1024 维）：

A) **1024 维**（精度最高，OpenSearch 存储 ~4KB/向量）✓
B) **512 维**（平衡，~2KB/向量）
C) **256 维**（成本最低，精度损失明显）
D) 其他
[回答]： A

### Question U3-N7 — Agent 失败重试预算
单章 DeepRead 失败（LLM 异常/JSON 解析失败）最多重试几次？

A) **2 次**（NFR-5.1 统一的重试上限，快速失败）
B) **3 次**（轻微冗余，能应对短暂抖动）✓
C) **5 次**（过度重试可能拖慢整体）
D) 其他
[回答]： B

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U3N-1: 生成 `nfr-requirements.md`
- [x] Step U3N-2: 生成 `tech-stack-decisions.md`
- [x] Step U3N-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- N1=B 分档（不同规模不同期望）
- N2=C 先默认配额 MVP，后续按需申请
- N3=A 宽松基线（Neptune Serverless 冷启动不可避免）
- N4=A kNN < 300ms（OpenSearch Serverless 通常能达）
- N5=A 每 5 步 checkpoint
- N6=A 1024 维（召回质量优先；存储成本对 V1 可接受）
- N7=B 3 次重试
