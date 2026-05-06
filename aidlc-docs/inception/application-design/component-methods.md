# 组件方法（Component Methods）— 小说仿写生成应用

**版本**：1.0
**日期**：2026-04-27
**说明**：方法签名为高层设计。详细业务规则在 Functional Design（per-unit，CONSTRUCTION 阶段）完善。

---

## C-03 NodeBff

```ts
// session.ts
exchangeCognitoToken(id_token: string): Promise<Session>
refreshSession(cookie: string): Promise<Session>
destroySession(cookie: string): Promise<void>

// proxy.ts
forwardRest(req: Request): Promise<Response>
relaySse(req: Request, res: Response): void  // 保活、lastEventId 处理

// static.ts
serveSpa(path: string): Response
```

---

## C-04 ApiService — 主要 REST 端点

### Novel（IngestionModule）
```python
POST   /api/v1/novels/upload            -> NovelSummary     # multipart
POST   /api/v1/novels/download          -> JobRef           # body: {title}
POST   /api/v1/novels/crawl             -> JobRef           # body: {url}
GET    /api/v1/novels                   -> List[NovelSummary]
GET    /api/v1/novels/{novel_id}        -> NovelDetail
DELETE /api/v1/novels/{novel_id}        -> 204
```

### Analysis
```python
POST   /api/v1/analyses                 -> JobRef           # body: {novel_id}
GET    /api/v1/analyses/{job_id}        -> AnalysisStatus
GET    /api/v1/novels/{novel_id}/report -> AnalysisReport   # 合并报告
```

### Generation
```python
POST   /api/v1/generations              -> JobRef           # body: {novel_id, mode, style, chapters, words}
GET    /api/v1/generations/{gen_id}     -> GenerationStatus
POST   /api/v1/generations/{gen_id}/outline/approve        -> 200
POST   /api/v1/generations/{gen_id}/outline/reject         -> 200
POST   /api/v1/jobs/{job_id}/cancel     -> 202              # AD4 澄清引入
GET    /api/v1/jobs/{job_id}/stream     -> SSE              # 流式
GET    /api/v1/generations/{gen_id}/chapters                -> List[ChapterRef]
GET    /api/v1/generations/{gen_id}/chapters/{n}            -> Chapter
PUT    /api/v1/generations/{gen_id}/chapters/{n}            -> Chapter  # 编辑
POST   /api/v1/generations/{gen_id}/chapters/{n}/rewrite    -> JobRef
POST   /api/v1/generations/{gen_id}/export                  -> SignedUrl
```

### Review
```python
GET    /api/v1/reviews/pending          -> List[ReviewItem]  # ContentModerator
POST   /api/v1/reviews/{chapter_id}/segments/{seg_id}/reject -> 200
GET    /api/v1/critiques/{chapter_id}   -> CritiqueReport
GET    /api/v1/consistency/{novel_id}   -> ConsistencyReport
```

### Admin（`@require_role("admin")`）
```python
GET    /api/v1/admin/users              -> List[User]
POST   /api/v1/admin/teams              -> Team
PUT    /api/v1/admin/teams/{id}/members -> Team
GET    /api/v1/admin/tags               -> List[Tag]           # 类型标签
POST   /api/v1/admin/tags/merge         -> 200                 # 合并
GET    /api/v1/admin/schemas            -> List[AnalysisSchema]
POST   /api/v1/admin/schemas            -> AnalysisSchema
PUT    /api/v1/admin/models             -> ModelConfig         # 任务-模型映射
PUT    /api/v1/admin/concurrency        -> ConcurrencyConfig   # AD6 细读并发上限
GET    /api/v1/admin/metrics            -> MetricsPayload
GET    /api/v1/admin/audit              -> List[AuditEvent]
PUT    /api/v1/admin/alerts             -> AlertConfig
```

---

## C-05 WorkerService — 核心方法

```python
class Worker:
    async def run(queue_name: str) -> None:
        """消费 SQS 消息并派发到对应 Agent 执行器"""

    async def handle_analysis(msg: AnalysisJobMessage) -> None
    async def handle_generation(msg: GenerationJobMessage) -> None
    async def handle_critique(msg: CritiqueJobMessage) -> None
    async def handle_consistency(msg: ConsistencyJobMessage) -> None
    async def handle_moderation(msg: ModerationJobMessage) -> None
```

---

## C-06 IngestionModule

