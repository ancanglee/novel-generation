# U5 部署架构（Deployment Architecture）

**Unit**：U5 Critic & Consistency
**阶段**：Infrastructure Design
**日期**：2026-04-28

本文件包含 3 张架构图（I4=B 决策）：
1. **U5 数据流图** —— Critic / Consistency 两条数据路径
2. **U5 增量部署图** —— U5 相对 U1/U2/U3/U4 的资源增量（高亮）
3. **Critic + Consistency + Rewrite 时序图** —— 三个关键业务时序

---

## 1. U5 数据流图

```
                    ┌──────────────────────────────────────────┐
                    │         U4 ChapterAgent (SFN)            │
                    │                                          │
                    │  Draft → Self-Critique (Layer-1) →       │
                    │  Emit events on chapter complete         │
                    └──┬─────────────────┬─────────────────────┘
                       │ chapter.completed│ consistency.trigger
                       │ (always)         │ (when idx % N == 0)
                       ▼                  ▼
              ┌────────────────┐  ┌──────────────────────┐
              │ EventBridge    │  │ EventBridge          │
              │ Rule           │  │ Rule (U4 retrofit)   │
              │ chapter→critic │  │ consistency-trigger  │
              └───────┬────────┘  └──────────┬───────────┘
                      ▼                      ▼
              ┌─────────────┐        ┌───────────────────┐
              │ critic-queue│        │ consistency-queue │
              │ (U1 SQS)    │        │ (U1 SQS)          │
              └──────┬──────┘        └──────────┬────────┘
                     ▼                          ▼
        ┌──────────────────────┐    ┌──────────────────────────┐
        │ worker-critic        │    │ worker-consistency       │
        │ (U1 ECS, Opus 4.7)   │    │ (U1 ECS, Sonnet 4.6)     │
        │                      │    │                          │
        │ build_input():       │    │ scan_window(from,to):    │
        │  - chapter text (S3) │    │  - 10 chapters (S3)      │
        │  - layer1 critique   │    │  - Memory facts top_k=30 │
        │  - 5 recent summary  │    │  - get_character snap    │
        │    (Outline.items)   │    │    (U3 MemoryFacade)     │
        │  - style_vector      │    │                          │
        │                      │    │  produce:                │
        │ produce:             │    │  - ConsistencyReport     │
        │  - CritiqueReport    │    │  - N × ConflictItems     │
        │  - Layer-2 issues    │    │  (rewrite_attempts=0)    │
        └──────────┬───────────┘    └────────────┬─────────────┘
                   ▼                             ▼
           ┌──────────────────────────────────────────┐
           │     DynamoDB  novelgen_tenancy           │
           │                                          │
           │   PK = TEAM#{team_id}                    │
           │   SK patterns:                           │
           │     CRITIQUE#{gid}#{idx:05d}             │
           │     CONSISTENCY#{gid}#{scan_to:05d}      │
           │     CONFLICT#{gid}#{conflict_id}         │
           │     GEN_SCAN#{gid}  (last_scan_to)       │
           └─────────┬────────────────────────────────┘
                     ▼
           ┌──────────────────────┐
           │ EventBridge          │
           │ critic.report_ready  │
           │ consistency.report_  │
           │   ready              │
           └─────────┬────────────┘
                     ▼
              ┌─────────────────┐
              │ api-service     │  ← consumed by per-replica SQS (U4)
              │ SSE to browser  │
              └─────────────────┘

User actions (UI) ───▶ api-service:
   GET  /critique              ─▶ DDB read CRITIQUE#
   GET  /consistency-reports   ─▶ DDB read CONSISTENCY#
   POST /conflicts/{id}/ignore ─▶ DDB update CONFLICT# (status=ignored)
   POST /conflicts/{id}/rewrite─▶ DDB update (rewrite_attempts++, frozen?)
                                  ─▶ U4  POST /rewrite  (internal HTTP)
```

---

## 2. U5 增量部署图（对比 U1/U2/U3/U4）

