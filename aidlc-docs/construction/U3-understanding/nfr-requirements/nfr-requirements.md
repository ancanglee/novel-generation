# U3 Understanding Agents — 非功能需求（NFR Requirements）

**Unit**：U3 Understanding Agents
**阶段**：NFR Requirements
**日期**：2026-04-28
**Inheritance**: 继承 U1 + U2（region / 99.5% SLA / AWS managed 加密 / 无 API 限流 / token metric 告警 / 按需 serverless）

---

## 1. 性能（U3 特有）

### NFR-1.1 分析延迟（N1=A 统一目标，C2=B 对所有规模承诺）
- **所有规模统一目标：端到端 < 15 min**（P95）
- 前提假设：账号已预先配置高 Bedrock Claude Sonnet 配额（用户声明已有）
- 细分：
  - 粗读：< 2 min
  - 细读（每章 1 次 Bedrock 调用 + Memory 写入）：并发处理下总时长 < 10 min
  - AnalysisReport 汇总：< 1 min

### NFR-1.2 Neptune Serverless 性能（N3=B + C1=C）
- **延迟目标**：
  - upsert p95 < 200ms
  - 邻居查询（depth=1）p95 < 300ms
- **NCU 配置（C1=C）**：保持最小 1 NCU（U1 默认）
- **权衡**：冷启动或突发流量可能偶尔违反 SLA；接受风险换取 $150/月 的成本节约
- 缓解：MemoryFacade 层针对 Neptune 失败做降级（R9.1）

### NFR-1.3 OpenSearch 向量检索（N4=A）
- kNN top_k=20 查询 p95 < **300ms**
- 混合检索（BM25 + kNN，RRF 合并）p95 < 500ms
- 嵌入生成（Titan V2 调用）p95 < 200ms

### NFR-1.4 Bedrock 配额（N2=A, C3=A）
- 使用默认配额 + AD6=F 动态并发
- **前提**：账号已预先具备 Claude Sonnet 4.6/4.7 + Haiku 4.5 的高 RPS 配额（用户声明）
- 监控：`BedrockErrorRate` metric + CloudWatch Alarm（U1 已定义）
- 应急：若 throttle 率持续 > 2%，动态并发自动降至 1

### NFR-1.5 Supervisor 决策延迟
- 单次 Supervisor 决策（调用 Opus 4.7 并获得工具调用）p95 < 3s
- 决策数上限 50 次/小说（R1 已定义），总 Supervisor 耗时 < 150s

---

## 2. 可靠性

### NFR-2.1 Supervisor Checkpoint（N5=A 每 5 步）
- 每 5 步写一次 checkpoint 到 `novelgen_jobs` 表 SK=`CHECKPOINT#{job_id}`
- 被 Spot 回收后从最近 checkpoint 恢复，最多丢失 5 步
- Checkpoint 内容：partial_results + step_history + current_goal

### NFR-2.2 单章重试预算（N7=B 3 次）
- 单章 `extract_chapter_all` 失败（LLM 异常 / JSON schema 校验失败）→ 重试 3 次
- 重试策略：指数退避 2s / 4s / 8s
- 3 次耗尽 → 该章标记 partial，Job 继续；最终 Report 标注 warning

### NFR-2.3 MemoryFacade 分层降级（F8=A）
- AgentCore Memory 失败 → 致命（Job FAILED）
- Neptune 失败 → warning + metric，业务继续
- OpenSearch 失败 → warning + metric，业务继续
- Circuit Breaker：Neptune 连续 5 次失败 → 熔断 30s

---

## 3. 可扩展性

### NFR-3.1 并发小说数
- 单 Worker 处理 1 本小说（asyncio 内可能多章并行）
- Auto Scaling：min 1 / max 5 Worker（U1 预留）
- **理论并发上限**：5 × 每小说 ~50 次 Bedrock 调用的峰值 RPS ≈ 250 RPS 峰值

### NFR-3.2 章节规模
- 单章最大字数：50,000 字（超过视为切分不充分，发 warning）
- 单次 `extract_chapter_all` prompt 输入 ≤ 80KB（含 Memory 召回的事实）

