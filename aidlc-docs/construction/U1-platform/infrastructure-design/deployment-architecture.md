# U1 Deployment Architecture — 架构图集

**Unit**：U1 Platform & Infrastructure
**阶段**：Infrastructure Design
**日期**：2026-04-27
**Figures**: 5 张（系统总览 / 分析数据流 / 生成数据流 / 网络拓扑 / CDK Stack 依赖）

每张图提供 **Mermaid 源** + **ASCII 文本替代**（content-validation.md 要求）。

---

## 图 1：系统总览（High-Level System Architecture）

### 1.1 Mermaid 源

```mermaid
flowchart TB
    subgraph Users["👥 Users"]
        U1[RegularUser / TeamMember]
        U2[Admin]
        U3[ContentModerator]
    end

    subgraph Edge["🌐 AWS Edge (Global)"]
        CFU[CloudFront<br/>User Distribution]
        CFA[CloudFront<br/>Admin Distribution]
        WAF[AWS WAF]
    end

    subgraph Region["📦 AWS Region: us-east-1"]
        subgraph VPCBlock["VPC 10.20.0.0/16"]
            subgraph PublicSub["Public Subnets"]
                ALB[Application<br/>Load Balancer]
            end

            subgraph PrivateSub["Private Subnets"]
                FEU[frontend-user<br/>SPA + BFF]
                FEA[frontend-admin<br/>SPA]
                API[api-service<br/>FastAPI]
                WRK[worker-service<br/>× 5 queue-specific]
                NEPT[(Neptune<br/>Serverless)]
            end

            VPCE[VPC Endpoints<br/>S3/DDB/Bedrock/...]
        end

        subgraph Auth["🔐 Identity"]
            COG[Cognito<br/>User Pool]
            ACID[AgentCore<br/>Identity]
        end

        subgraph AsyncBlock["⚙️ Async"]
            SFN[Step Functions<br/>× 5 State Machines]
            SQS[SQS<br/>× 5 + DLQs]
            EB[EventBridge<br/>Default Bus]
        end

        subgraph DataBlock["💾 Data"]
            DDB[(DynamoDB<br/>4 tables)]
            S3[(S3<br/>4 buckets)]
            OSS[(OpenSearch<br/>Serverless)]
        end

        subgraph AgentCore["🤖 AgentCore Services"]
            ACMEM[Memory]
            ACGW[Gateway]
            ACBR[Browser]
            ACRT[Runtime]
            ACOBS[Observability]
        end

        BR[Amazon Bedrock<br/>Claude Opus/Sonnet/Haiku 4.x]

        subgraph Obs["📊 Observability"]
            CW[CloudWatch<br/>Logs + Metrics + Alarms]
            SNS[SNS admin-alerts]
        end

        SEC[Secrets Manager<br/>+ SSM Parameter Store]
    end

    U1 --> CFU
    U2 --> CFA
    U3 --> CFU
    CFU --> WAF
    CFA --> WAF
    WAF --> ALB
    ALB --> FEU
    ALB --> FEA
    ALB --> API

    FEU -.BFF proxy.-> API
    FEA -.BFF proxy.-> API

    API -->|verify JWT| COG
    API --> DDB
    API --> S3
    API -->|StartExecution| SFN
    API -->|PutEvents| EB
    API --> BR

    SFN --> SQS
    SQS --> WRK
    WRK --> ACMEM
    WRK --> ACGW
    WRK --> ACBR
    WRK --> ACRT
    WRK --> BR
    WRK --> NEPT
    WRK --> OSS
    WRK --> DDB
    WRK --> S3
    WRK -->|PutEvents| EB
    EB --> API

    WRK -->|token via| ACID

    API --> VPCE
    WRK --> VPCE
    VPCE -.-> SEC
    VPCE -.-> BR

    API -.logs/metrics.-> CW
    WRK -.logs/metrics.-> CW
    ACRT --> ACOBS
    CW --> SNS

    style Users fill:#CE93D8,stroke:#6A1B9A,color:#000
    style Edge fill:#90CAF9,stroke:#0D47A1,color:#000
    style Region fill:#F5F5F5,stroke:#424242,color:#000
    style VPCBlock fill:#C8E6C9,stroke:#1B5E20,color:#000
    style Auth fill:#FFCCBC,stroke:#BF360C,color:#000
    style AsyncBlock fill:#FFE0B2,stroke:#E65100,color:#000
    style DataBlock fill:#B3E5FC,stroke:#01579B,color:#000
    style AgentCore fill:#F8BBD0,stroke:#880E4F,color:#000
    style Obs fill:#FFF9C4,stroke:#F57F17,color:#000
    linkStyle default stroke:#333,stroke-width:1.5px
```

