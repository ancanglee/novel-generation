# U3 Understanding Agents — 代码生成计划（Code Generation Plan）

**Unit**：U3 Understanding Agents
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-28

---

## 1. 代码放置

```
novel-generation/
├── services/
│   └── worker-analysis/            ← 新增：U3 主交付物
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/worker_analysis/
│       │   ├── __init__.py
│       │   ├── main.py             (SQS consumer + Supervisor entry)
│       │   ├── supervisor.py       (Opus 4.7 + few-shot)
│       │   ├── agents/             (6 sub-agents + memory_writer)
│       │   │   ├── __init__.py
│       │   │   ├── rough_read.py
│       │   │   ├── classification.py
│       │   │   ├── character_global.py
│       │   │   ├── map_global.py
│       │   │   ├── style.py
│       │   │   ├── chapter_all.py
│       │   │   ├── profile_rewrite.py
│       │   │   └── memory_writer.py
│       │   ├── memory/             (MemoryFacade 完整实现)
│       │   │   ├── __init__.py
│       │   │   ├── facade_impl.py
│       │   │   ├── agentcore_memory.py
│       │   │   ├── neptune_client.py
│       │   │   └── opensearch_client.py
│       │   ├── prompts/            (Markdown 系统 prompt)
│       │   │   ├── supervisor.md
│       │   │   ├── chapter_extraction.md
│       │   │   ├── style.md
│       │   │   ├── classification.md
│       │   │   ├── character_global.md
│       │   │   └── map_global.md
│       │   ├── agentcore_registration.py  (Worker 启动时自注册 I2=C)
│       │   └── checkpoint.py       (每 5 步 DDB Checkpoint)
│       └── tests/
├── lambdas/
│   └── load-novel-metadata/        ← 新增：AnalysisStateMachine 前置 Lambda
│       ├── pyproject.toml
│       ├── handler.py
│       └── tests/
├── infra/cdk/
│   ├── shared_constructs/
│   │   └── u3_extensions.py        ← 新增：扩展 U1 Stack 的 helper
│   └── asl/
│       └── analysis_workflow.json  ← 新增：完整 AnalysisStateMachine ASL
└── tests/
    └── integration/
        └── test_u3_analysis.py     ← 新增：U3 端到端 smoke
```

---

## 2. 覆盖 Stories

- **Primary**: US-03-01 触发分析 / US-03-02 类型鉴别 / US-03-03 人物报告 / US-03-04 地图路线 / US-03-05 风格雷达 / US-NFR-01 性能
- **Collab**: US-06-02（为 U4 提供 Memory 约束）/ US-08-02 模型配置生效 / US-08-03 类型标签合并

---

## 3. 生成步骤

### 阶段 A — MemoryFacade 具体实现
- [x] **A1**：`memory/agentcore_memory.py` — SDK placeholder wrapper
- [x] **A2**：`memory/neptune_client.py` — openCypher + botocore SigV4 + tenacity retry
- [x] **A3**：`memory/opensearch_client.py` — AsyncOpenSearch + kNN + bulk + RRF hybrid
- [x] **A4**：`memory/facade_impl.py` — 三后端 asyncio.gather 并行 + 分层降级 + 进程 LRU 嵌入缓存
- [x] **A5**：tests — facade 降级行为 + 嵌入缓存

### 阶段 B — Prompts
- [x] **B1**：`prompts/supervisor.md` — 3 few-shot + 9 工具清单 + 硬约束
- [x] **B2**：`prompts/chapter_extraction.md` — F7=A 单次复合调用指令
- [x] **B3**：`prompts/style.md` + `classification.md` + `character_global.md` + `map_global.md` + loader

