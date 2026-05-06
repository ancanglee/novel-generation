# U6 Frontend (User) + BFF — 功能设计计划

**Unit**：U6 Frontend + BFF
**阶段**：Functional Design
**日期**：2026-04-28

---

## 上下文摘要
U6 范围：React SPA（apps/frontend-user）+ Node.js BFF（apps/bff-user）+ 共享 UI 库（packages/ui）+ API Client（packages/api-client-ts）。
继承 U1 Cognito、U2/U3/U4/U5 所有 API、SSE 事件。前端面向"普通用户 + team member"（非 admin）。

---

## 第 1 部分 — 澄清问题（7 个）

### Question U6-F1 — BFF 的核心职责
Node.js BFF（apps/bff-user）是否承担业务逻辑？

A) **纯反向代理 + Cognito 会话 Cookie 封装 + SSE 中继**（薄 BFF，无业务逻辑）✓
B) **聚合多个 ApiService 调用 + DTO 裁剪**（中等 BFF，降低前端请求数）
C) 完整业务分层（BFF 实现全部 API 调用编排）
D) 其他
[回答]：A

### Question U6-F2 — SSE 中继形式
从 ApiService 的 SSE 端点经 BFF 转发到浏览器：

A) **BFF 侧 HttpClient 开启上游 SSE 流 → 原样透传 SSE event 帧 + 附加 Cookie 鉴权**（透传）✓
B) **BFF 侧解析 SSE 事件 + 做业务转换 + 重新 serialize**（会引入延迟）
C) **浏览器直连 ApiService（跨 BFF）用 JWT Authorization**（BFF 仅管会话 Cookie）
D) 其他
[回答]：A

### Question U6-F3 — 章节生成页流式渲染方式
用户审阅生成中的章节时：

A) **逐 delta 拼接渲染 + 平滑滚动 + 光标闪烁**（完整流式体验，对齐 ChatGPT） ✓
B) **每段落边界 flush 渲染**（视觉跳跃，TTFT 更晚）
C) **全章完成后一次性渲染**（无流式体验）
D) 其他
[回答]：A

### Question U6-F4 — ConflictItem UI 呈现
Consistency 报告的 ConflictItem 在章节生成页：

A) **右侧固定面板列出所有 Conflict + 点击跳转对应章节高亮 + Ignore / Rewrite 按钮**✓
B) **章节内内联标注（像 Word 批注）**
C) **仅单独报告页呈现，章节页不显示**
D) 其他
[回答]：A

### Question U6-F5 — 人物关系图渲染库
US-03-03 人物报告含人物关系图：

A) **React Flow**（拖拽交互强，bundle 较大 ~120KB）
B) **Cytoscape.js + react wrapper**（学术图谱专业，bundle ~200KB）
C) **D3 force layout**（灵活但工作量大）
D) **ECharts graph**（Apache ECharts，轻量，国内项目常见 ~100KB，支持中文标签） ✓
E) 其他
[回答]：A

### Question U6-F6 — 风格雷达图 / 地图可视化
US-03-04 地图 + US-03-05 风格雷达：

A) **ECharts radar + geo**（与 F5 统一栈）✓
B) **Recharts radar + Leaflet**（分栈）
C) 其他
[回答]：A

### Question U6-F7 — 前端状态管理
跨页数据（当前 Generation、Outline、Chapters）在 SPA 内如何管理？

A) **TanStack Query（React Query）+ Zustand 瞬态 UI 状态**（现代标准栈，缓存好）✓
B) **Redux Toolkit + RTK Query**（企业级，样板代码多）
C) **React Context + useReducer**（轻，复杂场景难维护）
D) 其他
[回答]：A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U6F-1: 生成 `domain-entities.md`（前端侧 DTO / UI 状态模型，区别于后端 entity）
- [x] Step U6F-2: 生成 `business-rules.md`（前端业务规则：SSE 重连、Cancel、Rewrite 链路、权限分支）
- [x] Step U6F-3: 生成 `business-logic-model.md`（关键用户流程图：登录、采集、分析查看、生成、章节审阅、导出）
- [x] Step U6F-4: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **F1=A** 薄 BFF —— 最小复杂度、便于未来演进（业务重心在 ApiService/Worker）
- **F2=A** 透传 SSE —— 保留原 event_id 便于 Last-Event-ID 断线重连
- **F3=A** 逐 delta 渲染 —— NFR-U4 已保证 TTFT ≤ 3s，完整流式 UX 是投资回报最高的 UI 细节
- **F4=A** 右侧固定面板 + 跳转高亮 + 按钮 —— 与业内 AI 写作工具主流一致
- **F5=D** ECharts graph —— 与 F6 统一栈、支持中文标签、bundle 最小、成熟度高
- **F6=A** ECharts radar + geo —— 与 F5 统一
- **F7=A** TanStack Query + Zustand —— React Query 的 request cache / invalidate / refetch 对 Outline/Chapter/Critic 交互场景非常契合；Zustand 处理模态框、tab、侧栏等 UI 状态
