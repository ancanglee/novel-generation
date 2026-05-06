# U4 Deployment Architecture — 架构图集

**Unit**：U4 Generation Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28
**Figures**: 3 张（U4 生成数据流 / SSE 事件流时序图 / U4 对 U1 增量图）

---

## 图 1：U4 生成数据流

### 1.1 Mermaid 源

```mermaid
flowchart TB
    U[Browser]
    BFF[NodeBff]
    API[ApiService<br/>含 SSE Relay]
    DDB[(DynamoDB<br/>Generation / Chapter / GEN_CONTEXT)]
    S3[(S3 novels<br/>outline.v / chapters/*.md)]
    SFN_O[Step Functions<br/>OutlineStateMachine]
    SFN_C[Step Functions<br/>ChapterStateMachine<br/>Choice Loop]
    L1[Lambda<br/>load-generation-context]
    SQS_G[[generation-queue]]
    SQS_R[[review-queue]]
    W[worker-generation<br/>ECS Fargate]
    OA[OutlineAgent<br/>Opus 4.7]
    CA[ChapterAgent<br/>Sonnet 4.7 Stream]
    SC[SelfCritique<br/>Sonnet 4.6]
    ORA[OutlineReview<br/>Sonnet 4.6]
    MF[U3 MemoryFacade<br/>hybrid_search / recall]
    BR[Bedrock Converse Stream]
    EB[EventBridge<br/>default bus]
    ARCH[(Archive<br/>7d retention)]
    SNS[SNS Topic<br/>novelgen-generation-events]
    SQS_SSE[[sse-relay-queue<br/>per-replica]]
    U5[U5 critic-queue<br/>moderation-queue]

    U -->|POST /generations /outline /start|BFF
    BFF-->API
    API-->DDB
    API-->|StartExecution|SFN_O
    API-->|StartExecution|SFN_C

    SFN_O-->SQS_G
    SFN_C-->L1
    L1-->MF
    L1-->DDB
    SFN_C-->SQS_G
    SFN_C-->SQS_R

    SQS_G-->W
    SQS_R-->W

    W-->OA
    W-->CA
    W-->SC
    W-->ORA
    OA-->BR
    CA-->BR
    SC-->BR
    ORA-->BR

    CA-->MF
    W-->S3
    W-->DDB

    CA-->|stream text_delta|EB
    W-->|chapter.completed|EB
    EB-->ARCH
    EB-->SNS
    SNS-->SQS_SSE
    SQS_SSE-->API
    API-->|SSE|BFF
    BFF-->U

    W-->|chapter.completed|U5

    W-->|CancelCheck TTLCache 8s|DDB

    style API fill:#BBDEFB,stroke:#1565C0,color:#000
    style W fill:#D1C4E9,stroke:#4527A0,color:#000
    style MF fill:#FFE0B2,stroke:#E65100,color:#000
    style EB fill:#C8E6C9,stroke:#2E7D32,color:#000
    linkStyle default stroke:#333,stroke-width:1.5px
```

### 1.2 ASCII 文本替代

