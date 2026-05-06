# 应用设计澄清问题（Application Design Clarification Questions）

在 AD1-AD10 的答案中，发现 AD6 未填内容 + AD4 需要确认一个小细节。请回答后告知"done"。

---

## Clarification AD6 — 细读阶段并发上限（补填）

你在 AD6 选择了 F (Other)，但 `[回答]：` 后面留空。请从下列选项重新选择或描述你的具体策略：

A) **固定并发 = 10**（保守）
B) **固定并发 = 20**
C) **固定并发 = 50**
D) **动态自适应**：从 10 起步，根据 Bedrock throttle 错误率自动调节上限（实现复杂但最智能）
E) **admin 可配置**（默认 50，admin 可在后台改）
F) **动态自适应 + admin 可配**（结合 D 和 E：admin 设置上限，实际运行按 throttle 状态在 [1, 上限] 之间自适应）
G) Other (please describe after [回答]： tag below)

[回答]： F

---

## Clarification AD4 — 章节生成的取消能力

你在 AD4 选了 A（纯 SSE）。SSE 是单向的（server → client），若用户想中途取消章节生成，需要一个额外的 REST 端点（例如 `POST /jobs/{jobId}/cancel`）。

请确认：

A) **接受增加 REST 取消端点**（SSE 流式推送 + REST 取消，两者并存）— 推荐，让用户可主动中止
B) **不需要取消功能**（纯 SSE，用户只能关闭页面让连接超时，后端不知用户意图继续烧 token）
C) Other (please describe after [回答]： tag below)

[回答]： A

---