---

## 4. 安全

继承 U1 + U2。U3 无新增安全需求。

- 多租户：MemoryFacade 三层 filter（namespace + property + filter）
- IAM：worker-analysis 需要新增 Neptune / OpenSearch / Titan Embeddings 权限

---

## 5. 可观测

### NFR-5.1 Agent 追踪
- AgentCore Observability 采集每 sub-agent 调用链路
- 每 Bedrock 调用注入 request_id 到 trace
- Supervisor 决策链路可在 admin 后台重放

### NFR-5.2 关键 metric（U3 新增）
| Metric | 用途 |
|---|---|
| `AgentSpanDurationMs{agent, model}` | 每 sub-agent 耗时分布 |
| `SupervisorStepCount{job_id}` | Supervisor 决策数（防飘移）|
| `MemoryWriteFailure{Layer}` | 分层降级统计 |
| `ChapterProcessingMs` | 单章细读耗时 |
| `LlmInvocationCount{stage}` | 按阶段 LLM 调用数 |
| `NeptuneLatencyMs{op}` | upsert / query 延迟 |
| `OpenSearchLatencyMs{op}` | index / knn 延迟 |
| `EmbeddingCacheHitRate` | Titan 嵌入缓存命中率 |

### NFR-5.3 告警
| Alarm | 条件 |
|---|---|
| `U3AnalysisTimeoutP95` | 分析 P95 > 15 min |
| `U3SupervisorDrift` | SupervisorStepCount > 40（接近 50 上限警告） |
| `U3MemoryWriteFailureHigh` | Neptune/OpenSearch 失败率 > 5%（5 min）|
| `U3NeptuneSlowUpsert` | Neptune upsert p95 > 500ms |
| `U3ChapterPartialRateHigh` | 章节 partial 率 > 10%（Job 内）|

---

## 6. 成本

### NFR-6.1 单小说分析成本估算
| 项目 | 100 万字小说 |
|---|---|
| 粗读（Claude Sonnet 4.6/4.7）| ~6 次调用，~20k tokens → ~$0.30 |
| 细读（Sonnet 4.7 × 300 章 × 1 次）| ~300 次调用，~800k tokens → ~$12 |
| Supervisor 决策（Opus 4.7）| ~20 次调用，~60k tokens → ~$3 |
| Titan Embeddings V2 | ~30k 向量 × 1024 维 → ~$0.03 |
| Neptune / OpenSearch 写入 | 按需付费，< $0.10 |
| **单小说总成本** | **~$15.40** |

### NFR-6.2 成本护栏
- U1 已定义的 `JobTokenSpike` alarm（> 200k tokens/job）继续生效
- 新增：`U3SingleNovelCostHigh`（按 tokens 计算换算成本 > $30）

---

## 7. 文档嵌入

### NFR-7.1 Titan Embeddings V2 配置（N6=A）
- 维度：**1024**
- 归一化：normalize=true（便于余弦相似度）
- 每小说平均向量数：~30k
- 每本存储：~120 MB OpenSearch

### NFR-7.2 缓存
- 进程内 LRU 缓存（key = sha256(text)）
- 缓存大小：1000 条
- 预期命中率：> 30%（Memory 召回时同一文本多次嵌入）

---

## 8. 继承 U1 + U2 的 NFR（不重复声明）

- us-east-1 / 99.5% SLA / 不做 DR
- AWS managed KMS 加密 + TLS 1.2+
- 无 API 限流，token metric 告警
- CloudWatch + AgentCore Observability（不引入 X-Ray）
- 手动部署
- 按需 serverless 主基调（U3 接受 Neptune 1 NCU 基础配置）

---

## 9. 约束与假设

1. Bedrock Claude Sonnet / Haiku / Opus 配额已预先提升（用户声明，C2=B + C3=A 基础）
2. Neptune Serverless 在 us-east-1 GA
3. OpenSearch Serverless Vector Search Collection 已在 U1 DataStack 创建
4. AgentCore Memory SDK 可用
5. Strands Agents 框架可在 Python 3.12 + AgentCore Runtime 上运行
