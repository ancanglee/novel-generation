# U2 Deployment Architecture — 架构图集

**Unit**：U2 Ingestion Service
**阶段**：Infrastructure Design
**日期**：2026-04-27
**Figures**: 2 张（U2 数据流 / 扩展 U1 的增量图）

---

## 图 1：U2 数据流（3 触发路径 + 两级 Tier 降级）

### 1.1 Mermaid 源

```mermaid
flowchart TB
    User[Browser]
    BFF[NodeBff]
    API[ApiService /api/v1/novels/*]
    DDB[(DynamoDB<br/>jobs + tenancy)]
    S3Raw[(S3 novels)]
    S3Cache[(S3 crawl-cache)]
    SFN[Step Functions<br/>IngestionStateMachine]
    Choice{Choice by kind}
    SQS[[ingestion-queue]]
    Worker[worker-ingestion Task<br/>asyncio 5 concurrent]
    Counter[(DDB COUNTER<br/>BROWSER_CONCURRENCY<br/>max=10)]

    subgraph Tier1["🟢 Tier 1: HTTP 爬虫"]
        T1HTTP[httpx GET<br/>trafilatura extract]
        Parsers[Parsers:<br/>txt/md/epub/pdf/docx/html]
    end

    subgraph Tier2["🟠 Tier 2: AgentCore Browser"]
        T2Lock[Acquire Browser Slot<br/>CAS on Counter]
        T2BR[AgentCore Browser<br/>render JS + DOM]
        T2Rel[Release Slot]
    end

    LLM[Bedrock Haiku<br/>Chapter Split LLM]
    EB[EventBridge<br/>novel.ingested]
    U3[U3 analysis worker<br/>downstream]

    User-->|POST /upload /download /crawl|BFF
    BFF-->API
    API-->|PutItem Job QUEUED|DDB
    API-->|StartExecution|SFN
    SFN-->Choice
    Choice-->|upload|SQS
    Choice-->|download|SQS
    Choice-->|crawl|SQS
    SQS-->Worker

    Worker-->|upload|Parsers
    Worker-->|crawl or download URL|T1HTTP
    T1HTTP-->|check robots.txt|T1HTTP
    T1HTTP-->|success 200 + content≥200|Parsers
    T1HTTP-->|403/429/503 or JS-only or timeout|T2Lock
    T1HTTP-->|robots disallow|JobFailed[JobFailed]

    T2Lock-->|acquire CAS|Counter
    T2Lock-->|success|T2BR
    T2Lock-->|10 retries fail|Worker
    T2BR-->Parsers
    T2BR-->T2Rel
    T2Rel-->Counter

    Worker-->|chapter split confidence<0.6|LLM
    LLM-->Worker

    Worker-->|write raw.md + chapters/|S3Raw
    Worker-->|write Novel+Chapter rows|DDB
    Worker-->|cache HTML|S3Cache

    Worker-->|SendTaskSuccess|SFN
    SFN-->|PutEvents|EB
    EB-->API
    EB-.->U3
    API-->|SSE to Browser|User

    style Tier1 fill:#C8E6C9,stroke:#2E7D32,color:#000
    style Tier2 fill:#FFE0B2,stroke:#E65100,color:#000
    style Worker fill:#BBDEFB,stroke:#1565C0,color:#000
    style Counter fill:#F8BBD0,stroke:#880E4F,color:#000
    linkStyle default stroke:#333,stroke-width:1.5px
```

### 1.2 ASCII 替代

```
Browser → BFF → ApiService → Step Functions IngestionStateMachine
                              │
                    ┌─────────┴─────────┐
                   Choice by payload.kind
                    │         │         │
                 upload    download    crawl
                    └─────────┬─────────┘
                              ▼
                         SQS ingestion-queue
                              ▼
                    worker-ingestion (asyncio 5 concurrent)
                              │
                ┌─────────────┼──────────────┐
                ▼             ▼              ▼
           Parsers:       Tier 1 HTTP     robots.txt
           txt/md/epub/   httpx +         disallow → Fail
           pdf/docx/html  trafilatura
                              │ 403/429/JS-only/timeout
                              ▼
                    Tier 2 AgentCore Browser
                              │ acquire Browser Slot (CAS on DDB COUNTER, max=10)
                              │ render JS + DOM
                              │ release slot
                              ▼
                         Parsers → 章节切分 (启发式)
                              │ confidence < 0.6
                              ▼
                         Bedrock Haiku 辅助
                              ▼
                    ┌────────────────────────┐
                    ▼                        ▼
               S3 raw.md + chapters/    DynamoDB Novel+Chapter
                    │
                    ▼
             S3 crawl-cache (7d TTL, URL hash)
                              ▼
                 SFN SendTaskSuccess → EventBridge novel.ingested
                              ▼
                    ApiService SSE → Browser
                    (未来 U3 analysis worker 订阅)
```