### 阶段 C — Sub-agents
- [x] **C1**：`agents/rough_read.py` — Haiku 自适应 + 首末强制保留
- [x] **C2**：`agents/classification.py` — 多标签 + 置信度
- [x] **C3**：`agents/character_global.py` — 粗读 Profile 初稿
- [x] **C4**：`agents/map_global.py` — places + factions + edges
- [x] **C5**：`agents/style.py` — 6 维风格向量
- [x] **C6**：`agents/chapter_all.py` — Bedrock Tool Use 强制 JSON schema
- [x] **C7**：`agents/profile_rewrite.py` — Opus 4.7 重写
- [x] **C8**：`agents/memory_writer.py` — MemoryFacade 批量 flush
- [x] **C9**：tests — 抽样 bounds + 所有 schema Draft 2020 合法性

### 阶段 D — Supervisor + Checkpoint
- [x] **D1**：`supervisor.py` — Opus 4.7 Tool Use 驱动决策 + 50 步/15min 硬限 + 重复调用检测
- [x] **D2**：`checkpoint.py` — 每 5 步 DDB 写入 + 24h TTL + 启动恢复
- [x] **D3**：tests — Supervisor 终止边界

### 阶段 E — Worker main.py
- [x] **E1**：`agentcore_registration.py` — DDB conditional put + AgentCore SDK 占位
- [x] **E2**：`main.py` — SQS consumer + Supervisor dispatcher + SFN callback
- [x] **E3**：SIGTERM/SIGINT stop_event 优雅关闭

### 阶段 F — Lambda load-novel-metadata
- [x] **F1**：`handler.py` — DDB 分页 Query + title 截断 MAX_TITLES=500
- [x] **F2**：tests — moto mock DDB 验证分页与返回结构

### 阶段 G — CDK 扩展
- [x] **G1**：`shared_constructs/u3_extensions.py` — 5 helper（extend_data / identity / messaging / observability / agentcore）
- [x] **G2**：`infra/cdk/asl/analysis_workflow.json` — 完整 ASL（UpdateRunning → LoadMetadata Lambda → InvokeSupervisor SQS → PublishAnalyzed EventBridge → JobSucceeded/Failed）
- [x] **G3**：`U3_INTEGRATION.md` — 如何在 U1 Stack __init__ 调用 helper

### Phase H — Docker + 集成测试
- [x] **H1**：`services/worker-analysis/Dockerfile` — python:3.12-slim + libxml2/libxslt
- [x] **H2**：workspace 成员自动覆盖（根 pyproject.toml 已含 `services/*`）
- [x] **H3**：`tests/integration/test_u3_analysis.py` — 3 步 canned decision 端到端验证

---

## 4. 估算

| Phase | 文件数 | LOC |
|---|---|---|
| A MemoryFacade 实现 | 5 | 900 |
| B Prompts | 6 | 400（Markdown 文字）|
| C Sub-agents | 9 | 1200 |
| D Supervisor + Checkpoint | 3 | 500 |
| E Worker main | 3 | 400 |
| F Lambda | 3 | 200 |
| G CDK 扩展 | 3 | 500 |
| H Docker + 测试 | 3 | 300 |
| **合计** | **~35 文件** | **~4400 LOC** |

分 2 轮交付：
- **轮 1**：Phase A + B + C（20 文件 / ~2500 LOC，MemoryFacade + Prompts + 6 sub-agent 核心）
- **轮 2**：Phase D + E + F + G + H（15 文件 / ~1900 LOC，Supervisor + Worker + Lambda + CDK + 测试）

---

## 5. 关键假设

- Strands Agents SDK 可从 PyPI 安装（最新稳定版）
- AgentCore Memory / Runtime Python SDK 未完全稳定 → 关键调用点用接口抽象 + 占位实现
- Bedrock Converse API 的 Tool Use 功能在 us-east-1 稳定可用
- Neptune Serverless 在 us-east-1 的 openCypher endpoint 路径格式稳定

---

## 6. 用户审批

请确认：
1. 代码路径：`services/worker-analysis/` + `lambdas/load-novel-metadata/` + `infra/cdk/shared_constructs/u3_extensions.py`
2. 分 2 轮交付（20 → 15 文件）
3. AgentCore SDK 未就绪处接受 `NotImplementedError` 占位
