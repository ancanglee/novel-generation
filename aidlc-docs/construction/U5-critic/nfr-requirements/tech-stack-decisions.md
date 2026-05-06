# U5 Tech Stack Decisions

**Unit**：U5 Critic & Consistency
**日期**：2026-04-28

U5 继承 U1-U4 技术栈。本文记录 U5 新增。

---

## 1. Bedrock 模型映射

| Stage | 默认模型 | 理由 |
|---|---|---|
| `critic` | **Claude Opus 4.7** | 复核模式需要深度推理 |
| `consistency` | **Claude Sonnet 4.6** | 事实比对任务，不需要 Opus |

均继承 U1 ModelConfig，admin 可覆盖。

---

## 2. Worker 规格

复用 U1 预建：
- `worker-critic` ECS Service
- `worker-consistency` ECS Service

无新建。镜像中加入 U5 agents 代码。

---

## 3. Python 依赖

继承 U3/U4。无新增。

---

## 4. Docker 镜像

- Base：python:3.12-slim
- 与 U3/U4 worker 相同 base 层（共用缓存）
- 预估 ~280 MB

---

## 5. 与其他 Unit 接口

- 消费 U4：EventBridge `generation.chapter.completed`
- 消费 U3：MemoryFacade.recall / get_character / neighbors
- 向 U6：EventBridge `critic.report_ready` / `consistency.report_ready` → 复用 U4 SseRelay
- 向 U4：`POST /generations/{gid}/chapters/{n}/rewrite`（用户点击 Rewrite 时由 ApiService 转调）
- 向 U7：Admin metric 聚合

---

## 6. 未决项（Infra Design 处理）

- critic-queue / consistency-queue 的 visibility timeout（U1 预定义 360s）是否足够
- 重写循环保护的计数器存储（DDB ConflictItem.rewrite_attempts 字段）
- CriticAgent prompt 模板的 few-shot 示例选择