### 1.2 ASCII 文本替代

```
Users -> CloudFront (User / Admin) -> WAF -> ALB (in VPC public subnet)
                                          |
                                          +-> frontend-user (SPA + Node BFF)
                                          +-> frontend-admin (SPA)
                                          +-> api-service (FastAPI)

api-service (FastAPI)
   |-> Cognito (verify JWT)
   |-> DynamoDB (4 tables)
   |-> S3 (4 buckets)
   |-> Step Functions (5 state machines)
   |-> EventBridge (publish)
   |-> Bedrock (direct calls if any)

Step Functions -> SQS (5 queues + DLQs) -> worker-service (5 queue-specific services)
   worker-service
      |-> AgentCore (Memory / Gateway / Browser / Runtime / Observability)
      |-> AgentCore Identity (get workload token)
      |-> Bedrock (Claude Opus/Sonnet/Haiku 4.x via Converse Stream)
      |-> Neptune Serverless (graph)
      |-> OpenSearch Serverless (vectors)
      |-> DynamoDB + S3
      +-> EventBridge (publish job events)

EventBridge --> api-service (SSE endpoint) --> ALB --> CloudFront --> Browser

CloudWatch Logs + Metrics + Alarms -> SNS admin-alerts -> Email
Secrets Manager + SSM Parameter Store -> VPC Endpoints -> Consumers
```

---

## 图 2：分析数据流（Analysis Flow）

### 2.1 Mermaid 源

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant BFF as NodeBff
    participant API as ApiService
    participant DDB as DynamoDB jobs
    participant SFN as Step Functions<br/>AnalysisStateMachine
    participant SQS as SQS analysis-queue
    participant WKR as Worker<br/>UnderstandingAgent
    participant BR as Bedrock Claude
    participant MEM as MemoryFacade
    participant ACM as AgentCore Memory
    participant NEP as Neptune
    participant OSS as OpenSearch
    participant EB as EventBridge

    User->>BFF: POST /api/v1/analyses<br/>(novel_id, mode)
    BFF->>API: 代理 + JWT
    API->>DDB: PutItem Job(status=QUEUED)
    API->>SFN: StartExecution(name=job_id)
    API-->>User: 200 {job_id}

    User->>BFF: GET /api/v1/jobs/{id}/stream (SSE)
    BFF->>API: SSE pipe
    Note over User,API: SSE long connection opened

    SFN->>DDB: UpdateItem status=RUNNING
    SFN->>SQS: SendMessage(taskToken + payload)
    SQS->>WKR: Receive
    WKR->>BR: RoughRead 抽样章节 (Sonnet)
    WKR->>MEM: remember(rough facts)
    MEM->>ACM: write

    par 并行 4 路
        WKR->>BR: Classification (Haiku)
    and
        WKR->>BR: ExtractCharacter (Sonnet)
        WKR->>MEM: upsert Fact + Graph
        MEM->>NEP: nodes+edges
    and
        WKR->>BR: ExtractMap (Sonnet)
        MEM->>NEP: place nodes
    and
        WKR->>BR: AnalyzeStyle (Sonnet 4.7)
    end

    loop DeepRead Map (并发 = current)
        WKR->>BR: 细读章节 N (Sonnet)
        WKR->>MEM: remember(chapter facts)
        MEM->>ACM: write
        MEM->>NEP: update graph
        MEM->>OSS: index embeddings
        WKR->>EB: PutEvents analysis.progress
        EB->>API: rule target SSE
        API-->>BFF: SSE event
        BFF-->>User: 进度更新
    end

    WKR->>DDB: 写 AnalysisReport 元数据
    WKR->>SFN: SendTaskSuccess(taskToken)
    SFN->>DDB: UpdateItem status=SUCCEEDED
    SFN->>EB: PutEvents analysis.completed
    EB->>API: forward
    API-->>BFF: SSE done event
    BFF-->>User: 分析完成
