# U4 Tech Stack Decisions

**Unit**：U4 Generation Agents
**日期**：2026-04-28

U4 继承 U1/U2/U3 技术栈。本文记录 U4 新增决策。

---

## 1. Bedrock Converse Stream API

| 方面 | 决策 |
|---|---|
| 流式接口 | `bedrock-runtime.converse_stream` |
| 客户端 | `aioboto3` 异步 |
| 默认模型 | Sonnet 4.7（ChapterAgent）|
| 可配置 | U1 ModelConfig 9 stage 的 `chapter` / `outline` / `self_critique` |

---

## 2. 流式事件发布

| 方面 | 决策 |
|---|---|
| 传输 | EventBridge default bus → ApiService SSE 端点中继 |
| 事件 ID | Worker 递增整数 + generation_id 拼接；支持 Last-Event-ID |
| 事件存档 | EventBridge Archive 7 天，支持重放 |
| 心跳 | ApiService SSE 每 15s 发 `heartbeat` 事件（对齐 U1 NFR 6.1）|

---

## 3. Cancel 机制

| 方面 | 决策 |
|---|---|
| 存储 | DDB `novelgen_jobs` 的 `cancel_requested` 字段（U1 Job schema 已有）|
| 进程缓存 | TTLCache(max=1000, ttl=8) —— 略严于 N2=B 的 10s |
| 写入 | API 层直接 update；幂等 |
| 检查 | Worker 每 Bedrock stream token 回调检查 |

---

## 4. 模式路由

| 方面 | 决策 |
|---|---|
| Mode Enum | `worker_generation/mode.py::Mode` |
| Prompts | `prompts/clean_room.md` / `prompts/continuation.md` |
| System prompt 构造 | `prompt = load_prompt(mode.value) + style_block + memory_context` |

---

## 5. Memory 使用

| 方面 | 决策 |
|---|---|
| 接口 | U3 MemoryFacade 导出的 `hybrid_search` / `recall` / `get_character` / `neighbors` |
| 失败处理 | 降级到空 facts + prompt 中标注警告（NFR-4.3 from U3） |

---

## 6. Python 依赖（U4 新增）

大部分与 U3 共用。新增：
```
sse-starlette~=2.1     # SSE server-side support（ApiService 路由新增）
aioitertools~=0.12     # 流式辅助
```

---

## 7. Worker

U4 扩展 U1 `worker-generation` Service（U1 已预建）：
- 镜像中加入 U4 代码（Chapter/Outline/SelfCritique agents）
- 无需新 Service 定义

---

## 8. 与其他 Unit 接口

| 方向 | 接口 |
|---|---|
| 消费 U3 | `MemoryFacade.hybrid_search / recall / get_character` |
| 消费 U1 | `Job.cancel_requested`、SSM `chapter-rewrite-max` 等 |
| 向 U5 | EventBridge `generation.chapter.completed` → critic-queue + moderation-queue |
| 向 U6 | EventBridge `generation.*` → ApiService SSE → Browser |

---

## 9. 未决项（Infra Design 处理）

- ChapterStateMachine 的完整 ASL（Map state + MaxConcurrency=1）
- ApiService SSE 端点的具体路径（`/api/v1/generations/{gid}/chapters/{n}/stream` vs `/api/v1/jobs/{id}/stream`）
- EventBridge Archive 启用与重放策略