```
                    ┌────────────────────────────────────────────────┐
                    │  AWS Account (Region = ap-northeast-1)         │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │  VPC (U1)                                │  │
                    │  │                                          │  │
                    │  │  ┌─────────────┐  ┌──────────────────┐   │  │
                    │  │  │ api-service │  │ ECS Cluster      │   │  │
                    │  │  │ ECS Service │  │                  │   │  │
                    │  │  │ (U1 + U4)   │  │  worker-critic   │   │  │
                    │  │  │  ★ U5 adds  │  │  (U1, img★ U5)   │   │  │
                    │  │  │   4 routes  │  │                  │   │  │
                    │  │  │   +4 env var│  │  worker-consist  │   │  │
                    │  │  └─────────────┘  │  (U1, img★ U5)   │   │  │
                    │  │                   │                  │   │  │
                    │  │                   │  worker-moder    │   │  │
                    │  │                   │  (U1, desired=0) │   │  │
                    │  │                   │                  │   │  │
                    │  │                   │  worker-ingest,  │   │  │
                    │  │                   │  worker-analyze, │   │  │
                    │  │                   │  (U2, U3, …)     │   │  │
                    │  │                   └──────────────────┘   │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ EventBridge Bus: novelgen-default-bus    │  │
                    │  │  ┌─────────────────────────────────────┐ │  │
                    │  │  │ Rule chapter-completed-to-critic    │ │  │
                    │  │  │ (U1 pre-built)                      │ │  │
                    │  │  └─────────────────────────────────────┘ │  │
                    │  │  ┌─────────────────────────────────────┐ │  │
                    │  │  │ Rule consistency-trigger-to-queue   │ │  │
                    │  │  │ ★ NEW (U5, retrofit into U4 ext)    │ │  │
                    │  │  └─────────────────────────────────────┘ │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ SQS  critic-queue + DLQ         (U1)     │  │
                    │  │ SQS  consistency-queue + DLQ    (U1)     │  │
                    │  │ SQS  moderation-queue + DLQ     (U1, V2) │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ DynamoDB novelgen_tenancy   (U1)         │  │
                    │  │   ★ U5 adds 4 SK patterns (no schema     │  │
                    │  │     change):                             │  │
                    │  │       CRITIQUE#, CONSISTENCY#,           │  │
                    │  │       CONFLICT#, GEN_SCAN#               │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ SSM Parameter Store                      │  │
                    │  │   ★ NEW 3 params (U5):                   │  │
                    │  │     /novelgen/{env}/config/              │  │
                    │  │         consistency-interval = 10        │  │
                    │  │         conflict-rewrite-max-attempts=3  │  │
                    │  │         critic-layer2-recent-summary=5   │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ CloudWatch                               │  │
                    │  │   ★ NEW 4 alarms (U5):                   │  │
                    │  │     U5CriticDurationHigh (P95 > 60s)     │  │
                    │  │     U5ConsistencyDurationHigh (P95>240s) │  │
                    │  │     U5CriticFailureRateHigh (> 5%)       │  │
                    │  │     U5ConflictLoopDetected (> 0)         │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ AgentCore Memory (U3)   ─┐               │  │
                    │  │ Neptune Serverless (U3) ─┼── U5 reads    │  │
                    │  │ OpenSearch Serverless(U3)┘   via U3      │  │
                    │  │                              MemoryFacade│  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    │  ┌──────────────────────────────────────────┐  │
                    │  │ Bedrock                                  │  │
                    │  │   Claude Opus 4.7 (Critic, U5)           │  │
                    │  │   Claude Sonnet 4.6 (Consistency, U5)    │  │
                    │  └──────────────────────────────────────────┘  │
                    │                                                │
                    └────────────────────────────────────────────────┘

Legend:  ★ = U5 net-new or modified;  otherwise inherited from U1/U2/U3/U4.
```

---

## 3. 三个关键业务时序图

### 3.1 Critic 时序（每章）