```

### 2.2 ASCII 文本替代

```
User                    BFF / API               Step Functions + Worker           Stores
 |                         |                         |                               |
 |--POST /analyses-------->|                         |                               |
 |                         |--PutItem Job(QUEUED)-------------------------------->DDB|
 |                         |--StartExecution------>SFN                              |
 |<-{job_id}---------------|                         |                               |
 |                         |                         |                               |
 |--GET /jobs/{id}/stream->|                         |                               |
 |<=========SSE open=======|                         |                               |
 |                         |                    [SFN RUNNING]                        |
 |                         |                         |--SendMsg w/taskToken-->SQS   |
 |                         |                         |                         |    |
 |                         |                    Worker receives                     |
 |                         |                         |                               |
 |                         |                    RoughRead (Bedrock Sonnet)           |
 |                         |                    Parallel(Classify/Char/Map/Style)    |
 |                         |                    MemoryFacade.remember -------------> AgentCore Memory
 |                         |                    MemoryFacade.upsertGraph ----------> Neptune
 |                         |                         |                               |
 |                         |                    DeepRead Map(concurrency=current)     |
 |                         |                         |--Bedrock calls × N (chapters) |
 |                         |                         |--Memory writes               |
 |                         |                         |--OpenSearch index vectors     |
 |                         |                         |                               |
 |                         |<---PutEvents analysis.progress---EventBridge            |
 |<=====SSE progress event=|                         |                               |
 |                         |                         |                               |
 |                         |                    Worker done --SendTaskSuccess-->SFN  |
 |                         |                    SFN UpdateItem SUCCEEDED --------->DDB|
 |                         |<---PutEvents analysis.completed------EventBridge        |
 |<=====SSE completed======|                         |                               |
```

---

## 图 3：生成数据流（Generation Flow + SSE 流式 + Cancel）

### 3.1 Mermaid 源

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant BFF as NodeBff
    participant API as ApiService
    participant DDB as DynamoDB jobs
    participant SFN as Step Functions<br/>ChapterStateMachine
    participant SQS as SQS generation-queue
    participant GW as Worker GenerationAgent
    participant BR as Bedrock Converse Stream
    participant CR as Worker CriticAgent
    participant MD as Worker ModerationAgent
    participant EB as EventBridge
    participant SSE as SSE endpoint

    User->>BFF: POST /generations (novel_id, mode=CLEAN_ROOM/CONTINUATION)
    BFF->>API: 代理
    API->>DDB: PutItem Generation Job
    API->>SFN: StartExecution outline-workflow
    API-->>User: {gen_id, outline_job_id}
    Note right of API: 大纲生成 (省略)
    User->>API: POST /outline/approve
    API->>SFN: StartExecution chapter-workflow

    loop For each chapter (按大纲)
        SFN->>SQS: SendMessage(chapter N payload)
        SQS->>GW: receive
        GW->>MEM: recall(related facts)
        Note over GW: 构造 prompt<br/>含 Memory 事实 + 风格向量
        GW->>BR: Converse Stream
        loop text_delta 流
            BR-->>GW: token chunk
            GW->>EB: PutEvents generation.chapter.streaming<br/>含 text_delta
            EB->>SSE: rule forward
            SSE-->>BFF: SSE text_delta
            BFF-->>User: 流式显示
            alt cancel_requested?
                GW->>DDB: 检查 Job.cancel_requested
                DDB-->>GW: true
                GW-->>BR: close stream
                GW->>DDB: Update status=CANCELED
                GW->>EB: PutEvents generation.cancel
                break 退出
            end
        end
        GW->>GW: SelfCritique (inline)
        GW->>DDB: Write chapter + self_critique
        GW->>EB: PutEvents generation.chapter.completed
        EB->>CR: rule → critic-queue
        EB->>MD: rule → moderation-queue
        par Critic
            CR->>MEM: recall Facts
            CR->>BR: Critic 评审 (Opus 4.7)
            CR->>DDB: 写 CritiqueReport
            CR->>EB: PutEvents critique_ready
        and Moderation
            MD->>BR: 敏感预标 (Sonnet)
            MD->>DDB: 写 flagged segments
            MD->>EB: PutEvents moderation.flagged
        end
        EB->>SSE: forward
        SSE-->>User: 建议 + 审核提醒
    end

    User->>API: POST /jobs/{id}/cancel (可选中途)
    API->>DDB: UpdateItem cancel_requested=true
    API-->>User: 202
```

