# U3 Deployment Architecture — 架构图集

**Unit**：U3 Understanding Agents
**阶段**：Infrastructure Design
**日期**：2026-04-28
**Figures**: 3 张（U3 数据流 / MemoryFacade 三后端写入 / U3 对 U1 增量）

---

## 图 1：U3 数据流（Supervisor + 6 sub-agent + 三存储后端）

### 1.1 Mermaid 源

```mermaid
flowchart TB
    EB[EventBridge<br/>novel.ingested] --> API[ApiService<br/>Create Analysis Job]
    API --> DDB1[(DynamoDB Job<br/>status=QUEUED)]
    API --> SFN[Step Functions<br/>AnalysisStateMachine]

    SFN --> L1[Lambda<br/>load-novel-metadata]
    L1 --> DDB2[(DynamoDB Tenancy<br/>read chapters)]
    L1 --> SFN

    SFN -->|WAIT_FOR_TASK_TOKEN| SQS[[analysis-queue]]
    SQS --> W[worker-analysis<br/>ECS Fargate]

    W --> SUP[Supervisor Agent<br/>Opus 4.7]
    SUP -->|decide next tool| RR[sample_chapters<br/>Haiku 4.5]
    SUP --> CLS[classify_tags<br/>Sonnet 4.6]
    SUP --> CG[extract_characters_global<br/>Sonnet 4.6]
    SUP --> MG[extract_map_global<br/>Sonnet 4.6]
    SUP --> ST[analyze_style<br/>Sonnet 4.7]
    SUP -->|per chapter loop| CA[extract_chapter_all<br/>Sonnet 4.7<br/>Tool Use JSON]
    SUP --> FN[finalize_report]

    CA --> MF[MemoryFacade<br/>Flush per chapter]

    MF --> ACM[(AgentCore Memory<br/>critical)]
    MF --> NEP[(Neptune<br/>openCypher MERGE<br/>degradable)]
    MF --> OSS[(OpenSearch<br/>facts-team_id<br/>HNSW 1024 dim<br/>degradable)]

    MF --> TITAN[Titan Embeddings V2<br/>1024 dim]
    TITAN --> OSS

    SUP -->|every 5 steps| CP[(DDB Checkpoint<br/>CHECKPOINT#job_id<br/>TTL 24h)]

    FN --> S3R[(S3 analysis-report.json)]
    FN --> W
    W -->|SendTaskSuccess| SFN
    SFN --> EB2[EventBridge<br/>novel.analyzed]
    EB2 -.->|future U4| U4[U4 GenerationAgent]

    style SUP fill:#D1C4E9,stroke:#4527A0,color:#000
    style MF fill:#FFE0B2,stroke:#E65100,color:#000
    style ACM fill:#C8E6C9,stroke:#2E7D32,color:#000
    style NEP fill:#BBDEFB,stroke:#1565C0,color:#000
    style OSS fill:#F8BBD0,stroke:#880E4F,color:#000
    style W fill:#FFF9C4,stroke:#F57F17,color:#000
    linkStyle default stroke:#333,stroke-width:1.5px
```

### 1.2 ASCII 替代

```
EventBridge novel.ingested → ApiService → DDB Job(QUEUED) → Step Functions AnalysisStateMachine
                                                             │
                                                             ├→ Lambda load-novel-metadata
                                                             │   └→ DDB read chapters
                                                             │
                                                             ├→ SQS analysis-queue (WAIT_FOR_TASK_TOKEN)
                                                             │
                                                             ↓
                                                     worker-analysis Task
                                                             │
                                                             ↓
                                                  Supervisor Agent (Opus 4.7)
                                                             │
                               ┌─────────────────────────────┼────────────────────────┐
                               ↓                             ↓                         ↓
                       sample_chapters (Haiku)     (parallel global analysis)     per-chapter loop
                                                        classify_tags                 │
                                                        extract_chars_global          ↓
                                                        extract_map_global      extract_chapter_all (Sonnet 4.7)
                                                        analyze_style                 (Bedrock Tool Use JSON)
                                                                                      │
                                                                                      ↓
                                                                                MemoryFacade flush
                                                                                      │
                                              ┌───────────────────────────┬──────────┼──────────┐
                                              ↓ (critical)                ↓ (degrad) ↓ (degrad)
                                          AgentCore Memory            Neptune       OpenSearch
                                                                  (openCypher)   (facts-team_id, HNSW)
                                                                                      ↑
                                                                              Titan Embed V2 (1024d)

Every 5 steps: Supervisor → DDB Checkpoint (TTL 24h)
End: finalize_report → S3 analysis-report.json
     SendTaskSuccess → Step Functions → EventBridge novel.analyzed → U4
```

