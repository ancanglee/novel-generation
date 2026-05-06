# U4 Generation Agents — 代码生成计划（Code Generation Plan）

**Unit**：U4 Generation Agents
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-28

---

## 1. 代码放置

```
novel-generation/
├── services/
│   ├── worker-generation/              ← 新增：U4 主 Worker
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/worker_generation/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                 (SQS 消费: generation + review 双队列)
│   │   │   ├── mode.py                 (Mode Enum)
│   │   │   ├── agents/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── outline.py          (OutlineAgent Opus 4.7)
│   │   │   │   ├── chapter.py          (ChapterAgent Sonnet 4.7 Stream)
│   │   │   │   ├── self_critique.py    (Sonnet 4.6)
│   │   │   │   ├── outline_review.py   (F3=B 异步)
│   │   │   │   └── _bedrock_stream.py  (converse_stream 辅助)
│   │   │   ├── prompts/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── clean_room.md
│   │   │   │   ├── continuation.md
│   │   │   │   ├── outline.md
│   │   │   │   ├── self_critique.md
│   │   │   │   └── outline_review.md
│   │   │   ├── cancel_cache.py         (TTLCache 8s)
│   │   │   ├── style_injection.py      (F7=C 风格注入构造器)
│   │   │   └── event_publisher.py      (EventBridge PutEvents 辅助)
│   │   └── tests/
│   └── api/                            ← 扩展：SSE 路由 + SNS 订阅
│       └── src/novelgen_api/
│           ├── routers/
│           │   ├── generations.py      (新增：/generations/*)
│           │   └── sse.py              (新增：SSE 中继)
│           ├── services/
│           │   └── sse_relay.py        (SNS/SQS 消费 + Last-Event-ID 回放)
│           └── lifespan.py             (启动时订阅 SNS，shutdown 清理)
├── lambdas/
│   └── load-generation-context/        ← 新增
│       ├── pyproject.toml
│       ├── handler.py
│       └── tests/
├── infra/cdk/
│   ├── shared_constructs/
│   │   └── u4_extensions.py            ← 新增
│   └── asl/
│       ├── chapter_workflow.json       ← 新增（Choice Loop）
│       └── outline_workflow.json       ← 新增
└── tests/
    └── integration/
        └── test_u4_generation.py       ← 新增
```

---

## 2. 覆盖 Stories

- **Primary**: US-04-01/02/03（生成配置）/ US-05-01/02（大纲）/ US-06-01（流式）/ US-06-02（Memory 约束）/ US-06-04（重写）/ US-NFR-02（单章 < 60s）
- **Collab**: US-06-03（Layer-1 Self-Critique）

---

## 3. 生成步骤

### 阶段 A — Mode / Prompts / 辅助模块
- [x] **A1**：`mode.py` + 5 Markdown prompts + loader
- [x] **A2**：`cancel_cache.py` TTLCache(8s)
- [x] **A3**：`style_injection.py` 3 块构造器（style / memory / prev chapter tail）
- [x] **A4**：`event_publisher.py` EventBridge 封装
- [x] **A5**：`agents/_bedrock_stream.py` converse_stream + invoke_tool 辅助
- [x] **A6**：tests — style_injection + cancel_cache

### 阶段 B — 4 个 Agent
- [x] **B1**：`agents/outline.py` — Opus 4.7 + Tool Use schema
- [x] **B2**：`agents/chapter.py` — converse_stream + cancel check per delta + EventBridge publishing + TTFT/duration metric
- [x] **B3**：`agents/self_critique.py` — CritiqueNote schema
- [x] **B4**：`agents/outline_review.py` — advice 数组（info/warn）
- [x] **B5**：tests — Draft 2020-12 schema 合法性 + 必填字段

### 阶段 C — Worker main
- [x] **C1**：`main.py` — 双队列 asyncio.gather 轮询 + kind 路由 (outline / chapter / review) + SFN callback + SIGTERM + GEN_CONTEXT 读取 + 前章末尾读取
- [x] **C2**：README 覆盖文档

### 阶段 D — API 扩展（SSE + 生成路由）
- [x] **D1**：`routers/generations.py` — 7 端点（create/outline/edit-outline/approve/start/rewrite）
- [x] **D2**：`services/sse_relay.py` — SNS 订阅 + per-replica SQS 消费 + subscriber filter + replay_since hook
- [x] **D3**：`routers/sse.py` — 2 端点（per-job / per-chapter）含 Last-Event-ID header + heartbeat
- [x] **D4**：`lifespan.py` — startup/shutdown 清理 relay
- [x] **D5**：集成测试覆盖于 tests/integration

### 阶段 E — Lambda load-generation-context
- [x] **E1**：`handler.py` + pyproject + tests — 读 Generation + 写 GEN_CONTEXT 24h TTL（hybrid_search 留占位）

### 阶段 F — CDK u4_extensions
- [x] **F1**：`shared_constructs/u4_extensions.py` — 4 helper（extend_data/identity/messaging/observability，含 SNS fan-out topic + Archive + 2 StateMachine）
- [x] **F2**：`asl/chapter_workflow.json` — 完整 Choice Loop + Cancel 检查
- [x] **F3**：`asl/outline_workflow.json`
- [x] **F4**：`U4_INTEGRATION.md`

### 阶段 G — Docker + 集成测试
- [x] **G1**：`services/worker-generation/Dockerfile` — python:3.12-slim
- [x] **G2**：`tests/integration/test_u4_generation.py` — mode prompts / style block / schemas

---

## 4. 估算

| Phase | 文件 | LOC |
|---|---|---|
| A 辅助 | 10 | 800 |
| B Agents | 5 | 900 |
| C Worker | 2 | 400 |
| D API | 5 | 900 |
| E Lambda | 3 | 200 |
| F CDK | 4 | 600 |
| G Docker+测试 | 2 | 200 |
| **合计** | **~31 文件** | **~4000 LOC** |

分 2 轮：
- **轮 1**：Phase A + B + C（~17 文件 / ~2100 LOC，Agent 核心 + Worker）
- **轮 2**：Phase D + E + F + G（~14 文件 / ~1900 LOC，API + Lambda + CDK + 测试）

---

## 5. 假设

- Bedrock Converse Stream API 在 us-east-1 稳定
- sse-starlette 2.1 与 FastAPI 0.115 兼容
- SNS fan-out + per-replica SQS 设计在 ECS Fargate 上可行（无持久化存储问题）

---

## 6. 用户审批

请确认：
1. 代码路径（新建 services/worker-generation，扩展 services/api，新 Lambda，新 CDK helper）
2. 分 2 轮交付
3. AgentCore SDK 未就绪处保留 NotImplementedError