### 3.2 ASCII 文本替代

```
User -> POST /generations (mode)
API -> Step Functions (OutlineStateMachine) -> generates outline -> User reviews -> approve
API -> Step Functions (ChapterStateMachine):

  for chapter 1..N:
    SFN -> SQS(generation-queue) -> GenerationWorker
      GW -> MemoryFacade.recall(related facts by chapter context)
      GW -> Bedrock Converse Stream (Sonnet 4.7 默认)
        while token chunks arrive:
          GW -> EventBridge PutEvents 'generation.chapter.streaming' (text_delta)
          EB -> ApiService SSE endpoint -> BFF -> Browser (流式显示)
          GW -> DynamoDB: 检查 Job.cancel_requested?
             if true: close stream, set status=CANCELED, break
      GW -> self-critique (inline with same model)
      GW -> DynamoDB: 写 chapter + self_critique
      GW -> EventBridge: 'generation.chapter.completed'

      parallel:
        Critic:
          CriticAgent -> Bedrock (Opus 4.7) -> CritiqueReport -> DynamoDB
          EventBridge 'critique_ready' -> SSE -> User
        Moderation:
          ModerationAgent -> Bedrock (Sonnet) -> flagged segments -> DynamoDB
          EventBridge 'moderation.flagged' -> SSE -> User / Moderator UI

Cancel:
  User -> POST /jobs/{id}/cancel
  API -> DynamoDB UpdateItem cancel_requested=true
  Worker 轮询检查此 flag，真则关闭 Bedrock stream 并标记 CANCELED。
```

---

## 图 4：网络拓扑（VPC + AZ + Subnets + Endpoints）

### 4.1 Mermaid 源

