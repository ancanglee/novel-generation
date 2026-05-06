# U5 Critic & Consistency — 代码生成计划（Code Generation Plan）

**Unit**：U5 Critic & Consistency
**阶段**：Code Generation (Part 1 — Planning)
**日期**：2026-04-28

---

## 1. 代码放置

```
novel-generation/
├── services/
│   ├── worker-critic/                    ← 新增（复用 novelgen-base 镜像层）
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/worker_critic/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                   (SQS 消费 critic-queue + SIGTERM)
│   │   │   ├── agent.py                  (CriticAgent Opus 4.7 + Tool Use)
│   │   │   ├── context.py                (CriticContext 构造：chapter + layer1 + 5 summary + style)
│   │   │   ├── ssm_config.py             (SsmConfigCache 60s refresh)
│   │   │   ├── metrics.py                (CriticDurationMs / FailureCount / Score 分桶)
│   │   │   ├── event_publisher.py        (critic.report_ready)
│   │   │   └── prompts/
│   │   │       ├── __init__.py
│   │   │       └── critic_layer2.md
│   │   └── tests/
│   │       ├── test_context.py
│   │       ├── test_agent.py
│   │       └── test_metrics.py
│   │
│   ├── worker-consistency/               ← 新增
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/worker_consistency/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                   (SQS 消费 consistency-queue)
│   │   │   ├── agent.py                  (ConsistencyAgent Sonnet 4.6 + Tool Use)
│   │   │   ├── context.py                (ConsistencyContext：scan_from/to + facts + char snapshots)
│   │   │   ├── scan_cursor.py            (GEN_SCAN# conditional update 串行保证)
│   │   │   ├── ssm_config.py             (共享，复制自 worker-critic 或 shared_libs)
│   │   │   ├── metrics.py
│   │   │   ├── event_publisher.py
│   │   │   └── prompts/
│   │   │       ├── __init__.py
│   │   │       └── consistency.md
│   │   └── tests/
│   │       ├── test_context.py
│   │       ├── test_scan_cursor.py
│   │       └── test_agent.py
│   │
│   └── api/                               ← 扩展：追加 3 个 router
│       └── src/novelgen_api/
│           ├── routers/
│           │   ├── critique.py           (新增：GET /generations/{gid}/chapters/{n}/critique)
│           │   ├── consistency.py        (新增：GET /generations/{gid}/consistency-reports)
│           │   └── conflicts.py          (新增：POST /conflicts/{cid}/ignore + /rewrite)
│           ├── services/
│           │   ├── critique_repo.py      (DDB 读 CRITIQUE#)
│           │   ├── consistency_repo.py   (DDB 读 CONSISTENCY#)
│           │   └── conflict_repo.py      (DDB CRUD CONFLICT# + rewrite_attempts 递增 + frozen 判断)
│           └── main.py                   (include_router)
│
├── shared_libs/                           ← 新增（如不存在）
│   └── novelgen_domain/
│       └── critique.py                   (Pydantic 模型：CritiqueReport/Issue/CrossChapterConcern/
│                                          ConsistencyReport/ConflictItem 6 种类型)
│
├── infra/cdk/
│   ├── shared_constructs/
│   │   ├── u4_extensions.py              ← 修改（retrofit：追加 ConsistencyTriggerRule）
│   │   └── u5_extensions.py              ← 新增
│   └── stacks/
│       └── u1_platform_stack.py          ← 修改（__init__ 末尾调用 apply_u5_extensions）
│
└── tests/
    └── integration/
        └── test_u5_critic.py             ← 新增（DDB 读写 + ConflictItem 冻结逻辑）
```

---

## 2. 覆盖 Stories

- **Primary**:
  - US-07-01 Critic Layer-2 评审（Opus 4.7）
  - US-07-02 Critic 失败降级（写 minimal report，不阻断 Chapter 状态）
  - US-08-01 Consistency 全局扫描（每 10 章）
  - US-08-02 ConflictItem 呈现（6 种类型）
  - US-08-03 用户 Ignore / Rewrite
  - US-08-04 重写循环保护（3 次 frozen）
- **NFR**:
  - NFR-U5-1（Critic P95 < 60s）
  - NFR-U5-2（Consistency P95 < 4min）
  - NFR-U5-3（失败不阻断）
- **Not implemented（F4=D 决策）**: US-09-01 / US-09-02 Moderation（V2）

---

## 3. 生成步骤

### 阶段 A — Domain 模型
- [x] **A1**：`packages/shared-types-py/src/novelgen_types/critique.py` — Pydantic v2 模型（沿用现网 `novelgen_types` 包，非新建 `shared_libs`）
  - `CritiqueReport` (layer1_confirmed, layer1_overridden, layer2_issues, chapter_idx, score, minimal)
  - `Issue` (Severity / IssueDimension enum + evidence_excerpt)
  - `CrossChapterConcern` (chapter_refs, message)
  - `ConsistencyReport` (scan_from, scan_to, conflict_ids, memory_unavailable, minimal)
  - `ConflictItem` (conflict_id, ConflictType × 6, chapter_refs, summary, evidence, rewrite_attempts, frozen, user_action)
  - 6 种 ConflictType Enum