---

## 图 2：MemoryFacade 三后端写入流程（I4=B 新增）

### 2.1 Mermaid 源

```mermaid
sequenceDiagram
    participant CA as extract_chapter_all
    participant MF as MemoryFacade
    participant TITAN as Titan Embed V2
    participant ACM as AgentCore Memory
    participant NEP as Neptune
    participant OSS as OpenSearch
    participant M as Metric Emitter

    CA->>MF: remember_and_upsert(facts, nodes, edges)

    Note over MF,ACM: Critical path — must succeed
    MF->>ACM: batch put_memory_item(20 facts)
    ACM-->>MF: 200 OK
    MF->>M: emit MemoryWriteSuccess{Layer=agentcore}

    par Neptune + OpenSearch run in parallel
        MF->>NEP: openCypher batch MERGE (nodes)
        alt Neptune success
            NEP-->>MF: 200 OK
        else Neptune timeout / 5xx
            NEP-->>MF: error
            MF->>M: emit MemoryWriteFailure{Layer=neptune}
            Note over MF: log warning, continue
        end
        MF->>NEP: openCypher batch MERGE (edges)
    and
        MF->>TITAN: invoke_model(text × 20)
        TITAN-->>MF: embeddings (1024 dim × 20)
        MF->>OSS: bulk _index(facts-team_id)
        alt OpenSearch success
            OSS-->>MF: 200 OK
        else OpenSearch throttle / 5xx
            OSS-->>MF: error
            MF->>M: emit MemoryWriteFailure{Layer=opensearch}
            Note over MF: log warning, continue
        end
    end

    MF-->>CA: FlushResult{ok=true, degradations=[...]}
```

### 2.2 ASCII 替代

```
extract_chapter_all → MemoryFacade.remember_and_upsert(facts, nodes, edges)
                         │
                         ├─[1] AgentCore Memory (CRITICAL, must succeed)
                         │      batch put_memory_item(20 facts)
                         │      失败 → raise MemoryBackendError (致命)
                         │
                         ├─[2a] (parallel with 2b) Neptune
                         │      openCypher batch MERGE nodes (Place/Character/Event/Faction)
                         │      openCypher batch MERGE edges (visited/located_in/event_at/belongs_to/rival)
                         │      失败 → warning + emit metric MemoryWriteFailure{Layer=neptune}, 继续
                         │
                         └─[2b] (parallel) OpenSearch
                                Titan Embed V2 (1024d × 20 facts)
                                bulk _index(facts-team_id)
                                失败 → warning + emit metric MemoryWriteFailure{Layer=opensearch}, 继续

                         → FlushResult{ok=true, degradations=[neptune|opensearch|none]}
```

---

## 图 3：U3 对 U1 增量部署图

### 3.1 Mermaid 源