```mermaid
flowchart TB
    INET((Internet))
    CFTOP[CloudFront + WAF]

    subgraph AWS["AWS us-east-1 — Account"]
        subgraph VPC["VPC 10.20.0.0/16"]

            subgraph AZa["AZ us-east-1a"]
                SPA["public-a<br/>10.20.0.0/24"]
                SPRa["private-a<br/>10.20.16.0/22"]
                SIa["isolated-a<br/>10.20.32.0/24"]
            end

            subgraph AZb["AZ us-east-1b"]
                SPB["public-b<br/>10.20.1.0/24"]
                SPRb["private-b<br/>10.20.20.0/22"]
                SIb["isolated-b<br/>10.20.33.0/24"]
            end

            ALBN[ALB<br/>in public-a/b]
            NAT[NAT Gateway<br/>in public-a]
            IGW[Internet Gateway]

            ECSAPI[ECS api-service × 2]
            ECSFE[ECS frontend × 2]
            ECSWKR[ECS worker × 5]
            NEPTN[(Neptune<br/>private)]

            VPCE1[S3 Gateway Endpoint]
            VPCE2[DynamoDB Gateway Endpoint]
            VPCE3[Interface Endpoints:<br/>Secrets, SSM, Logs,<br/>Bedrock, STS, ECR, Events]
        end

        subgraph Managed["AWS Managed Services"]
            DDB[(DynamoDB)]
            S3[(S3)]
            BR[Bedrock]
            COG[Cognito]
            SM[Secrets Manager]
            ACORE[AgentCore Services]
            OSS[(OpenSearch<br/>Serverless)]
        end
    end

    INET --> CFTOP
    CFTOP --> IGW
    IGW --> ALBN
    ALBN --> ECSAPI
    ALBN --> ECSFE

    ECSAPI -.-> NAT
    ECSFE -.-> NAT
    ECSWKR -.-> NAT
    NAT --> IGW

    ECSAPI --> VPCE1
    ECSAPI --> VPCE2
    ECSAPI --> VPCE3
    ECSWKR --> VPCE1
    ECSWKR --> VPCE2
    ECSWKR --> VPCE3

    VPCE1 --- S3
    VPCE2 --- DDB
    VPCE3 --- SM
    VPCE3 --- BR
    VPCE3 --- COG
    VPCE3 --- ACORE

    ECSAPI --- NEPTN
    ECSWKR --- NEPTN

    ECSWKR --- OSS

    style VPC fill:#C8E6C9,stroke:#1B5E20,color:#000
    style AZa fill:#E1F5FE,stroke:#01579B,color:#000
    style AZb fill:#FCE4EC,stroke:#880E4F,color:#000
    style Managed fill:#FFE0B2,stroke:#E65100,color:#000
    linkStyle default stroke:#333,stroke-width:1.5px
```

### 4.2 ASCII 文本替代

```
Internet
   |
   v
CloudFront + WAF (global edge)
   |
   v
Internet Gateway  <---> NAT Gateway (in public-a, single AZ for dev)
   |                         ^
   v                         |
ALB (public-a + public-b)   |
   |                         |
   v                         |
ECS Services (private-a + private-b)
   - frontend-user × 2
   - frontend-admin × 1
   - api-service × 2
   - worker-analysis × 1  ----+
   - worker-generation × 1    |
   - worker-critic × 1        +-> NAT (egress for Bedrock, AgentCore, external)
   - worker-consistency × 1   |
   - worker-moderation × 1    |
                              |
VPC Endpoints (less NAT traffic):
   - S3 Gateway     <-> S3 Buckets
   - DynamoDB Gateway <-> DynamoDB tables
   - Interface: Secrets Manager, SSM, CloudWatch Logs, Bedrock Runtime,
                STS, ECR API/DKR, EventBridge

Neptune Serverless (in private-a, private-b subnets)
OpenSearch Serverless (managed, AOSS endpoint via Interface endpoint)

Subnet CIDR 分配:
  public-a    10.20.0.0/24   (ALB, NAT)
  public-b    10.20.1.0/24   (ALB)
  private-a   10.20.16.0/22  (ECS, Neptune)
  private-b   10.20.20.0/22  (ECS, Neptune)
  isolated-a  10.20.32.0/24  (预留)
  isolated-b  10.20.33.0/24  (预留)
```

---

## 图 5：CDK Stack 依赖图

### 5.1 Mermaid 源