```
Browser → NodeBff → ApiService
  ├─ POST /generations → DDB Generation(DRAFT)
  ├─ POST /outline → Step Functions OutlineStateMachine → generation-queue → worker-generation
  │                  → OutlineAgent (Opus 4.7) → S3 outline.v1.json → EventBridge outline.ready
  ├─ PUT /outline (edit) → DDB + review-queue → worker-generation → OutlineReviewAgent (异步建议)
  ├─ POST /outline/approve → DDB status=APPROVED
  ├─ POST /start → Step Functions ChapterStateMachine (Choice Loop + Cancel 检查)
  │     ├─ load-generation-context Lambda → MemoryFacade.hybrid_search → DDB GEN_CONTEXT (24h TTL)
  │     └─ 对 i=1..chapter_count 串行：
  │           GenerateChapter (SQS WAIT_FOR_TASK_TOKEN) → worker-generation
  │             → ChapterAgent (Sonnet 4.7 Converse Stream)
  │             → 每 token: 读 cancel_requested (TTLCache 8s) + 发 text_delta 到 EventBridge
  │             → 完成: 写 S3 chapters/{idx:05d}.md + DDB Chapter + SelfCritique 异步 + 发 chapter.completed
  │
  └─ GET /jobs/{id}/stream 或 /generations/{gid}/chapters/{n}/stream (SSE)
        → sse-starlette EventSourceResponse
        → 订阅 per-replica sse-relay-queue (SNS fan-out 来源)
        → 匹配 generation_id/chapter_idx filter → 转发给 Browser
        → 断线: 用 Last-Event-ID 从 EventBridge Archive 回放

Cancel:
  POST /jobs/{id}/cancel → DDB cancel_requested=true
  Worker 下一个 Bedrock token 回调读 TTLCache 过期 → 查 DDB → 为 true 关 stream → status=CANCELED
  ApiService SSE 发 canceled 事件

派发 U5:
  chapter.completed → EventBridge Rule → critic-queue + moderation-queue
```

---

## 图 2：SSE 事件流时序图（I4=B 新增）