```
ChapterAgent          EventBridge         critic-queue       worker-critic         Bedrock          DDB         EventBridge
  (U4 SFN)             Rule                  (SQS)           (ECS, U1)            (Opus 4.7)
     │                  │                      │                  │                     │              │              │
     │── chapter done ──▶                      │                  │                     │              │              │
     │ PutEvents         │                      │                  │                     │              │              │
     │ (chapter.         │── match ────────────▶                  │                     │              │              │
     │  completed)       │  SendMessage          │── ReceiveMsg ──▶│                    │              │              │
     │                  │                      │                  │── load outline + ──▶│              │              │
     │                  │                      │                  │   Layer-1 critique  │              │              │
     │                  │                      │                  │   + 5 recent summary│              │              │
     │                  │                      │                  │                     │              │              │
     │                  │                      │                  │── Converse call ───▶│              │              │
     │                  │                      │                  │  (~10k input tok)   │              │              │
     │                  │                      │                  │◀── Layer-2 JSON ────│              │              │
     │                  │                      │                  │                     │              │              │
     │                  │                      │                  │── PutItem ─────────────────────────▶              │
     │                  │                      │                  │  (SK=CRITIQUE#gid#idx)                            │
     │                  │                      │                  │                                                  │
     │                  │                      │                  │── PutEvents critic.report_ready ─────────────────▶
     │                  │                      │                  │                                                  │
     │                  │                      │◀── DeleteMessage ─│                                                  │
     │                  │                      │                  │                                                  │
  SLA: P95 < 60s end-to-end  (N3=A 失败不阻断 Chapter 状态)
```

### 3.2 Consistency 时序（每 10 章）

```
ChapterAgent     EventBridge       consistency-queue   worker-consistency   MemoryFacade    Bedrock      DDB
 (U4 SFN)         Rule (U5)          (SQS)             (ECS, U1)           (U3)           (Sonnet 4.6)
    │               │                   │                    │                 │              │            │
    │  idx % 10 ==0?                    │                    │                 │              │            │
    │── PutEvents ──▶                    │                    │                 │              │            │
    │ consistency.   │── match ──────────▶                    │                 │              │            │
    │ trigger        │ SendMessage        │── Receive ───────▶│                 │              │            │
    │ {scan_to=idx}  │                   │                    │                 │              │            │
    │               │                   │                    │── read GEN_SCAN#──────────────────────────▶│
    │               │                   │                    │   get last_scan_to                         │
    │               │                   │                    │◀────────────────────────────────────────── │
    │               │                   │                    │                 │              │            │
    │               │                   │                    │── recall(team,gid,              │            │
    │               │                   │                    │    "ch scan_from-to", k=30) ─▶│              │            │
    │               │                   │                    │◀── facts ───────────────────│              │            │
    │               │                   │                    │                 │              │            │
    │               │                   │                    │── get_character(char_id,       │            │
    │               │                   │                    │    at_chapter=scan_to) ─────▶│              │            │
    │               │                   │                    │◀── snapshots ──────────────│              │            │
    │               │                   │                    │                 │              │            │
    │               │                   │                    │── S3 GetObject 10 chapters ──────────────────┐          │
    │               │                   │                    │◀─────────────────────────────────────────────┘          │
    │               │                   │                    │                 │              │            │
    │               │                   │                    │── Converse ──────────────────▶│            │
    │               │                   │                    │◀── ConflictItems JSON ───────│            │
    │               │                   │                    │                 │              │            │
    │               │                   │                    │── PutItem ────────────────────────────────▶│
    │               │                   │                    │   SK=CONSISTENCY#gid#scan_to               │
    │               │                   │                    │── TransactWriteItems ────────────────────▶│
    │               │                   │                    │   N × CONFLICT# (rewrite_attempts=0)       │
    │               │                   │                    │── UpdateItem (conditional) ──────────────▶│
    │               │                   │                    │   GEN_SCAN#  if scan_to > last_scan_to     │
    │               │                   │                    │   (保证串行)                                │
    │               │                   │                    │                                             │
 SLA: P95 < 4 min  (N2=B)；Memory 不可用时降级 text-diff，report.memory_unavailable=true (N3 同 Critic)
```

### 3.3 Rewrite 循环保护时序（用户点 Rewrite）

