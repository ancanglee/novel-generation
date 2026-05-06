# U2 Ingestion Service — 代码生成计划（Code Generation Plan）

**Unit**：U2 Ingestion Service
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-27

---

## 1. 代码放置（新建项目 续建）

U1 已建 monorepo 骨架。U2 只新增/扩展以下路径（不污染 `aidlc-docs/`）：

```
novel-generation/
├── services/
│   ├── api/                           ← 新增：FastAPI /api/v1/novels/* 路由
│   │   ├── pyproject.toml
│   │   ├── src/novelgen_api/
│   │   │   ├── main.py                (FastAPI app)
│   │   │   ├── routers/novels.py      (upload / download / crawl / list / get / delete)
│   │   │   ├── services/ingestion_service.py
│   │   │   ├── errors.py              (exception handlers)
│   │   │   └── deps.py                (Principal, adapters wiring)
│   │   └── tests/
│   ├── worker-ingestion/              ← 新增：SQS consumer
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/worker_ingestion/
│   │   │   ├── main.py                (asyncio loop + Semaphore 5)
│   │   │   ├── parsers/               (txt/md/epub/pdf/docx/html)
│   │   │   ├── fetchers/              (tier1_http, tier2_browser)
│   │   │   ├── chapter_splitter.py    (heuristic + LLM fallback)
│   │   │   ├── search/                (gutenberg, ctext, wikisource, baidu, bing)
│   │   │   ├── robots.py              (robots.txt cache)
│   │   │   ├── url_normalizer.py      (crawl-cache key)
│   │   │   ├── browser_pool.py        (DDB counter CAS)
│   │   │   └── pipeline.py            (orchestrate: fetch → parse → split → write)
│   │   └── tests/
├── packages/
│   └── agentcore-browser-pool/        ← 新增：Browser slot CAS 共享库
│       ├── pyproject.toml
│       ├── src/novelgen_browser_pool/
│       │   ├── __init__.py
│       │   └── pool.py
│       └── tests/
├── infra/cdk/stacks/                  ← 修改：5 个 Stack 扩展
│   ├── data_stack.py                  (+ S3 Lifecycle, + SSM, + Counter init)
│   ├── identity_stack.py              (+ worker-ingestion Role)
│   ├── messaging_stack.py             (+ ingestion queue, + NovelIngestedRule, + IngestionSM ASL)
│   ├── compute_stack.py               (+ worker-ingestion Service + ECR)
│   └── observability_stack.py         (+ 5 Alarms)
└── tests/
    └── integration/
        └── test_u2_ingestion.py       ← 新增：采集端到端 smoke
```

---

## 2. 覆盖 Stories

- **Primary**：US-02-01（上传）/ US-02-02（公版书搜索下载）/ US-02-03（URL 抓取）/ US-02-04（列表）
- **Collab**：US-07-01（导出组装的底层文件读取）

---

## 3. 生成步骤

### 阶段 A — Browser Pool 共享库
- [x] **A1**：`packages/agentcore-browser-pool/`
  - `pool.py` — `BrowserPool.acquire()` / `release()` / `cleanup_expired()` 基于 DDB CAS
  - 测试：moto mock DDB，模拟 10 并发抢 slot、失败退避、僵尸清理

### 阶段 B — Worker 辅助模块
- [x] **B1**：`url_normalizer.py` — tracking 参数白名单 + sha256 cache key
- [x] **B2**：`robots.py` — urllib.robotparser + TTLCache 24h
- [x] **B3**：`chapter_splitter.py` — 启发式 4 pattern + LLM 回退
- [x] **B4**：tests 覆盖以上

### 阶段 C — Parsers
- [x] **C1**：`parsers/base.py` — `DocumentParser` Protocol + 注册表
- [x] **C2**：6 个 parser（txt/markdown/epub/pdf/docx/html）
- [x] **C3**：tests（txt/md 冒烟，二进制格式留在 Round 2 添加 fixtures）

### 阶段 D — Fetchers（两级抓取）
- [x] **D1**：`fetchers/tier1_http.py` — httpx + 降级判定
- [x] **D2**：`fetchers/tier2_browser.py` — AgentCore Browser 封装 + BrowserPool 集成（SDK 占位）
- [x] **D3**：`fetchers/orchestrator.py` — Worker 主决策层（NFR §3.1）
- [x] **D4**：tests：mock 覆盖 robots 硬拒 / Tier1 成功 / 403 降级 / JS-only 降级

