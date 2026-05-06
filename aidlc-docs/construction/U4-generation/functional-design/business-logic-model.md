# U4 Business Logic Model

**Unit**：U4 Generation Agents
**阶段**：Functional Design
**日期**：2026-04-28

---

## Flow 1. 创建 Generation

**触发**：`POST /api/v1/generations`（body=mode / style / chapters / words / reference）

1. ApiService 校验参数、novel_id 所属 team
2. 创建 Generation 记录（status=DRAFT）
3. 返回 `{generation_id}`

---

## Flow 2. 大纲生成（US-05-01）

**触发**：用户点"生成大纲" → `POST /api/v1/generations/{gid}/outline`

1. API 启动 OutlineStateMachine（U1 Step Functions）
2. SFN → SQS(generation-queue) → Worker
3. Worker 调用 OutlineAgent（Opus 4.7）：
   - 输入：U3 分析报告 + mode + style_vector + target counts
   - 输出：Outline（main_plot + character_table + world_summary + items）
4. 写 S3 `outline.v1.json`
5. 更新 Generation.outline_s3_key, status=OUTLINE_READY
6. 发 EventBridge `generation.outline.ready`
7. ApiService SSE 推送给前端

---

## Flow 3. 用户编辑大纲 + LLM 校验（F3=B）

**触发**：`PUT /api/v1/generations/{gid}/outline` (body=修改后的 Outline)

1. API 校验用户权限 + version 冲突（乐观锁）
2. 写 S3 `outline.v{N+1}.json`
3. 发 `generation.outline.edited` 事件
4. 异步：OutlineReviewAgent 校验（Sonnet 4.6）
   - 对比 v(N-1) 与 vN 的差异
   - 输出 OutlineRevisionAdvice 列表
   - 写回 DynamoDB Generation.outline_advice
5. 前端轮询或 SSE 展示 advice（仅参考，不阻断）

---

## Flow 4. 大纲审批（US-05-02）

**触发**：`POST /api/v1/generations/{gid}/outline/approve`

1. 校验 status == OUTLINE_READY
2. 更新 Generation.outline_approved=true, status=APPROVED
3. 此时前端显示"开始生成"按钮

---

## Flow 5. 启动章节批量生成

**触发**：`POST /api/v1/generations/{gid}/start`

1. 校验 status == APPROVED
2. 启动 ChapterStateMachine（Map state over outline items, MaxConcurrency=1 for F8=A 串行）
3. 更新 status=GENERATING, current_chapter=1
4. 返回 `{job_id}`

---

## Flow 6. 单章流式生成（US-06-01）

**触发**：ChapterStateMachine Map state 每项

1. SFN → SQS(generation-queue) → Worker
2. Worker:
   a. 读 Outline.items[chapter_idx] + 前一章末尾 500 字
   b. `MemoryFacade.hybrid_search` 召回 20 条相关事实
   c. 构造 StyleInjectionBlock（F7=C：前缀 + 3 段相似风格片段）
   d. 按 mode 选择 prompt 模板（clean_room / continuation）
   e. Bedrock `converse_stream` 流式调用（Sonnet 4.7）
3. 每收到 text_delta：
   a. 检查 cancel_requested（TTLCache 5s）
   b. 为 true → 关闭 stream，标记 CANCELED，break
   c. 否则发 EventBridge `generation.chapter.streaming` with text_delta
4. stream 完成后：
   a. 组装完整文本，写 S3 `chapters/{idx:05d}.md`
   b. 更新 Chapter.status=GENERATED, word_count
   c. 发 EventBridge `generation.chapter.completed`
5. SFN SendTaskSuccess 继续下一章

**ApiService SSE 端点**：
- 订阅 EventBridge default bus，过滤 generation_id
- 为每个 event 分配 event_id，支持 Last-Event-ID 断线恢复

---

## Flow 7. Cancel（F6=A）

**触发**：`POST /api/v1/jobs/{job_id}/cancel`

1. API 写 DDB `jobs[job_id].cancel_requested=true`
2. API 返回 202（不等待确认）
3. Worker 在下一次 Bedrock stream callback 读 DDB（TTLCache 5s）
4. 读到 true → 关闭 stream，标记 Chapter.status=CANCELED，partial 内容保存
5. 发 EventBridge `generation.cancel_requested`
6. Generation.status 视剩余章节决定（全部 CANCELED 则 Generation.status=CANCELED）

---

## Flow 8. Self-Critique（F5=A）

**触发**：章节 `status=GENERATED` 后自动（EventBridge rule → SQS）

1. Worker 读完整章节文本 + Outline + StyleVector + Memory.recall
2. SelfCritiqueAgent（Sonnet 4.6）输出 CritiqueNote
3. 写入 Chapter.self_critique
4. 发 `generation.chapter.critique_ready`
5. 前端 SSE 展示评分 + 建议

---

## Flow 9. 章节重写（US-06-04）

**触发**：`POST /api/v1/generations/{gid}/chapters/{n}/rewrite` body=`{instruction}`

1. 校验 rewrite_count < max（默认 5）
2. 新建子 Job（job_type=CHAPTER_REWRITE）
3. Worker 读现有章节 + instruction → 重写
4. S3 新版本写入（保留历史版本）
5. rewrite_count += 1
6. 更新 Chapter.status=GENERATED（重新走 Self-Critique 流程）

---

## Flow 10. 全书完成

**触发**：所有 Chapter status ∈ {APPROVED, COMPLETED}

1. Generation.status = COMPLETED
2. 发 `generation.completed`
3. 可选：自动触发 U5 全书一致性校验
4. 通知用户（SNS / 应用内）

---

## Flow 11. 派发给 U5（Critic + Moderation）

**触发**：`generation.chapter.completed`

由 U5 的 EventBridge Rule 订阅：
- `critic-queue` → CriticAgent（Opus 4.7）→ 写 critique_report
- `moderation-queue` → ModerationAgent（Sonnet 4.6）→ 写 moderation flags

U4 不阻塞等待结果，继续下一章。