- [x] **A2**：`packages/shared-types-py/tests/test_critique.py` — schema 往返序列化 + enum 边界 + score 范围 + extra=forbid

### 阶段 B — worker-critic
- [x] **B1**：`ssm_config.py` — `SsmConfigCache(prefix, refresh_interval=60)` + `get_int/get_str` 带并发锁
- [x] **B2**：`context.py` — `pick_recent_summaries` + `render_prompt`（chapter text + layer1 + 5 summary + style_vector）
- [x] **B3**：`prompts/critic_layer2.md` — Layer-2 prompt
- [x] **B4**：`agent.py` — `CriticAgent` Bedrock Converse + Tool Use（emit_critique_report schema），tenacity 指数退避 3 次 + `minimal_failure_report`
- [x] **B5**：`event_publisher.py` — `publish_report_ready`
- [x] **B6**：`metrics.py` — `emit_duration_ms / emit_failure / emit_total / emit_score_bucket`
- [x] **B7**：`main.py` — SQS long-poll 消费 critic-queue → context → agent.run() → 写 DDB CRITIQUE# → 发事件；失败降级为 minimal report (N3=A)
- [x] **B8**：`Dockerfile` + `pyproject.toml`（FROM python:3.12-slim + shared packages 挂载）
- [x] **B9**：tests — `test_context.py` / `test_agent.py` / `test_metrics.py`

### 阶段 C — worker-consistency
- [x] **C1**：`context.py` — `ConsistencyContext` + `render_prompt`（scan_from/to + facts + snapshots + chapters_text 排序拼装）
- [x] **C2**：`scan_cursor.py` — `advance_scan` / `get_last_scan_to` DDB conditional update `last_scan_to < :new` 保证串行
- [x] **C3**：`prompts/consistency.md` — 6 种 ConflictType + evidence 格式约束 + memory_unavailable 降级说明
- [x] **C4**：`agent.py` — `ConsistencyAgent` Sonnet 4.6 + Tool Use（emit_consistency_report schema）+ `_assemble`（raw → ConsistencyReport + ConflictItem[]）+ `minimal_failure_report`
- [x] **C5**：`main.py` — SQS 消费 consistency-queue → advance_scan → 读 chapters + facts + char snapshots → agent → 分批 TransactWriteItems（≤20/批）
- [x] **C6**：`event_publisher.py` — `publish_report_ready`（conflict_count + memory_unavailable）
- [x] **C7**：`metrics.py` — ConsistencyDurationMs / TotalCount / FailureCount / ConflictCount{Type} / MemoryUnavailable
- [x] **C8**：`Dockerfile` + `pyproject.toml`
- [x] **C9**：tests — `test_context.py` / `test_agent.py` / `test_scan_cursor.py`（moto 模拟 DDB 并发 advance + 乱序拒绝 + 单调推进）

### 阶段 D — api-service 扩展
- [x] **D1**：`services/critique_repo.py` — `get_critique(team_id, gid, idx)` 读 DDB CRITIQUE#
- [x] **D2**：`services/consistency_repo.py` — `list_reports(team_id, gid, since_chapter)` query_by_sk_prefix + since filter + sort by scan_to
- [x] **D3**：`services/conflict_repo.py` — `find/find_by_id/ignore/request_rewrite`；rewrite 用 DDB `UpdateItem` + conditional `rewrite_attempts = :cur AND frozen = :fcur`（乐观锁防并发）；attempts+1>=max 时 SET frozen=true + 发 `ConflictLoopDetected` EMF
- [x] **D4**：`routers/critique.py` — 1 GET，鉴权 `PrincipalDep`
- [x] **D5**：`routers/consistency.py` — 1 GET（支持 since_chapter + limit）
- [x] **D6**：`routers/conflicts.py` — 2 POST；rewrite 调用内部 `POST /api/v1/generations/{gid}/chapters/{n}/rewrite`（httpx）；frozen→409；返回 `{conflict_id, rewrite_attempts, frozen, job_ref}`
- [x] **D7**：`main.py` — `include_router` 追加 3 个
- [x] **D8**：tests 合并到 F1（避免重复 DDB fixture）