```
Browser            api-service              DDB              U4 api-service       ChapterAgent (SFN)
                   (U1+U4+U5)              (CONFLICT#)        /rewrite            (U4)
   │                  │                      │                  │                     │
   │── POST /conflicts/{cid}/rewrite ──────▶│                  │                     │
   │                  │                      │                  │                     │
   │                  │── GetItem CONFLICT# ─▶                  │                     │
   │                  │◀── item (frozen?     │                  │                     │
   │                  │     attempts=X)      │                  │                     │
   │                  │                      │                  │                     │
   │             ┌────┴─────┐                │                  │                     │
   │             │ frozen?  │                │                  │                     │
   │             └────┬─────┘                │                  │                     │
   │                  │ yes                  │                  │                     │
   │◀─ 409 "多次尝试未解决" ────────────────│                  │                     │
   │                  │                      │                  │                     │
   │             no   │                      │                  │                     │
   │                  │                      │                  │                     │
   │                  │── UpdateItem ──────▶│                  │                     │
   │                  │   SET attempts+=1    │                  │                     │
   │                  │   SET frozen=        │                  │                     │
   │                  │     (attempts>=3)    │                  │                     │
   │                  │◀── updated item ────│                  │                     │
   │                  │                      │                  │                     │
   │                  │ if attempts>=3:      │                  │                     │
   │                  │   emit metric        │                  │                     │
   │                  │   ConflictLoopDetected (→ alarm)        │                     │
   │                  │                      │                  │                     │
   │                  │── POST /generations/{gid}/chapters/{n}/rewrite ────────────────▶
   │                  │   instruction = conflict.summary        │                     │
   │                  │◀────────────────────────────── 202 Accepted + job_id ─────────│
   │                  │                      │                  │                     │
   │◀─ 202 Accepted + {job_id, conflict_id, attempts, frozen} ─│                     │
   │                  │                      │                  │                     │
                                                                                       ChapterAgent rewrites
                                                                                       → new chapter.completed
                                                                                       → new Critic + Consistency
```

---

## 4. 网络与安全

- 所有 ECS Task 在 U1 VPC 私有子网内，通过 NAT / Gateway Endpoints 访问 AWS 服务（Bedrock / DDB / S3 / EventBridge / SSM / SQS）
- Bedrock 使用 **Gateway Endpoint**（U1 已配置），减少 NAT 流量
- DDB / S3 / SSM 使用 **Gateway Endpoints**（U1 已配置）
- EventBridge / SQS 使用 **Interface Endpoints**（U1 已配置）
- `api-service` 依旧位于 public ALB 后，走 Cognito JWT 鉴权（U1）

---

## 5. 部署风险与回滚

| 风险 | 缓解 |
|---|---|
| U4 retrofit 引入的 Rule 错误 → ChapterAgent PutEvents 被 DLQ | CloudWatch 告警 `event-bus-dlq-depth`（U1 预建），回滚只需在 CDK 中移除该 Rule |
| worker-critic 镜像 Bug → 产生大量 minimal report | N3=A 确保业务继续；监控 `CriticFailureRateHigh` 告警触发 → ECR rollback 到前版 |
| SSM 参数误配为 0 或极大值 → 所有章节都触发 Consistency / 永不触发 | CDK 默认值保底；监控 `ConsistencyDurationMs` 与 `ConsistencyTotalCount` 异常 |
| DDB hot-partition（同 generation 密集写 CONFLICT#） | `novelgen_tenancy` PK=`TEAM#{team_id}` 天然分散；单 team 超量走 U1 限流 |

回滚步骤：
1. ECR rollback 镜像到前一版 tag
2. `cdk deploy` 回滚 `u5_extensions` / `u4_extensions retrofit`
3. SSM 参数手动改回原值（或交由 `cdk deploy` 重置）

---

## 6. 架构图文本导出说明

本文件的三张架构图使用 ASCII 盒形图（对齐 `common/ascii-diagram-standards.md`），所有资源名均与 `infrastructure-design.md` 及 `logical-components.md` 保持一致。PDF 导出时建议使用 monospace 字体（如 Menlo、JetBrains Mono）。
