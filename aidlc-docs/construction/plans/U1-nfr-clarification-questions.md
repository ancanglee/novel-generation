# U1 NFR Clarification Questions

答案中发现 2 个需要确认的组合问题 + 1 个提醒。请回答后回复"done"。

---

## Clarification N1+N12 — 轻量规模与无预算上限的组合

你选 N1=A（< 50 用户轻量规模）与 N12=D（不设预算上限）。两者可共存，但需要确认选型倾向：

A) **小规模 + 高规格**：虽然用户少，但基础设施按中等规模配置（Neptune 小实例、OpenSearch Serverless 2 OCU 起、ECS Fargate 预留容量），确保体验流畅、未来可扩展；月度预算预计 $1500-3000 ✓
B) **小规模 + 按需伸缩**：全用 serverless/按需（DynamoDB on-demand、Neptune Serverless、OpenSearch Serverless 最小值、ECS Fargate Spot 为主），成本随使用量变化；空闲时 $400-800，活跃时 $1500-2500
C) **小规模 + 最低规格**：每项资源都选最小可用规格，$300-600/月，性能可能受限
D) Other (please describe after [回答]： tag below)

[回答]： B

---

## Clarification N9 — 不限流的风险确认

你选 N9=A（不限流）。这意味着：
- 单个恶意/失控用户可能消耗大量 Bedrock token
- 单个 bug 死循环可能迅速产生高额账单
- 无 API 层防护，Worker 层也不做 token 预算熔断

请确认你接受这个风险，或选择一个轻量保护方案：

A) **完全不限流**（现状，接受所有风险） ✓（你之前的选择）
B) **完全不限流 + 仅发射 metric 告警**：不阻止调用，但超过阈值时 CloudWatch 告警给 admin 通知（最低保护）
C) **完全不限流 + 每 Job 软 token 预算**：单个 Job 超过 token 预算时 Worker 自动停止并标记 FAILED；admin 可调阈值
D) Other (please describe after [回答]： tag below)

[回答]： B

---

## 提醒 N4 — 认证延迟放宽的含义

你把 N4 从推荐的 A（p99 50ms）改为 B（p99 200ms）。这没有实际冲突，但意味着：
- AuthAdapter 的 JWKs 缓存可以实现得稍简单（例如不必做异步预热）
- 但要注意：在并发高峰时，200ms 的 p99 累积在一个请求链路上（BFF→Api→Worker 可能多次鉴权）可能放大

这只是提醒，不需回答。如无异议继续。
