# U5 Critic & Consistency — 非功能需求（NFR Requirements）

**Unit**：U5 Critic & Consistency
**阶段**：NFR Requirements
**日期**：2026-04-28
**Inheritance**: 继承 U1/U2/U3/U4

---

## 1. 性能

### NFR-1.1 Critic 延迟（N1=B 宽松）
- 单章 Critic P95 < **60 秒**
- 首字节无要求（非流式）

### NFR-1.2 Consistency 延迟（N2=B 宽松）
- 每次扫描 P95 < **4 分钟**
- 默认 10 章一次（SSM 可配）

### NFR-1.3 ConflictItem API 响应（N5=A）
- `POST /conflicts/{id}/ignore`：同步 < 200ms
- `POST /conflicts/{id}/rewrite`：202 Accepted 返回 job_id，< 500ms

---

## 2. 可靠性

### NFR-2.1 Critic 失败降级（N3=A）
- SFN Retry 3 次
- 耗尽写 minimal CritiqueReport（score=0, issue='critic_failed'）
- Chapter 状态保持 GENERATED，业务不阻断
- 用户可在 UI 手动触发重跑 Critic

### NFR-2.2 Consistency 失败降级
- Memory 不可用 → 仅文本 diff，Report 标 `memory_unavailable=true`
- LLM 超时 → SFN Retry 2 次，耗尽标 FAILED，可重跑

### NFR-2.3 重写循环保护
用户 Rewrite 一个 Conflict 后新章节触发 Critic + Consistency，新 Report 若产生同一 ConflictItem：
- 同一 `(conflict_type, chapter_range)` 连续 3 次出现 → 冻结，不再 rewrite，UI 提示"多次尝试未能解决"

---

## 3. 成本（N4=C 无硬上限）

### NFR-3.1 单 Generation 成本估算
| 项 | 50 章 |
|---|---|
| CriticAgent（Opus 4.7 × 50）| ~$30 |
| ConsistencyAgent（Sonnet 4.6 × 5）| ~$1 |
| Memory 召回（Titan embed + kNN）| ~$0.1 |
| **U5 合计** | **~$31** |

### NFR-3.2 成本护栏
- 无硬预算上限
- 依赖 U1 `JobTokenSpike` / `TeamHourlyToken` alarm
- Admin 可通过 U1 ModelConfig 将 Critic 降级到 Sonnet 4.7（~$0.3/章）

---

## 4. 并发

### NFR-4.1 无全局限制
与 U4 一致，依赖 Bedrock RPS 自适应。

### NFR-4.2 Critic / Consistency 独立扩展
- worker-critic ECS Service Auto Scaling（U1 已预定义）
- worker-consistency 同上

---

## 5. 数据管理

### NFR-5.1 Report 保留
- `CRITIQUE#` / `CONSISTENCY#` 项随 Generation 生命周期保留
- Generation 删除时级联删除

### NFR-5.2 ConflictItem user_action 状态追踪
- 用户操作（ignore/rewrite）写入审计日志

---

## 6. 可观测（U5 新增 metric）

| Metric | 用途 |
|---|---|
| `CriticDurationMs` P95 | < 60s |
| `ConsistencyDurationMs` P95 | < 240s |
| `CriticScore` by severity | 质量趋势 |
| `ConsistencyConflictCount` by conflict_type | 矛盾类型分布 |
| `ConflictResolutionRate` | Rewrite / (Rewrite + Ignore) |
| `CriticFailureCount` | 降级次数 |

### 告警
| Alarm | 条件 |
|---|---|
| `U5CriticDurationHigh` | P95 > 60s (5min 窗口)|
| `U5ConsistencyDurationHigh` | P95 > 240s |
| `U5CriticFailureRateHigh` | 失败率 > 5% |
| `U5ConflictLoopDetected` | 同一 ConflictItem 3+ 次 rewrite |

---

## 7. 安全与合规

继承 U1。U5 无新增安全需求。

---

## 8. 继承 U1/U2/U3/U4

- us-east-1 / 99.5% SLA / 按需 serverless
- AWS managed KMS + TLS 1.2+
- CloudWatch + AgentCore Observability
- 手动部署
- MemoryFacade 三后端 + 分层降级（U3 提供）

---

## 9. 未实现范围（F4=D/F6=C 决策）

- Moderation 延迟/成本：N/A
- ContentModerator UI 延迟：N/A