```mermaid
flowchart LR
    NET[01-NetworkStack<br/>VPC, Subnets, VPCE, SGs]
    DATA[02-DataStack<br/>DDB ×4, S3 ×4, Neptune, OpenSearch, Secrets, SSM]
    IDT[03-IdentityStack<br/>Cognito, IdP, IAM Roles, PreSignUp Lambda]
    MSG[04-MessagingStack<br/>SQS ×10, EventBridge, Step Functions ×5]
    COMP[05-ComputeStack<br/>ECS Cluster, ECR ×8, TaskDefs, Services, ALB]
    EDGE[06-EdgeStack<br/>CloudFront ×2, WAF]
    OBS[07-ObservabilityStack<br/>LogGroups, Metric Filters, Alarms, SNS, Aggregator Lambda]
    AC[08-AgentCoreStack<br/>Memory, Gateway, Browser, Identity, Runtime, Observability]

    NET --> DATA
    NET --> IDT
    DATA --> MSG
    IDT --> MSG
    DATA --> COMP
    IDT --> COMP
    MSG --> COMP
    COMP --> EDGE
    DATA --> OBS
    COMP --> OBS
    DATA --> AC
    IDT --> AC

    style NET fill:#BBDEFB,stroke:#1565C0,color:#000
    style DATA fill:#C8E6C9,stroke:#2E7D32,color:#000
    style IDT fill:#FFCCBC,stroke:#BF360C,color:#000
    style MSG fill:#FFE0B2,stroke:#E65100,color:#000
    style COMP fill:#F8BBD0,stroke:#880E4F,color:#000
    style EDGE fill:#90CAF9,stroke:#0D47A1,color:#000
    style OBS fill:#FFF9C4,stroke:#F57F17,color:#000
    style AC fill:#D1C4E9,stroke:#4527A0,color:#000
    linkStyle default stroke:#333,stroke-width:2px
```

### 5.2 ASCII 文本替代

```
Deployment order (topological):

  Level 0:  01-NetworkStack (VPC, Subnets, VPCE, SGs)
                    |
      +-------------+--------------+
      |                            |
      v                            v
  Level 1:  02-DataStack       03-IdentityStack
            (DDB/S3/Neptune/   (Cognito, IdP,
             OpenSearch/       IAM Roles,
             Secrets/SSM)      PreSignUp λ)
      |        |                   |
      +--------+-------+-----------+
                       |
                       v
  Level 2:  04-MessagingStack (SQS, EventBridge, Step Functions)
                       |
                       v
  Level 3:  05-ComputeStack (ECS Cluster, Services, ALB)
                       |
                       v
  Level 4:  06-EdgeStack (CloudFront × 2, WAF)

  独立叶子（不阻塞前面的部署）:
    07-ObservabilityStack  (depends on DataStack + ComputeStack)
    08-AgentCoreStack      (depends on DataStack + IdentityStack)

部署命令：
  cdk deploy --all              # 全量（~43min）
  cdk deploy --exclusively 05-ComputeStack  # 单栈
  cdk deploy 06-EdgeStack       # 仅 CloudFront
```

---

## 附：图的使用建议

| 图 | 用途 | 阅读场景 |
|---|---|---|
| 图 1 系统总览 | 新成员 onboarding、架构评审 | 首次理解系统 |
| 图 2 分析数据流 | U3 开发、debug 分析任务 | 查看 "分析为何慢" |
| 图 3 生成数据流 | U4/U5 开发、SSE 问题排查 | 章节生成/取消/Critic |
| 图 4 网络拓扑 | 网络/安全问题排查、成本优化 | VPC endpoint 走向、NAT 流量 |
| 图 5 CDK Stack 依赖 | 部署顺序、回滚策略、CI 规划 | 发布前 |

---

## 跨图一致性检查

- **多租户**：图 1-3 中所有数据存储都带 team_id 前缀/命名空间（在 MemoryFacade、StorageAdapter 层保证）
- **AgentCore**：图 1 Agent 调用经 Runtime；图 2-3 细化到各 sub-agent；图 4 Agent 调用走 Interface Endpoint；图 5 AgentCoreStack 单独
- **SSE**：图 1 BFF 中继；图 3 展示完整流式链路；图 4 说明 ALB IdleTimeout 600s；图 5 跨 ComputeStack + MessagingStack
- **Step Functions**：图 1 Async 盒子；图 2-3 具体使用；图 5 MessagingStack
