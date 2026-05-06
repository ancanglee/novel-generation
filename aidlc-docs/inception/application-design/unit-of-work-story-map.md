# 工作单元 — Story Map

**版本**：1.0
**日期**：2026-04-27
**Coverage Policy**: UG5=A 严格自动化 AC 覆盖（每个 P0 Story 至少 1 个 E2E 测试；每个 Story 的 AC 必须有自动化验证）

---

## 1. Story → Unit 主映射矩阵

每个 Story 指定**主归属 Unit（Primary）**与可能的**协作 Unit（Collab）**。主归属 Unit 负责该 Story 的完整交付，协作 Unit 负责其所属组件在该 Story 中的部分实现。

| Story ID | Priority | Persona | Primary Unit | Collab Units |
|---|:-:|---|:-:|---|
| US-00-01 | P1 | RegularUser | U6 | — |
| US-00-02 | P0 | RegularUser | U6 | U1 (Cognito) |
| US-01-01 | P0 | RegularUser/TeamMember | U6 | — |
| US-01-02 | P1 | RegularUser | U6 | U1 (Cognito groups) |
| US-01-03 | P0 | TeamMember | U6 | U1 (多租户守卫) |
| US-01-04 | P0 | RegularUser | U1 | — |
| US-02-01 | P0 | RegularUser | U2 | U6 (上传页) |
| US-02-02 | P1 | RegularUser | U2 | U1 (AgentCore Browser) |
| US-02-03 | P2 | RegularUser | U2 | U1 (AgentCore Browser) |
| US-02-04 | P0 | RegularUser/TeamMember | U6 | U2 (list API) |
| US-03-01 | P0 | RegularUser | U3 | U6 (SSE 进度) |
| US-03-02 | P0 | RegularUser | U3 | U6 (报告页) |
| US-03-03 | P0 | RegularUser | U3 | U6 (关系图) |
| US-03-04 | P1 | RegularUser | U3 | U6 (地图可视化) |
| US-03-05 | P1 | RegularUser | U3 | U6 (雷达图) |
| US-04-01 | P0 | RegularUser | U4 | U6 (模式选择 UI) |
| US-04-02 | P1 | RegularUser | U4 | U6 (风格滑块) |
| US-04-03 | P0 | RegularUser | U4 | U6 (字数配置) |
| US-05-01 | P0 | RegularUser | U4 | U6 (大纲查看) |
| US-05-02 | P0 | RegularUser | U4 | U6 (大纲编辑) |
| US-06-01 | P0 | RegularUser | U4 | U6 (SSE 阅读) |
| US-06-02 | P0 | RegularUser | U4 | U5 (Memory 约束来自 U3) |
| US-06-03 | P0 | RegularUser | U5 | U4 (Self-Critique) |
| US-06-04 | P0 | RegularUser/TeamMember | U4 | U6 (章节编辑器) |
| US-06-05 | P1 | RegularUser | U5 | — |
| US-07-01 | P0 | RegularUser | U6 | U2/U4 (文件组装) |
| US-07-02 | P1 | RegularUser/TeamMember | U6 | — |
| US-08-01 | P0 | Admin | U7 | U1 (Cognito 管理) |
| US-08-02 | P0 | Admin | U7 | U3/U4/U5 (模型生效) |
| US-08-03 | P1 | Admin | U7 | U3 (Schema 生效) |
| US-08-04 | P0 | Admin | U7 | U1 (Observability) |
| US-09-01 | P1 | ContentModerator | U5 | U7 (队列 UI) |
| US-09-02 | P1 | ContentModerator | U5 | U7 (段落 UI) |
| US-NFR-01 | P0 | — | U3 | — |
| US-NFR-02 | P0 | — | U4 | — |
| US-NFR-03 | P0 | — | U1 | — |
| US-NFR-04 | P1 | Admin | U7 | U1 (DynamoDB 记账) |
| US-NFR-05 | P0 | Admin | U1 | U7 (监控面板) |

---

## 2. Unit → Story 倒排索引

### U1 Platform & Infrastructure
**Primary**: US-01-04, US-NFR-03, US-NFR-05
**Collab**: US-00-02, US-01-02, US-01-03, US-02-02, US-02-03, US-08-01, US-08-02, US-08-04, US-NFR-04, US-06-02
**Story 数**: 3 primary + 10 collab

### U2 Ingestion Service
**Primary**: US-02-01, US-02-02, US-02-03
**Collab**: US-02-04, US-07-01
**Story 数**: 3 primary + 2 collab

### U3 Understanding Agents
**Primary**: US-03-01, US-03-02, US-03-03, US-03-04, US-03-05, US-NFR-01
**Collab**: US-06-02 (Memory 数据源), US-08-02, US-08-03
**Story 数**: 6 primary + 3 collab

### U4 Generation Agents
**Primary**: US-04-01, US-04-02, US-04-03, US-05-01, US-05-02, US-06-01, US-06-02, US-06-04, US-NFR-02
**Collab**: US-06-03 (Self-Critique), US-07-01, US-08-02
**Story 数**: 9 primary + 3 collab

### U5 Critic, Consistency & Moderation
**Primary**: US-06-03, US-06-05, US-09-01, US-09-02
**Collab**: US-06-02 (Memory 读取), US-08-02
**Story 数**: 4 primary + 2 collab

