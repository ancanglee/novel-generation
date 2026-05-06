# U3 Tech Stack Decisions

**Unit**：U3 Understanding Agents
**日期**：2026-04-28

U3 继承 U1 + U2 的技术栈。本文仅记录 U3 新增/细化的选择。

---

## 1. Agent 框架（AD7=B Strands + AgentCore）

| 方面 | 决策 |
|---|---|
| 框架 | **Strands Agents** (latest)，通过 `@tool` 装饰器注册 sub-agent |
| 运行时 | **AgentCore Runtime**（托管 Agent 执行环境）|
| 编排模式 | **Supervisor Agent**（F1=B），单顶层 Agent 决定调用哪个 sub-agent |
| Supervisor 模型 | Claude Opus 4.7（复杂推理决策） |
| Sub-agent 模型 | 按 ModelConfig 配置（Sonnet 4.6/4.7 为主，Haiku 4.5 处理抽样） |

---

## 2. MemoryFacade 后端

### 2.1 AgentCore Memory
- Namespace 模板：`{team_id}:{novel_id}`
- 一致性：eventual
- API：bedrock-agentcore SDK 原生调用

### 2.2 Neptune Serverless（N3=B + C1=C）
| 方面 | 决策 |
|---|---|
| 容量 | 最小 1 NCU / 最大 16 NCU（保持 U1 默认）|
| 查询语言 | **openCypher**（主）+ Gremlin（备，用于复杂遍历）|
| 认证 | IAM SigV4（boto3 辅助签名） |
| 驱动 | `httpx` + 自实现 sigv4 签名（不引入重型驱动）|
| 事务 | 每批 ≤ 100 节点 + 100 边 |
| 连接池 | 10 并发连接（单 Worker）|

### 2.3 OpenSearch Serverless Vector Search
| 方面 | 决策 |
|---|---|
| 索引命名 | `facts-{team_id}`（按 team 分索引，便于清理）|
| 向量字段 | `embedding`（type=knn_vector，dim=1024）|
| 算法 | HNSW + ef_construction=512 + m=16（默认推荐）|
| 距离 | Cosine similarity |
| 驱动 | `opensearch-py~=2.7` + `requests-aws4auth`（sigv4）|
| 混合检索 | BM25 + kNN，客户端 RRF 合并 |

### 2.4 Titan Embeddings V2（N6=A）
| 方面 | 决策 |
|---|---|
| 模型 ID | `amazon.titan-embed-text-v2:0` |
| 维度 | **1024** |
| normalize | true |
| 调用方式 | `bedrock-runtime.invoke_model` |
| 客户端缓存 | 进程内 LRU(1000)，key=sha256(text) |

---

## 3. Bedrock Claude 使用（继承 U1 ModelConfig）

| Stage | 默认模型 | 说明 |
|---|---|---|
| `sample_chapters` | Haiku 4.5 | 目录级决策，成本优先 |
| `classify_tags` | Sonnet 4.6 | 多标签分类 |
| `extract_characters_global` | Sonnet 4.6 | 粗读 Profile 初稿 |
| `extract_map_global` | Sonnet 4.6 | 粗读主要地点/势力 |
| `analyze_style` | Sonnet 4.7 | 风格评分（需细腻理解）|
| `extract_chapter_all` | Sonnet 4.7 | 细读单章复合抽取（F7=A）|
| `rewrite_character_profile` | Opus 4.7 | 罕见 Profile 重写 |
| `supervisor_decision` | Opus 4.7 | Supervisor 自身 |

所有映射继承 U1 DEFAULT_MODEL_MAPPING，admin 可在线覆盖。

---

## 4. Python 依赖

新增 U3 特有包：
```
strands-agents       ~=0.x     # Supervisor + @tool 装饰器
bedrock-agentcore    (AWS SDK) # AgentCore Memory/Runtime
opensearch-py        ~=2.7
requests-aws4auth    ~=1.3
httpx                (已有)    # Neptune HTTP client
pydantic             (已有)    # JSON schema 校验
jsonschema           ~=4.23    # LLM 响应校验
```

---

## 5. Worker 规格

U3 扩展 U1 `worker-analysis` Service（U1 已预定义）：
- CPU 2048 / Memory 4096 MB
- FARGATE_SPOT 混合
- Auto Scaling：min 1 / max 5，基于 `analysis-queue` 深度

无需新增 ECS Service（U1 `worker-analysis` 即是 U3 的 Worker）。

---

## 6. Docker 镜像

`novelgen/worker-analysis` 在 U1 预建 ECR Repo 上推送：
- Base：`python:3.12-slim`
- 系统依赖：libxml2 / libxslt（与 U2 共享基础）
- 不需要 poppler（U3 不做 PDF 解析）
- 预估大小：~280 MB（含 strands + opensearch-py）

---

## 7. 与 U1 + U2 + U4 接口

### 7.1 向 U1 填充
- **MemoryFacade 具体实现**（U1 只提供抽象）：`packages/memory-facade-impl/`
- 新增 U1 ComputeStack 中 `worker-analysis` 的 env：`NEPTUNE_ENDPOINT` / `OPENSEARCH_ENDPOINT`
- IAM 新增：Neptune / OpenSearch / Titan Embeddings 权限

### 7.2 订阅 U2 事件
- EventBridge `novel.ingested` → 触发 U3 AnalysisStateMachine

### 7.3 为 U4 提供
- MemoryFacade.recall() / get_character() / neighbors() 接口
- EventBridge `novel.analyzed` 事件（U4 订阅后开始大纲生成）

---

## 8. 未决项（Infra Design 处理）

- Neptune IAM SigV4 签名辅助库的选择（自写 vs `aws-neptune-gremlin` 社区库）
- OpenSearch 索引 mapping 的具体配置 JSON
- Strands Agents 的 AgentCore Runtime 集成包路径
- Supervisor 系统 prompt 的最终版本