---

## 图 2：扩展 U1 的增量部署图

### 2.1 Mermaid 源

```mermaid
flowchart LR
    subgraph U1["U1 现有 Stack（U2 扩展点）"]
        Network[01-Network<br/>不变]
        Data[02-Data<br/>+S3 Lifecycle<br/>+6 SSM Parameters<br/>+Counter 项]
        Identity[03-Identity<br/>+worker-ingestion Role]
        Messaging[04-Messaging<br/>+ingestion-queue + DLQ<br/>+NovelIngestedRule<br/>+填充 IngestionStateMachine ASL]
        Compute[05-Compute<br/>+worker-ingestion Service<br/>+ECR repo]
        Edge[06-Edge<br/>不变]
        Obs[07-Observability<br/>+5 Alarms]
        AgentCore[08-AgentCore<br/>+Browser 配置]
    end

    subgraph U2New["U2 新代码（部署到 U1 Stack）"]
        NewQueue[ingestion-queue + DLQ]
        NewRole[worker-ingestion IAM Role]
        NewService[worker-ingestion ECS Service]
        NewECR[ECR novelgen/worker-ingestion]
        NewLifecycle[S3 crawl-cache 7d<br/>uploads/tmp 1d]
        NewASL[IngestionStateMachine 完整 ASL<br/>Choice 分支 + Tier 2 兜底]
        NewAlarms[5 new Alarms]
        NewSSM[6 SSM Parameters]
        NewCounter[DDB Counter 初始化项]
    end

    NewQueue-.->Messaging
    NewRole-.->Identity
    NewService-.->Compute
    NewECR-.->Compute
    NewLifecycle-.->Data
    NewASL-.->Messaging
    NewAlarms-.->Obs
    NewSSM-.->Data
    NewCounter-.->Data

    style U1 fill:#BBDEFB,stroke:#1565C0,color:#000
    style U2New fill:#FFF9C4,stroke:#F57F17,color:#000
    linkStyle default stroke:#999,stroke-width:1.5px,stroke-dasharray: 3 3
```

### 2.2 ASCII 替代

```
U1 Stack 层                              U2 新增内容（扩展点）
─────────────────────                   ─────────────────────
01-Network                              (不变)
02-Data                          ←───   S3 Lifecycle: crawl-cache 7d / uploads 1d
                                 ←───   6 SSM Parameters
                                 ←───   DynamoDB COUNTER 初始化项 (Browser=10)
03-Identity                      ←───   worker-ingestion IAM Role
                                        (+ Bedrock/AgentCore/SQS/Events/SSM)
04-Messaging                     ←───   ingestion-queue + DLQ
                                 ←───   NovelIngestedRule (EventBridge)
                                 ←───   填充 IngestionStateMachine ASL
                                        (Choice by kind: upload/download/crawl
                                         + TryBrowserFallback SFN 兜底)
05-Compute                       ←───   worker-ingestion ECS Service
                                        (Fargate SPOT:on-demand=4:1, 1-5 tasks)
                                 ←───   ECR repo novelgen/worker-ingestion
06-Edge                                 (不变)
07-Observability                 ←───   5 new Alarms
                                        (CrawlDowngrade/SearchDowngrade/
                                         BrowserOverused/IngestionTimeoutP95/
                                         RobotsBlockedHigh)
08-AgentCore                     ←───   Browser 会话配置（placeholder 扩展）

单次 cdk deploy --all 增量时间：~8 分钟
```

---

## 图说明

| 图 | 用途 | 阅读场景 |
|---|---|---|
| **图 1** U2 数据流 | 理解 upload/download/crawl 三路径如何走 Tier 1 → Tier 2 | U2 开发、debug 抓取问题 |
| **图 2** 增量部署图 | 理解 U2 对 U1 Stack 的扩展点与 CDK 变更范围 | 发布计划、影响评估 |

---

## 合规关键点（图 1 重点标注）

- **robots.txt disallow → 硬拒绝**（不走 Tier 2）
- **Tier 2 Browser 仍然遵守 robots.txt**
- **Browser 并发硬上限 10**（DDB COUNTER CAS 保障）
- **搜索引擎来源强制 audit**（business-rules R9.2，图中未展开但在 Worker 代码内实现）
