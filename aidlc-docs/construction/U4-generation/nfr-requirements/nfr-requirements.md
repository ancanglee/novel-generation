# U4 Generation Agents — 非功能需求（NFR Requirements）

**Unit**：U4 Generation Agents
**阶段**：NFR Requirements
**日期**：2026-04-28
**Inheritance**: 继承 U1/U2/U3（region / 99.5% SLA / AWS managed 加密 / 无 API 限流 / token metric 告警 / 按需 serverless）

---

## 1. 性能

### NFR-1.1 流式章节延迟（N1=A）
- **TTFT（首字节）** < **3 秒**
- **单章 P95** < **60 秒**（3000 字）
- **整章 P99** < **90 秒**
- Bedrock `converse_stream` 天然满足首字节目标

### NFR-1.2 Cancel 响应时间（N2=B）
- 用户点 Cancel → Worker 关闭 stream **≤ 10 秒**
- 实现：`cancel_requested` 进程内 TTLCache 有效期 **8 秒**（比 N2 目标略严以留余量）
- 每个 Bedrock stream token 回调读缓存；缓存过期时去 DDB 读一次

### NFR-1.3 大纲 LLM 校验延迟（F3=B, N4=B）
- OutlineReviewAgent P95 < **2 分钟**
- 异步执行，不阻塞用户体验
- 超时则取消 Review 任务 + warning

### NFR-1.4 大纲生成延迟
- OutlineAgent（Opus 4.7）P95 < **5 分钟**（NFR-1 from requirements.md NFR-1.1 承诺）

### NFR-1.5 Self-Critique 延迟
- 单章 Critique（Sonnet 4.6）P95 < **15 秒**
- 非阻塞，章节生成后异步执行

---

## 2. 并发与可扩展性

### NFR-2.1 并发 Generation（N3=A）
- **无全局并发限制**
- 依赖 Bedrock RPS 自适应（AD6=F 动态并发）
- 依赖用户声明的高 Bedrock 配额

### NFR-2.2 章节串行（F8=A）
- 单 Generation 内章节**严格串行**（ChapterStateMachine Map state MaxConcurrency=1）
- 跨 Generation 间无串行约束

### NFR-2.3 Worker 规格
扩展 U1 `worker-generation` Service（U1 已预定义）：
- CPU 2048 / Memory 4096 MB
- FARGATE_SPOT 混合
- Auto Scaling：min 1 / max 5

---

## 3. 数据管理

### NFR-3.1 章节 S3 版本保留（N6=B）
- **保留最近 10 个版本**
- S3 Lifecycle Rule：`NoncurrentVersionExpiration` 保留最近 10 个版本
- 对应前缀：`teams/{tid}/generations/{gid}/chapters/`

### NFR-3.2 大纲 S3 版本保留
- 大纲按 `outline.v{N}.json` 独立 key 保存
- 无 lifecycle 限制（大纲 JSON 本身很小）

### NFR-3.3 重写上限（N5=A）
- 默认 **5 次**
- admin 可通过 SSM `/novelgen/{env}/config/chapter-rewrite-max` 调整

---

## 4. 可靠性

### NFR-4.1 流式中断恢复
- SSE 客户端用 `Last-Event-ID` 恢复
- ApiService 从 EventBridge 事件存档（7 天）回放最近事件

### NFR-4.2 重试策略
- Bedrock ThrottlingException → tenacity 指数退避（2s/4s/8s，最多 3 次）
- SFN Task 层面额外 Retry 2 次
- Self-Critique 失败：非致命，warning

### NFR-4.3 部分生成保存
- Cancel 时已流出的文本保存为 `partial.md`
- 用户可在 UI 查看或选择"继续生成"

---

## 5. 安全与合规

继承 U1/U2。U4 新增：
- Generation.owner_user_id 记录创建者；rewrite 操作写审计
- S3 presigned URL for export（U6/U7 使用）

---

## 6. 可观测（U4 新增 metric）

| Metric | 用途 |
|---|---|
| `ChapterTTFTMs` | 首字节延迟（P95 < 3000） |
| `ChapterGenerationMs` | 单章总耗时（P95 < 60000）|
| `CancelResponseMs` | Cancel 到 stream 关闭延迟 |
| `OutlineReviewDurationMs` | F3=B LLM 校验延迟 |
| `GenerationRetries` | 单章重试次数 |
| `RewriteCount` | 单章被用户打回次数 |
| `ConcurrentGenerations` | 当前 GENERATING 状态数 |

### 告警
| Alarm | 条件 |
|---|---|
| `U4ChapterTTFTHigh` | `ChapterTTFTMs` P95 > 3000 |
| `U4ChapterGenerationSlow` | `ChapterGenerationMs` P95 > 60000 |
| `U4CancelResponseSlow` | `CancelResponseMs` P95 > 10000 |

---

## 7. 成本

### NFR-7.1 单 Generation 成本估算
| 项 | 50 章 × 3000 字生成 |
|---|---|
| OutlineAgent（Opus 4.7 × 1） | ~$2 |
| ChapterAgent（Sonnet 4.7 × 50） | ~$15 |
| SelfCritiqueAgent（Sonnet 4.6 × 50） | ~$5 |
| Memory 召回（Titan embed × 50） | ~$0.1 |
| OutlineReviewAgent（F3=B 异步） | ~$0.5（用户编辑才触发） |
| **合计** | **~$22-23** |

---

## 8. 继承 U1/U2/U3 的 NFR（不重复）

- us-east-1 / 99.5% SLA / 按需 serverless
- AWS managed KMS + TLS 1.2+
- CloudWatch + AgentCore Observability
- 手动部署
- MemoryFacade 三后端 + 分层降级（U3 提供）