```python
class IngestionService:
    async def upload(team_id, user_id, file: UploadFile) -> NovelSummary
    async def start_download(team_id, user_id, title: str) -> JobRef
    async def start_crawl(team_id, user_id, url: str) -> JobRef
    async def parse_file(content: bytes, fmt: FileFormat) -> Markdown
    async def split_chapters(md: Markdown) -> List[Chapter]
    async def list_novels(team_id) -> List[NovelSummary]
    async def get_novel(team_id, novel_id) -> NovelDetail
    async def delete_novel(team_id, novel_id) -> None
```

---

## C-07 UnderstandingAgent

```python
class UnderstandingAgentGroup:
    async def run(team_id, novel_id) -> AnalysisReport

# Sub-agents
class RoughReadSubAgent:
    async def sample(novel: NovelDetail) -> List[ChapterSample]   # 首尾+等间距

class ClassificationSubAgent:
    async def classify(samples: List[ChapterSample]) -> List[TagWithConfidence]

class CharacterSubAgent:
    async def extract(chapter: Chapter, running_memory: Memory) -> CharacterUpdate

class MapSubAgent:
    async def extract(chapter: Chapter, running_memory: Memory) -> MapUpdate

class StyleSubAgent:
    async def analyze(samples: List[ChapterSample]) -> StyleVector

class DeepReadSubAgent:
    async def process_chapter(chapter: Chapter, running_memory: Memory) -> ChapterFacts
    async def process_all(novel: NovelDetail, concurrency: int) -> None
```

---

## C-08 GenerationAgent

```python
class OutlineAgent:
    async def generate(novel_id, mode: Mode, style: StyleVector, n_chapters: int) -> Outline

class ChapterAgent:
    async def generate_stream(novel_id, gen_id, chapter_idx: int, outline: Outline,
                              memory: Memory, style: StyleVector) -> AsyncIterator[TextDelta]
    async def rewrite_stream(novel_id, gen_id, chapter_idx: int,
                             user_prompt: str | None) -> AsyncIterator[TextDelta]

class SelfCritiqueAgent:
    async def critique(chapter_text: str, memory: Memory) -> CritiqueNote
```

---

## C-09 CriticAgent

```python
class CriticAgent:
    async def evaluate(chapter_text: str, memory: Memory, style: StyleVector,
                       outline_item: OutlineItem) -> CriticReport
    # CriticReport = [Issue{severity, category, segment_range, suggestion}]
```

---

## C-10 ConsistencyAgent

```python
class ConsistencyAgent:
    async def scan(team_id, gen_id, since_chapter: int, until_chapter: int) -> ConsistencyReport
    # 触发器：每生成 N 章（admin 可配）
```

---

## C-11 ModerationAgent

```python
class ModerationAgent:
    async def flag(chapter_text: str) -> List[FlaggedSegment]
```

---

## C-12 MemoryFacade

```python
class MemoryFacade:
    # AgentCore Memory
    async def remember(team_id, novel_id, facts: List[Fact]) -> None
    async def recall(team_id, novel_id, query: str, top_k: int = 20) -> List[Fact]
    async def get_character(team_id, novel_id, character_id: str,
                            at_chapter: int | None = None) -> CharacterSnapshot

    # Neptune 知识图谱
    async def upsert_graph(team_id, novel_id,
                           nodes: List[GraphNode], edges: List[GraphEdge]) -> None
    async def neighbors(team_id, novel_id, node_id: str, edge_type: str | None = None,
                        depth: int = 1) -> List[GraphNode]
    async def shortest_path(team_id, novel_id, from_id: str, to_id: str) -> List[GraphNode]

    # OpenSearch 向量检索
    async def index_vector(team_id, novel_id, chunk_id: str,
                           embedding: Vector, payload: dict) -> None
    async def search_similar(team_id, novel_id, embedding: Vector, top_k: int = 10,
                             filters: dict | None = None) -> List[VectorHit]
    async def hybrid_search(team_id, novel_id, query_text: str, query_embed: Vector,
                            top_k: int = 10) -> List[VectorHit]

    # Embeddings
    async def embed(text: str) -> Vector
```

---

## C-13 WorkflowOrchestrator (Step Functions definitions)

```
- arn:aws:states:...:stateMachine:AnalysisWorkflow
- arn:aws:states:...:stateMachine:OutlineWorkflow
- arn:aws:states:...:stateMachine:ChapterWorkflow
- arn:aws:states:...:stateMachine:ConsistencyWorkflow
```