### 阶段 E — Search Sources
- [x] **E1**：`search/base.py` — `SearchSource` Protocol
- [x] **E2**：5 个 source（gutenberg/ctext/wikisource/baidu/bing）
- [x] **E3**：`search/aggregator.py` — 分组并行 + 两阶段回调
- [x] **E4**：tests：两阶段顺序 + 归一化去重

### 阶段 F — Pipeline + Worker Loop
- [x] **F1**：`pipeline.py` — fetch / parse / split / persist 编排
- [x] **F2**：`main.py` — asyncio loop + Semaphore(5) + SFN 回调
- [x] **F3**：graceful shutdown（SIGTERM → stop_event）
- [x] **F4**：tests：pipeline upload 路径端到端

### 阶段 G — API Service
- [x] **G1**：`services/api/src/novelgen_api/main.py` — FastAPI app + lifespan 启动
- [x] **G2**：`routers/novels.py` — 端点：
  - `POST /api/v1/novels/upload`（multipart, Idempotency-Key）
  - `POST /api/v1/novels/download`（title + engines）
  - `POST /api/v1/novels/download/confirm`（选定结果）
  - `POST /api/v1/novels/crawl`（URL）
  - `GET /api/v1/novels`（列表）
  - `GET /api/v1/novels/{id}`
  - `DELETE /api/v1/novels/{id}`
- [x] **G3**：`services/ingestion_service.py` — SFN + Novel 表 + 幂等 + 标题去重
- [x] **G4**：`errors.py` — 统一异常 handler
- [x] **G5**：tests：FastAPI TestClient (health / list / unsupported MIME)

### Phase H — CDK Stack 扩展
- [x] **H1-H5**：`shared_constructs/u2_extensions.py` 集中封装 5 个 helper（extend_data_stack / extend_messaging_stack / extend_identity_stack / extend_compute_stack / extend_observability_stack）+ `U2_INTEGRATION.md` 指导如何在现有 U1 Stack __init__ 中调用。保持 U2 diff 可单独 review。完整 IngestionStateMachine ASL 保存在 infrastructure-design.md §3，部署时用 DefinitionBody 加载。

### Phase I — Docker + CI
- [x] **I1**：`services/worker-ingestion/Dockerfile`
- [x] **I2**：`services/api/Dockerfile`
- [x] **I3**：根 `pyproject.toml` 添加 `packages/agentcore-browser-pool` 到 workspace

### Phase J — 集成测试
- [x] **J1**：`tests/integration/test_u2_ingestion.py` — upload 切分 + robots 硬拒 + cache_key 语义

---

## 4. 估算

| Phase | 文件数 | LOC |
|---|---|---|
| A Browser Pool | 4 | 300 |
| B Worker helpers | 7 | 600 |
| C Parsers | 10 | 700 |
| D Fetchers | 5 | 500 |
| E Search | 8 | 700 |
| F Pipeline+Worker | 5 | 600 |
| G API | 8 | 900 |
| H CDK 扩展 | 5 (修改) | 400 |
| I Docker | 3 | 60 |
| J Integration tests | 1 | 200 |
| **合计** | **~56 文件** | **~4960 LOC** |

分 2 轮交付：
- **轮 1**：Phase A + B + C + D（26 文件 / ~2100 LOC，核心抓取 + 解析能力）
- **轮 2**：Phase E + F + G + H + I + J（30 文件 / ~2860 LOC，编排 + API + CDK 接入 + 测试）

---

## 5. 关键依赖与假设

- U1 共享库已可用（`novelgen-types` / `novelgen-auth` / `novelgen-storage` / `novelgen-obs`）
- AgentCore Browser Python SDK 暂未完全公开 → 用接口抽象 + TODO 标记，实际调用处保留 `NotImplementedError` 占位
- Bedrock Claude Haiku 4.5 在 us-east-1 可用
- 测试使用 moto 5.x mock AWS，sample 文件放 `tests/fixtures/`

---

## 6. 用户审批

请确认：
1. **代码路径**：新 `services/api`、`services/worker-ingestion`、`packages/agentcore-browser-pool` + 修改 5 个 CDK Stack
2. **交付策略**：分 2 轮（~26 文件 → ~30 文件）
3. **AgentCore Browser 占位**：实际 SDK 调用处用 `NotImplementedError` 标记，U3 Agent 开发时再替换