```mermaid
flowchart LR
    subgraph U1["U1 现有 Stack（U3 扩展点）"]
        Network[01-Network<br/>不变]
        Data[02-Data<br/>+5 SSM Parameters]
        Identity[03-Identity<br/>+worker-analysis Role 补 Neptune/AOSS/AgentCore]
        Messaging[04-Messaging<br/>+完整 AnalysisStateMachine ASL<br/>+load-novel-metadata Lambda]
        Compute[05-Compute<br/>worker-analysis 镜像更新<br/>Service 定义不变]
        Edge[06-Edge<br/>不变]
        Obs[07-Observability<br/>+5 Alarms]
        AgentCore[08-AgentCore<br/>Memory namespace 模板<br/>Observability project 配置]
    end

    subgraph U3New["U3 新代码（部署到 U1 Stack）"]
        NewASL[AnalysisStateMachine ASL<br/>UpdateRunning → LoadMeta → InvokeSupervisor →<br/>PublishAnalyzed → JobSucceeded]
        NewLambda[load-novel-metadata Lambda]
        NewSSM[5 SSM: titan-embed-model/dim<br/>supervisor-max-steps/retry-max<br/>memory-write-timeout]
        NewIAM[Neptune-db + AOSS + AgentCore<br/>IAM policies]
        NewAlarms[5 Alarms: AnalysisTimeoutP95<br/>SupervisorDrift / MemoryWriteFailure<br/>NeptuneSlowUpsert / ChapterPartialRate]
    end

    NewASL -.-> Messaging
    NewLambda -.-> Messaging
    NewSSM -.-> Data
    NewIAM -.-> Identity
    NewAlarms -.-> Obs

    style U1 fill:#BBDEFB,stroke:#1565C0,color:#000
    style U3New fill:#E1BEE7,stroke:#6A1B9A,color:#000
    linkStyle default stroke:#999,stroke-width:1.5px,stroke-dasharray: 3 3
```

### 3.2 ASCII 替代

```
U1 Stack 层                        U3 新增内容（扩展点）
─────────────────────             ─────────────────────
01-Network                         (不变)
02-Data                     ←───   5 SSM Parameters
                                   (titan-embed-model/dim/supervisor-max-steps/
                                    chapter-retry-max/memory-write-timeout-ms)
03-Identity                 ←───   worker-analysis Role 补齐:
                                   - bedrock-agentcore:InvokeAgent/CreateAgent/
                                     DescribeAgent/PutMemoryItem/GetMemoryItem/
                                     QueryMemory
                                   - neptune-db:ReadDataViaQuery/WriteDataViaQuery
                                   - aoss:APIAccessAll/BatchGetCollection
04-Messaging                ←───   完整 AnalysisStateMachine ASL
                                   (UpdateRunning → LoadMetadata Lambda →
                                    InvokeSupervisor WAIT_FOR_TASK_TOKEN →
                                    PublishAnalyzed EventBridge →
                                    UpdateSucceeded / JobFailed)
                            ←───   load-novel-metadata Lambda
05-Compute                         worker-analysis 镜像更新 (Strands + MemoryFacade)
                                   Service 定义不变
06-Edge                            (不变)
07-Observability            ←───   5 new Alarms
                                   (U3AnalysisTimeoutP95 / SupervisorDrift /
                                    MemoryWriteFailureHigh / NeptuneSlowUpsert /
                                    ChapterPartialRateHigh)
08-AgentCore                ←───   Memory namespace 模板声明
                                   Observability project = novelgen-{env}
                                   (Runtime 注册由 Worker 启动时自注册，I2=C)

预计 cdk deploy --all 增量时间：~4 分钟 (不含 docker push)
```

---

## 图说明

| 图 | 用途 | 阅读场景 |
|---|---|---|
| **图 1** U3 数据流 | 理解 Supervisor 如何编排 6 sub-agent + 三存储 | U3 开发 / debug 分析任务 |
| **图 2** MemoryFacade 写入 | 理解三后端并行 + 分层降级 | Memory 失败排查 / 性能优化 |
| **图 3** U3 对 U1 增量 | 理解 U3 对 U1 Stack 的最小变更范围 | 发布计划 / 影响评估 |

---

## 合规与关键约束（在图中标注）

- **AgentCore Memory 为 critical 层**：失败即 Job FAILED
- **Neptune / OpenSearch 为降级层**：失败仅 warning + metric，业务继续
- **Bedrock Tool Use 强制 JSON schema**：解析失败率接近 0
- **Supervisor 50 步上限** + **每 5 步 checkpoint**：防止 Opus 决策飘移 / Spot 回收损失
- **多租户三层过滤**：Memory namespace + Neptune team_id property + OpenSearch filter