每个 State Machine 的状态定义在 CDK 中声明（Amazon States Language）。

---

## C-14 AdminModule

```python
class AdminService:
    # users/teams
    async def list_users(filters: UserFilter) -> List[User]
    async def create_team(payload: TeamCreate) -> Team
    async def update_team_members(team_id, members: List[Member]) -> Team

    # tags & schemas
    async def list_tags() -> List[Tag]
    async def merge_tags(from_tag: str, to_tag: str) -> None
    async def upsert_schema(schema: AnalysisSchema) -> AnalysisSchema

    # model config
    async def get_model_config() -> ModelConfig
    async def update_model_config(cfg: ModelConfig) -> ModelConfig
    # ModelConfig keys: 9 stages (classification/character/map/style/outline/chapter/self_critique/critic/consistency)
    # Values: {model: "anthropic.claude-opus-4-7" | ..., fallback: "..."}

    # concurrency (AD6=F)
    async def get_concurrency_config() -> ConcurrencyConfig
    async def update_concurrency_config(cfg: ConcurrencyConfig) -> ConcurrencyConfig
    # ConcurrencyConfig: {deep_read_max: int, dynamic_enabled: bool}

    # metrics & audit
    async def get_metrics(window: str) -> MetricsPayload
    async def list_audit_events(filters: AuditFilter, limit: int = 100) -> List[AuditEvent]
    async def upsert_alert(rule: AlertRule) -> None
```

---

## C-15 AuthAdapter

```python
class AuthAdapter:
    async def verify_jwt(token: str) -> Principal
    # Principal = {user_id, team_id, roles: List[str], email}

    async def get_workload_token(agent_id: str, resource: str) -> str
    # 调用 AgentCore Identity 获取下游工具的 OAuth token

    # FastAPI decorator
    require_team_access()        # 校验 request path/body 中 team_id 与 principal.team_id 一致
    require_role(role: str)      # 例如 "admin" / "moderator"
```

---

## C-16 StorageAdapter

```python
# S3
class S3Adapter:
    async def put_object(team_id, key, body: bytes | IO) -> S3Ref
    async def get_object(team_id, key) -> bytes
    async def presign_get(team_id, key, expires: int = 1800) -> str
    async def presign_put(team_id, key, expires: int = 1800) -> str
    # 所有方法强制 key 前缀以 teams/{team_id}/ 开头

# DynamoDB（单表设计）
class DynamoDBAdapter(Generic[T]):
    async def put(team_id, entity: T) -> None
    async def get(team_id, pk, sk) -> T | None
    async def query(team_id, pk, sk_prefix: str | None = None, limit: int = 50) -> List[T]
    async def update(team_id, pk, sk, patch: dict) -> T
    async def delete(team_id, pk, sk) -> None
    # 所有方法 runtime 断言 pk 以 team_id 前缀开头
```

---

## C-17 ObservabilityAdapter

```python
class ObservabilityAdapter:
    log(level, message, **fields)              # 结构化日志
    metric(name, value, unit, dimensions)       # CloudWatch EMF
    trace(segment_name)                         # X-Ray context manager
    start_agent_span(agent_id, model, prompt_tokens)  # AgentCore Observability
    record_token_usage(team_id, stage, model, input_tokens, output_tokens)
```

---

## 共享类型摘要

```python
# identity
Principal          {user_id, team_id, roles}
# novel
NovelSummary       {novel_id, title, chapter_count, word_count, status, updated_at}
NovelDetail        = NovelSummary + chapters: List[Chapter]
Chapter            {idx, title, content_md, word_count}
# job
JobRef             {job_id, type, state_machine_arn}
JobStatus          {job_id, status, progress, started_at, ended_at, error?}
# analysis
AnalysisReport     {tags: [Tag], characters: [Character], map_graph: GraphSummary, style: StyleVector}
# generation
Mode               enum {ORIGINAL_STYLE, CONTINUATION}
StyleVector        6-dim {tone, pace, detail_density, dialogue_ratio, emotion, scope}
Outline            {characters: [...], main_line: str, chapters: [OutlineItem]}
# review
CritiqueReport     List[Issue{severity, category, segment_range, suggestion}]
# admin
ModelConfig        Map[stage, {model, fallback}]
ConcurrencyConfig  {deep_read_max: int, dynamic_enabled: bool}
```