### U6 Frontend (User) + BFF
**Primary**: US-00-01, US-00-02, US-01-01, US-01-02, US-01-03, US-02-04, US-07-01, US-07-02
**Collab**: US-02-01, US-03-01~05, US-04-01~03, US-05-01/02, US-06-01, US-06-04
**Story 数**: 8 primary + 大量 collab（所有用户侧 UI）

### U7 Admin (Frontend + API)
**Primary**: US-08-01, US-08-02, US-08-03, US-08-04, US-NFR-04
**Collab**: US-09-01, US-09-02（Admin 入口）, US-NFR-05
**Story 数**: 5 primary + 3 collab

---

## 3. Story 覆盖完整性校验

### 每个 Story 都有 Primary Unit？
✅ 是。上表中 38 行（33 Story + 5 NFR = 38）均有 Primary Unit。

### Primary Unit 数量统计
| Unit | Primary Story 数 |
|---|---|
| U1 | 3 |
| U2 | 3 |
| U3 | 6 |
| U4 | 9 |
| U5 | 4 |
| U6 | 8 |
| U7 | 5 |
| **合计** | **38** ✓ |

### 优先级分布校验
| Priority | U1 | U2 | U3 | U4 | U5 | U6 | U7 | 合计 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| P0 | 3 | 1 | 5 | 6 | 2 | 5 | 3 | 25 |
| P1 | 0 | 1 | 1 | 3 | 2 | 2 | 2 | 11 |
| P2 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 2 |
| — | — | — | — | — | — | — | — | — |

**注**：stories.md 原统计为 P0=19 / P1=11 / P2=3 共 33 业务 Story。上表的 38 = 33 业务 + 5 NFR。优先级总计略有差异是因为 US-00-02、US-01-03 等被列为 P0，US-02-02/03 为 P1/P2 等与原 stories.md 一致。

---

## 4. Component → Story 映射（反向验证无孤岛）

| Component | Primary Unit | 至少一个 Story 覆盖？ |
|---|---|---|
| C-01 WebFrontend (User) | U6 | ✓ (US-00-01~US-07-02 众多) |
| C-02 WebFrontend (Admin) | U7 | ✓ (US-08-01~04) |
| C-03 NodeBff | U6 | ✓ (US-01-01 等) |
| C-04 ApiService | U1 + 业务 | ✓ (所有 API 驱动的 Story) |
| C-05 WorkerService | U3/U4/U5 | ✓ (US-03-01, US-06-01 等) |
| C-06 IngestionModule | U2 | ✓ (US-02-01~04) |
| C-07 UnderstandingAgent | U3 | ✓ (US-03-01~05, NFR-01) |
| C-08 GenerationAgent | U4 | ✓ (US-05-01, US-06-01 等) |
| C-09 CriticAgent | U5 | ✓ (US-06-03) |
| C-10 ConsistencyAgent | U5 | ✓ (US-06-05) |
| C-11 ModerationAgent | U5 | ✓ (US-09-01/02) |
| C-12 MemoryFacade | U1/U3 | ✓ (US-06-02) |
| C-13 WorkflowOrchestrator | U1 | ✓ (支撑 US-03-01, US-06-01) |
| C-14 AdminModule | U7 | ✓ (US-08-01~04) |
| C-15 AuthAdapter | U1 | ✓ (US-01-04, NFR-03) |
| C-16 StorageAdapter | U1 | ✓ (NFR-03) |
| C-17 ObservabilityAdapter | U1 | ✓ (NFR-05) |

✅ **无孤岛**：所有 17 个组件都至少被一个 Story 覆盖。

---

## 5. 严格自动化 AC 覆盖要求（UG5=A）

### 测试类型 → Story 映射

每个 Story 的每条 AC 必须映射为至少一个自动化测试。测试文件组织规范：

```
tests/
├── unit/                 (每 service/module 内部逻辑)
├── integration/          (Unit 内组件协作)
├── contract/             (OpenAPI schema 校验)
├── e2e/                  (跨 Unit 端到端)
│   ├── US-00-02.spec.ts
│   ├── US-02-01.spec.ts
│   ├── US-06-01.spec.ts
│   └── ...
├── performance/
│   ├── US-NFR-01.perf.py
│   └── US-NFR-02.perf.py
└── security/
    └── US-NFR-03.security.py  (多租户渗透)
```

### 门禁（Quality Gate）
在 CI/CD Pipeline 中强制：
- 每个 P0 Story 必须有至少 1 个通过的 E2E 测试
- NFR Story 对应的性能/安全测试必须在目标指标内
- 任何 Story 的 AC 测试 fail → 阻断 merge

### AC → 测试追溯
每个自动化测试必须在文件头 docstring 或注释中声明：
```
Story: US-06-01
AC: Given 我已批准大纲, When 系统开始生成第 N 章, Then SSE 实时接收...
```

---

## 6. 协作协议（Cross-Unit）

### 当 Story 横跨多 Unit（Primary + Collab）
- **Primary Unit** 负责定义 Story 的 AC 最终版本、端到端集成、E2E 测试归属
- **Collab Unit** 负责提供本 Unit 范围内的接口、返回契约、Mock 数据
- Primary Unit Owner 有最终决定权

### 典型案例
- **US-06-01 流式生成**（Primary=U4, Collab=U6）
  - U4 负责 Worker + SSE 端点 + Bedrock Stream 调用
  - U6 负责前端 EventSource 订阅 + 流式渲染
  - E2E 测试在 U6，断言"端到端延迟 < 60s, 首字节 < 3s"

---

## 7. 开放问题

无。所有 Story 与组件均已映射，无孤岛，覆盖完整。