### 阶段 E — CDK
- [x] **E1**：`shared_constructs/u4_extensions.py` retrofit — `extend_messaging_stack` 新增可选 `consistency_queue` 形参 + `U4ConsistencyTriggerRule`（event_pattern `detail_type=consistency.trigger` → consistency-queue）
- [x] **E2**：`shared_constructs/u5_extensions.py` — `apply_u5_extensions` + 3 子函数（`extend_data_stack` 3 SSM / `extend_identity_stack` Bedrock+EventBridge+SSM+AOSS+Neptune IAM / `extend_observability_stack` 4 CloudWatch Alarms 含 MathExpression 失败率 + SNS action）
- [x] **E3**：`U5_INTEGRATION.md` —— 详细 wiring 注释（与 U4_INTEGRATION.md 风格一致，per-stack 嵌入）；现网 stack 布局为 data/identity/messaging/observability 分离式，不存在单一 `u1_platform_stack.py`
- [x] **E4**：cdk diff 预期：3 SSM + 4 Alarms + 1 Rule + 2-3 IAM updates（记录在 U5_INTEGRATION.md §4）

### 阶段 F — 集成测试 + 文档
- [x] **F1**：`tests/integration/test_u5_critic.py` — 覆盖：
  - CritiqueReport schema 往返
  - 6 种 ConflictType 枚举稳定性
  - GEN_SCAN# 并发 serializer（moto DDB，10/10 重复→拒绝，10→20 推进→接受）
  - ConflictItem rewrite_attempts 3 次后 frozen 状态机
  - ConsistencyReport minimal + memory_unavailable 标志位
  - memory_unavailable 经 agent `_assemble` 正确透传
- [x] **F2**：`services/worker-critic/README.md` + `services/worker-consistency/README.md`
- [x] **F3**：现网已有 `novelgen_types` 包 README 文档，不额外新增

---

## 4. 估算

| Phase | 文件 | LOC |
|---|---|---|
| A Domain | 2 | 350 |
| B worker-critic | 10 | 900 |
| C worker-consistency | 10 | 1000 |
| D api 扩展 | 8 | 700 |
| E CDK | 3（2 新 1 改） | 450 |
| F 集成测试 + 文档 | 4 | 350 |
| **合计** | **~37 文件** | **~3750 LOC** |

### 交付轮次

- **轮 1（Agent 核心）**：Phase A + B + C，约 **22 文件 / ~2250 LOC**
  - Domain models + worker-critic + worker-consistency
- **轮 2（API + CDK + 测试）**：Phase D + E + F，约 **15 文件 / ~1500 LOC**
  - api-service 3 router + CDK retrofit + u5_extensions + 集成测试 + 文档

---

## 5. 假设

- `shared_libs/novelgen_domain/` 已由 U1/U2 建立（如无，Phase A 会顺带创建基础 `__init__.py`）
- `novelgen-base:{arch}` 基础镜像已由 U1 发布，critic / consistency 镜像 FROM 它
- U3 `MemoryFacade` 的 `recall()` / `get_character()` 接口契约稳定，worker-consistency 直接 pip install `novelgen_memory_facade`
- U4 `POST /rewrite` 端点稳定，conflicts router 用 httpx 内部调用 localhost:8000（同容器），或 ALB 内部 URL
- Bedrock Converse Tool Use 强制 JSON Schema 能正常约束 Opus 4.7 / Sonnet 4.6 输出
- 测试使用 moto + pytest-asyncio（与 U4 一致）

---

## 6. Out of Scope

- **Moderation Agent / ModerationReport / ModerationFlag**（F4=D 移除，V2 实现）
- `worker-moderation` ECS Service 保留 desired_count=0，代码侧不 touching
- Admin 审核队列 UI（US-09-01/02 未实现）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Opus 4.7 Tool Use schema 违约（罕见） | tenacity 重试 + 违约后降级为纯文本 prompt + 手工 regex 抽取（只作为 B7 fallback） |
| Consistency 扫描 10 章并发读 S3 超时 | asyncio.gather 并行 GetObject，单次 GetObject 超时 5s，总超时 30s |
| MemoryFacade 三层降级扰动 | 上游 U3 已提供 try-except，worker-consistency 只判断返回空集合 → 走降级分支 |
| DDB TransactWriteItems 超 25 项（CONSISTENCY 大量 ConflictItem） | 分批提交，每批 ≤ 20（预留 5 个其他写） |
| rewrite_attempts 竞态（用户连续点两次 Rewrite） | DDB 条件更新 `attribute_not_exists(frozen) OR frozen = :false`，自带并发保护 |

---

## 8. 用户审批

请确认：
1. 代码路径（新建 `services/worker-critic` + `services/worker-consistency`；扩展 `services/api` 追加 3 router；retrofit `u4_extensions.py`；新增 `u5_extensions.py`）
2. 分 2 轮交付（轮 1 Agent 核心、轮 2 API + CDK + 测试）
3. Moderation 全线不触碰（F4=D 决策坚持）
4. 是否需要保留 worker-moderation 占位容器代码（推荐：不需要，CDK 已保留 desired_count=0，代码侧保持空）

**请回复 `Approve Plan` 开始轮 1 生成。**