### 2.1 Mermaid 源

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant BFF as NodeBff
    participant API as ApiService replica N
    participant SNS as SNS Topic
    participant SQ as sse-relay-queue (replica N's)
    participant ARCH as EventBridge Archive
    participant W as worker-generation
    participant BR as Bedrock Stream
    participant EB as EventBridge

    Note over API,SQ: Startup: replica creates its SQS + subscribes SNS
    API->>SQ: create queue novelgen-sse-relay-{replica_id}
    API->>SNS: subscribe queue to topic

    U->>BFF: GET /api/v1/jobs/{id}/stream
    BFF->>API: SSE pipe (sse-starlette EventSourceResponse)
    Note over U,API: SSE connection open

    opt Last-Event-ID present (reconnect)
      API->>ARCH: StartReplay events since id
      ARCH-->>API: replay events
      API-->>BFF: SSE replay events
      BFF-->>U: events
    end

    par Worker streaming
      W->>BR: converse_stream(chapter prompt)
      loop each token
        BR-->>W: text_delta
        W->>EB: PutEvents generation.chapter.streaming
        EB->>SNS: fan-out
        SNS->>SQ: deliver to replica N's queue
      end
    and ApiService consuming
      loop SQS poll
        SQ->>API: receive message
        Note right of API: Filter by generation_id / chapter_idx<br/>against active SSE connections
        alt matches an active connection
          API-->>BFF: SSE event
          BFF-->>U: text chunk
          API->>SQ: delete message
        else no active match
          API->>SQ: delete message (drop)
        end
      end
    end

    U->>API: disconnect / tab close
    API-->>API: close SSE connection

    Note over API,SNS: On shutdown: unsubscribe + delete queue
    API->>SNS: unsubscribe
    API->>SQ: delete queue
```

### 2.2 ASCII 文本替代

```
Startup (per ApiService replica):
  replica → SQS create queue novelgen-sse-relay-{replica_id}
  replica → SNS subscribe topic

Client connects:
  Browser → NodeBff → ApiService (sse-starlette EventSourceResponse)
  [optional] Last-Event-ID → EventBridge Archive StartReplay → replay to client

Live flow (parallel):
  Worker:   Bedrock converse_stream → per-token EventBridge PutEvents
            → SNS fan-out → every replica's SQS
  ApiService: SQS poll → filter by generation_id/chapter_idx matching active SSE conns
                       → SSE send or drop → delete from SQS

Disconnect:
  Client close → ApiService close SSE connection

Shutdown (per replica):
  SNS unsubscribe → delete SQS queue
```

---

## 图 3：U4 对 U1 增量图

### 3.1 Mermaid 源

```mermaid
flowchart LR
    subgraph U1["U1 Stack (U4 扩展点)"]
      Network[01-Network 不变]
      Data[02-Data<br/>+5 SSM + S3 Lifecycle]
      Identity[03-Identity<br/>worker-gen + api Role 扩展]
      Messaging[04-Messaging<br/>+review-queue + SNS<br/>+Archive + 2 状态机 + Lambda]
      Compute[05-Compute<br/>worker-gen + api 镜像更新]
      Edge[06-Edge 不变]
      Obs[07-Observability<br/>+3 Alarms]
    end

    subgraph U4New["U4 新增"]
      Q[review-queue + DLQ]
      SNS[SNS novelgen-generation-events]
      ARCH[EventBridge Archive 7d]
      L[load-generation-context Lambda]
      CSM[ChapterStateMachine<br/>Choice Loop]
      OSM[OutlineStateMachine]
      SSM[5 SSM Parameters]
      S3L[S3 NoncurrentVersion<br/>保留 10 + 30d 降冷]
      ALRM[3 Alarms]
    end

    Q-.->Messaging
    SNS-.->Messaging
    ARCH-.->Messaging
    L-.->Messaging
    CSM-.->Messaging
    OSM-.->Messaging
    SSM-.->Data
    S3L-.->Data
    ALRM-.->Obs

    style U1 fill:#BBDEFB,stroke:#1565C0,color:#000
    style U4New fill:#D1C4E9,stroke:#4527A0,color:#000
    linkStyle default stroke:#999,stroke-width:1.5px,stroke-dasharray: 3 3
```

### 3.2 ASCII 文本替代

```
U1 Stack                          U4 新增
─────────────                    ─────────────
01-Network                       (不变)
02-Data                  ←────   5 SSM Parameters
                         ←────   S3 Lifecycle NoncurrentVersionExpiration (保留 10 + 30d 降冷)
03-Identity              ←────   worker-generation Role 扩展（aoss/neptune-db/events）
                         ←────   ApiService Role 扩展（sns:Subscribe/Unsubscribe + sqs:Create/DeleteQueue）
04-Messaging             ←────   review-queue + DLQ
                         ←────   SNS Topic novelgen-generation-events (fan-out 到 per-replica SQS)
                         ←────   EventBridge Archive 7d
                         ←────   load-generation-context Lambda
                         ←────   ChapterStateMachine 完整 ASL (Choice Loop + Cancel 检查)
                         ←────   OutlineStateMachine ASL
05-Compute                       worker-generation 镜像更新 (Outline/Chapter/SelfCritique/OutlineReview agents)
                                 ApiService 镜像更新 (sse-starlette + SNS/SQS 消费协程)
06-Edge                          (不变)
07-Observability        ←────   3 Alarms (TTFT / GenerationSlow / CancelSlow)

cdk deploy --all 增量时间 ~5 min（不含 docker push）
```

---

## 图说明

| 图 | 用途 | 阅读场景 |
|---|---|---|
| **图 1** U4 生成数据流 | 理解 Outline/Chapter/SelfCritique 三条主路径 + SSE 链路 + Cancel 机制 | U4 开发 / debug 生成任务 |
| **图 2** SSE 时序图 | 理解 SNS fan-out 每 replica 独立 SQS 的设计原理 + Archive 重放 | 排查 SSE 断线 / 事件丢失 |
| **图 3** U4 对 U1 增量图 | 理解 U4 对 U1 Stack 的变更范围 | 发布计划 / 影响评估 |

---

## 合规与关键约束

- **串行章节生成**（F8=A）：LoopGuard Choice 保证 MaxConcurrency=1 的效果
- **Cancel 响应 ≤ 10s**（N2=B）：TTLCache 8s + Worker 每 token 检查
- **多 replica SSE**：SNS fan-out + 每 replica 独立 SQS，支持水平扩展
- **Last-Event-ID 回放**：依赖 EventBridge Archive 7 天
