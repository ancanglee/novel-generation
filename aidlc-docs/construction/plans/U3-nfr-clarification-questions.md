# U3 NFR Clarification Questions

N3=B（严格 Neptune 延迟）与 N2=A（默认 Bedrock 配额）+ U1 NFR-9.2（按需 serverless）存在张力。请澄清。

---

## Clarification C1 — Neptune Serverless 最小容量

N3=B 要求 upsert p95 < 200ms / 查询 p95 < 300ms。这需要 Neptune 常驻较高 NCU，避免冷启动。三种实现方式：

A) **常驻最小 2 NCU**（NeptuneDB ServerlessConfig min_capacity=2.0）
  - 延迟：冷启动消失，upsert p95 ~150ms ✓
  - 成本：~$300/月 vs 原 1 NCU ~$150/月（+$150）

B) **常驻最小 4 NCU**（min_capacity=4.0）
  - 延迟：upsert p95 ~80ms，查询 p95 ~150ms（更稳）
  - 成本：~$600/月（+$450）

C) **保持最小 1 NCU（U1 默认）但接受 SLA 风险**
  - 延迟：冷启动时 p95 可能超过 200ms，偶尔违反 SLA
  - 成本：不变

D) Other (describe below)

[回答]： C

---

## Clarification C2 — N1 小说规模边界

N1=A 统一 < 15min 目标。这意味着：

A) **仅对 ≤ 100 万字小说承诺**：> 100 万字的情况用 best-effort，不承诺 SLA，UI 预先告知用户 ✓
B) **对所有规模严格 15min**：需要大幅提升 Bedrock 配额 + 并发
C) **改为 N1=B 分档**（推翻原答案）
D) 其他
[回答]： B. 我现有的配额很高，不用担心这个问题。

---

## Clarification C3 — 是否升级 N2 Bedrock 配额

N3=B 严格 Neptune 已引入额外成本。N2=A 保持默认配额但 100 万字分析在默认 RPS 下可能延迟。是否同时申请 Bedrock 配额提升？

A) **保持 N2=A 默认**：先观察 MVP 实际 throttle 率再决定 ✓
B) **改为 N2=B 申请配额提升**：提前申请 RPS=100，确保 N1 SLA 可达
C) 其他
[回答]： A.我现有的配额很高，不用担心这个问题。

---
