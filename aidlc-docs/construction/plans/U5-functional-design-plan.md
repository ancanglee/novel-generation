# U5 Critic, Consistency & Moderation — 功能设计计划

**Unit**：U5 Critic, Consistency & Moderation
**阶段**：Functional Design
**日期**：2026-04-28

---

## Unit Context

U5 承载 3 个后处理 Agent：
- **CriticAgent (Opus 4.7)** — Layer-2 章节级质量评审（FR-5.3）
- **ConsistencyAgent** — 每 N 章全局一致性校验（FR-6.3）
- **ModerationAgent** — 敏感内容预标（NFR-7 / US-09-01/02）

U5 消费 U4 `generation.chapter.completed` 事件，产出报告写入 DDB，Moderator UI 数据接口由 U7 消费。

## Stories
- Primary：US-06-03（双层 Critic Layer-2）/ US-06-05（周期性一致性）/ US-09-01（审核队列）/ US-09-02（段落级打回）
- Collab：US-06-04（重写时读 Critic 建议）/ US-08-04（Admin 监控 U5 指标）

---

## 第 1 部分 — 澄清问题（7 个）

### Question U5-F1 — CriticAgent 评审维度
U5 CriticAgent（Layer-2）与 U4 SelfCritique（Layer-1）的关系：

A) **互补评审**：Layer-2 着重跨章节一致性 + 整体风格漂移；不重复 Layer-1 的单章内部问题 ✓
B) **复核评审**：Layer-2 重新评审 Layer-1 的所有问题 + 补充新问题（冗余但全面）
C) **仅读 Layer-1 评审结果提建议**（便宜）
D) 其他
[回答]： B

### Question U5-F2 — Consistency 触发频率
R6.3 要求每 N 章一次全局校验：

A) **N=10**（每 10 章一次）✓
B) **N=5**（更频繁）
C) **N=20**（稀疏）
D) admin 可配置（默认 10）

[回答]： D

### Question U5-F3 — Consistency 检测范围
ConsistencyAgent 扫描什么？

A) **所有已生成章节 + Memory 全部 facts**（全量扫描，最严格）
B) **最近 N 章 + Memory 相关 facts**（增量，Memory 约束兜底）✓
C) **仅 Memory facts 间的冲突**（最便宜）
D) 其他
[回答]： B

### Question U5-F4 — Moderation 分类体系
ModerationAgent 敏感类别：

A) **固定 4 类**：SEXUAL / VIOLENCE / POLITICAL / MINORS（适合中文环境）✓
B) **扩展 8 类**：加入 HATE_SPEECH / SELF_HARM / ILLEGAL_ACTIVITY / PRIVACY
C) **AWS Comprehend Toxicity + 自定义分类**
D) 其他
[回答]： D. 不需要ModerationAgent。

### Question U5-F5 — Moderation 置信度阈值
低于多少置信度不进入审核队列？

A) **0.7**（高阈值，少噪声）✓
B) **0.5**（中阈值，更多召回）
C) **0.3**（低阈值，全部入队）
D) admin 可配置

[回答]： D

### Question U5-F6 — Critic / Moderation 之间的关系
两者是并行还是有先后？

A) **并行**（EventBridge fan-out，互不阻塞）✓
B) **串行**：先 Moderation，通过后才 Critic
C) 其他
[回答]： C，不需要Moderation

### Question U5-F7 — 修订建议的落库形式
Consistency 检测到矛盾后：

A) **写一份"矛盾清单"到 DDB**，用户在 UI 查看并决定是否重写章节 ✓
B) **自动触发对应章节 rewrite**（激进，可能反复循环）
C) 其他
[回答]： A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U5F-1: 生成 `domain-entities.md`（范围缩减：Critic + Consistency，移除 Moderation）
- [x] Step U5F-2: 生成 `business-rules.md`（2 agent 规则）
- [x] Step U5F-3: 生成 `business-logic-model.md`（Critic + Consistency + Conflict 处理 + 失败降级）
- [x] Step U5F-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- F1=A 互补评审
- F2=A N=10
- F3=B 增量扫描
- F4=A 4 类固定
- F5=A 0.7 阈值
- F6=A 并行
- F7=A 矛盾清单供用户决策
