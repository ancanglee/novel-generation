# U6 Frontend + BFF — 非功能设计计划

**Unit**：U6 Frontend + BFF
**阶段**：NFR Design
**日期**：2026-04-30

---

## 上下文摘要
U6 NFR Design 聚焦：
- SPA 架构与代码拆分模式
- SSE 重连状态机与前端流式渲染策略
- BFF 的透传 + 会话模型（F1=A 薄 BFF + F2=A 透传）
- 遥测管道（RUM → BFF /telemetry → CloudWatch EMF）
- 安全头与 CSP 具体规则
- 路由级代码拆分与懒加载

澄清面较窄（5 问）。

---

## 第 1 部分 — 澄清问题（5 个）

### Question U6-D1 — BFF 会话存储形态
`sid` cookie 指向的服务端会话数据（含 id_token / access_token / refresh_token）：

A) **BFF 进程内 LRU（100MB 上限 / 6h TTL / 多实例非共享）**（N4=A 降低复杂度，重启需重新登录，用户可接受）✓
B) **Redis 共享存储（U1 预留 ElastiCache）**（跨实例一致，但成本 +$30/月且 U1 未启用 Redis）
C) **Cookie 直接装 JWT（无服务端状态）**（无法主动吊销，refresh_token 入 cookie 风险）
D) 其他
[回答]：A

### Question U6-D2 — 路由级 Code Split 粒度
除首屏关键路径外，次级 chunk 如何切？

A) **按顶级路由切**（/novels、/generations、/read/:gid、/analysis/:id 各自一 chunk；图形库随其所在页懒加载）✓
B) **按"重资源"切 4 个 chunk**（React Flow 独立 / ECharts 独立 / Markdown 独立 / 其余业务合并）
C) **精细化每个视图 1 个 chunk**（过度拆分，HTTP/2 也有额外成本）
D) 其他
[回答]：A

### Question U6-D3 — SSE 客户端实现
前端建立 SSE 连接时：

A) **浏览器原生 `EventSource`**（自动重连 + 自动带 Last-Event-ID，但不能自定义 headers）—— 配合 cookie 鉴权即可✓
B) **`@microsoft/fetch-event-source`**（可自定义 headers 但需手写重连循环）
C) 自建 fetch + ReadableStream 逐 frame 解析
D) 其他
[回答]：A

### Question U6-D4 — 遥测批处理
RUM 事件如何从 SPA 发到 BFF /telemetry？

A) **批量缓冲 30s 或 20 事件触发一次 POST；navigator.sendBeacon 兜底 unload**✓
B) **逐事件立即 POST**（消耗带宽）
C) 页面卸载时一次 POST
D) 其他
[回答]：B

### Question U6-D5 — BFF 上游错误透传
BFF 收到 ApiService 5xx / 超时 / 网络错时：

A) **原样透传 status + body，附加 X-Upstream-Error header 便于排查**✓
B) **BFF 统一转 502 并吞上游细节**（前端难以定位）
C) BFF 做 1 次重试再透传
D) 其他
[回答]：A

---

## 第 2 部分 — 执行清单（批准后）

- [x] Step U6D-1: 生成 `nfr-design-patterns.md`
- [x] Step U6D-2: 生成 `logical-components.md`
- [x] Step U6D-3: 更新 aidlc-state.md

---

## 第 3 部分 — 推荐
- **D1=A** BFF 进程内 LRU —— 简单、无额外成本；重启相当于强制重新登录（低频，可接受）
- **D2=A** 按顶级路由切分 —— 与 React Router 数据路由 API 天然契合，Vite 自动 code-split
- **D3=A** 原生 EventSource —— 配合 BFF cookie 鉴权，零重连逻辑自己写
- **D4=A** 批量 30s/20 事件 + sendBeacon unload —— 业界标准
- **D5=A** 透传 + X-Upstream-Error —— 便于 DevTools 排查
