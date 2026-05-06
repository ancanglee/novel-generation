# U6 Frontend + BFF — 非功能需求（NFR Requirements）

**Unit**：U6 Frontend + BFF
**阶段**：NFR Requirements
**日期**：2026-04-30

---

## 范围

U6 面向终端用户的 React SPA + Node.js BFF。本文规定 **性能 / 可观测 / 可访问性 / 可靠性 / 安全 / 国际化 / 兼容性** 等非功能约束，作为后续 NFR Design 与 Code Generation 的闭环判据。

---

## 1. 性能（Performance）

### NFR-U6-1.1 Lighthouse 性能分
- **指标**：Lighthouse v11 Mobile 模式（Emulated Moto G Power, 4G 连接）Performance 分
- **目标**：**≥ 85**（N1=A）
- **依据**：与 React Flow（~120KB） + ECharts（按需 radar/geo/graph）bundle 体量平衡
- **验证**：`lighthouse-ci` 在每次 PR 跑 3 次取中位数；CI 门槛硬限

### NFR-U6-1.2 核心 Web Vitals（P75，CrUX 风格）
| 指标 | 目标 |
|---|---|
| LCP | ≤ 2.5 s |
| FID / INP | ≤ 200 ms |
| CLS | ≤ 0.1 |
| TTFB（SPA HTML） | ≤ 800 ms |

### NFR-U6-1.3 Bundle 预算（gzipped）
- **首屏关键路径**（index.html + 登录页 / Dashboard 最小闭包）：**≤ 200 KB**（N2=A）
  - React 18 + React Router + TanStack Query + Zustand + axios ≈ 95 KB
  - UI 基础组件（shadcn/ui + Tailwind runtime）≈ 30 KB
  - 业务基础壳（Auth/Layout/Toast/ErrorBoundary）≈ 40 KB
  - 预留：35 KB
- **次级 chunk 懒加载预算**
  - `chunk-analysis-graph`（React Flow）≤ 180 KB
  - `chunk-analysis-charts`（ECharts radar/geo 按需）≤ 130 KB
  - `chunk-editor`（章节 markdown 编辑器）≤ 80 KB
- **单个 chunk** 超 250 KB 必须在 PR 拆分

### NFR-U6-1.4 SSE 感知 TTFT（端到端）
- **定义**：用户点"开始生成章节"按钮 → 第一个可见字符出现在屏幕上
- **目标**：**P95 < 5 秒**（N3=A）
  - 预算拆解：U4 TTFT ≤ 3s（后端已保证） + BFF 透传 ≤ 300ms + SPA 处理 ≤ 1.5s + rAF 渲染 ≤ 200ms
- **测量**：SPA 端记录 `firstByteAt - clickAt`，经 BFF `/telemetry` 上报 `novelgen/frontend::SseTtftMs`
- **告警**：P95 > 5s 持续 10 分钟 → SNS `ops-warn`

### NFR-U6-1.5 SSE 流畅度
- 渲染节奏：delta 收到后 ≤ 1 frame（~16.7ms）内合并到 buffer；`requestAnimationFrame` 批量 flush
- 在 1x CPU throttled 设备上，滚动跟随流式光标不掉帧（60fps，允许偶发 ≤ 5% 掉帧）

### NFR-U6-1.6 路由切换性能
- 页间导航动作到首屏元素渲染：P95 < 500 ms（利用预取 + code-split）

---

## 2. 可靠性（Reliability）

### NFR-U6-2.1 SSE 重连能力
- 网络中断后浏览器 EventSource 自动重连
- 最多 5 次重试，指数退避 1s / 2s / 4s / 8s / 16s
- 利用 `Last-Event-ID` 请求头由 ApiService 回放未消费事件
- 重试耗尽 → phase='failed'；UI 提示 "连接不稳定，请刷新"

### NFR-U6-2.2 Cancel 响应
- 用户点"取消"按钮 → UI 进入 `cancelling` 状态（立即禁用按钮） ≤ 100ms
- `cancelled` 事件到达 / 8 秒超时 → phase='cancelled'

### NFR-U6-2.3 错误边界
- 任一 React 组件抛异常 → `ErrorBoundary` 捕获并渲染降级 UI + 提供"重置"按钮
- BFF 单进程崩溃 → ECS 自动重启（U1 预设），同 task 内其它请求不受影响（Node worker_threads 不启用）

### NFR-U6-2.4 离线 / 弱网
- 断网时已加载的页面可只读查看；所有写操作 toast "网络暂时不可用"
- service worker **不启用**（V1 不做 PWA 以免缓存 token 风险）

### NFR-U6-2.5 上传恢复
- 分片上传中断可续传（S3 multipart 固有能力）；前端保留 uploadId 24h

---

## 3. 可访问性（Accessibility, A11y）

### NFR-U6-3.1 WCAG 合规
- **目标**：WCAG 2.1 **Level AA**（N4=A）
- 对比度 ≥ 4.5:1（正文）/ 3:1（大字号）
- 所有可交互元素键盘可达（Tab / Shift+Tab / Enter / Space）
- ARIA 语义：nav / main / article / aside / button / dialog 等使用正确 role
- 模态框焦点陷阱（focus-trap-react）
- 屏幕阅读器公告：流式生成时 `aria-live="polite"` 节流到每 500ms

### NFR-U6-3.2 自动化验证
- `axe-core` + `@axe-core/playwright` 在 E2E 跑每个主要页面
- CI 失败阈值：0 个 serious / critical 违规；≤ 2 个 moderate

### NFR-U6-3.3 键盘快捷键
- Cmd/Ctrl + Enter：在章节编辑器中触发"生成"
- Esc：关闭模态
- `/`：全局搜索

---

## 4. 安全（Security）

### NFR-U6-4.1 Cookie 与会话
- BFF 的 `sid` cookie：`HttpOnly` + `Secure` + `SameSite=Lax` + `path=/` + `max-age=86400`
- Cookie 值为 HS256 签名的 session id，指向服务端内存存储（BFF 进程内 LRU，重启重新登录）
- 签名密钥从 Secrets Manager 读取，30 天自动轮换（U1 支持）

### NFR-U6-4.2 CSRF
- 所有非 GET 请求需要 `X-CSRF-Token` header；值为登录时 BFF 在 cookie 旁返回的明文 token（双提交防御）

### NFR-U6-4.3 CSP
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'wasm-unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https://s3.{region}.amazonaws.com;
  connect-src 'self' https://cognito-idp.{region}.amazonaws.com;
  font-src 'self' data:;
  frame-ancestors 'none';
```

### NFR-U6-4.4 XSS 防御
- 章节正文使用 `DOMPurify` 过滤后渲染（后端 markdown → HTML 前先 sanitize）
- 用户输入（instruction、评论等）永远不用 `dangerouslySetInnerHTML`

### NFR-U6-4.5 多租户边界
- 所有 BFF 请求强制附 `X-Team-Id = session.active_team_id`
- 前端切换 Team 时 `queryClient.clear()`（继承 U1 三层防御）

### NFR-U6-4.6 依赖供应链
- `npm audit` + GitHub Dependabot 启用；high / critical 漏洞 7 天内处理
- Lockfile 入库，`npm ci` 严格安装

---

## 5. 可观测（Observability）

### NFR-U6-5.1 RUM 上报
- BFF 提供 `POST /telemetry`，SPA 每 30 秒批量发送
- 上报字段：sessionId / userId / route / metric / value / timestamp
- BFF 写入 CloudWatch EMF（命名空间 `novelgen/frontend`）

### NFR-U6-5.2 错误上报
- 前端异常 → BFF `POST /telemetry/error`（含 stack / user-agent / build sha）
- 本地已安装 Sentry SDK？**V1 不接 Sentry**，仅走 CloudWatch Logs 简化方案

### NFR-U6-5.3 4 个核心 Alarm
| Alarm | 指标 | 阈值 | 严重度 |
|---|---|---|---|
| `U6-{env}-SseTtftHigh` | `SseTtftMs` P95 5min | > 5_000 ms | warn |
| `U6-{env}-LighthouseRegressed` | 每日 scheduled lighthouse P95 | < 85 | warn |
| `U6-{env}-ClientErrorRateHigh` | `ClientError` 数 / 访问量 5min | > 2% | critical |
| `U6-{env}-BffLatencyHigh` | BFF P95 5min | > 500 ms | warn |

---

## 6. 国际化（i18n）

### NFR-U6-6.1 语言支持
- **V1 仅中文（zh-CN）**（N5=A）
- UI 文案直接使用中文字面量，**建立 `apps/frontend-user/src/strings/` 目录**集中维护（每个模块一个 `.ts` 导出 const 词表）
- 未来若加英语：可一次性扫 `strings/*` 迁到 `react-i18next`

### NFR-U6-6.2 文案规范
- 专有名词英文不译（例：Generation / Outline / Chapter / Critic / Consistency）
- 按钮用动词开头（生成 / 取消 / 重写 / 保存）
- 错误提示遵循"是什么 + 如何处理"（例：多次尝试未解决，请手动编辑）

---

## 7. 兼容性（Compatibility）

### NFR-U6-7.1 浏览器矩阵
- **支持**（N6=A）：Chrome/Edge 115+、Safari 16+、Firefox 115+
- **不支持**：IE、Chrome < 115（vite build target: `es2022`）
- 旧浏览器访问时 SPA 展示升级提示

### NFR-U6-7.2 设备
- 桌面：1280×800 起（主流分辨率）
- 平板：iPad / Android 10" 横竖屏
- 手机：≥ 375×667（iPhone SE）；弱势适配，不作为首选场景

---

## 8. 部署与 CI/CD

### NFR-U6-8.1 构建可复现
- pnpm lockfile + Node 版本锁（engines + `.nvmrc`）
- Docker 构建 deterministic（不依赖外网时间戳）

### NFR-U6-8.2 部署耗时
- CloudFront 失效 ≤ 5 分钟
- BFF ECS rolling update P50 < 4 分钟

### NFR-U6-8.3 回滚
- CloudFront 静态产物 S3 版本化，回滚一键切版本（< 1 分钟）
- BFF 镜像保留最近 5 个 tag，支持 ECR tag 回滚

---

## 9. 成本

继承 U1 / U4 成本模型：
- CloudFront 流量：免费额度后 $0.085 / GB（海外）
- BFF ECS 2×0.25 vCPU / 0.5GB mem ≈ $15/月
- 不设置硬上限，依赖 U1 CloudWatch BillingAlarm

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| React Flow + ECharts 拖低 Lighthouse | 严格懒加载；Lighthouse 测首屏（不含人物图页） |
| SSE 中继引入抖动 → TTFT 超标 | BFF 透传零解析；生产预留 P95 > 4.5s Alarm 提前通知 |
| 中文字面量耦合代码 | `strings/` 目录集中 + lint 规则禁止组件内直接写长串中文 |
| A11y 退化 | axe-core CI 门槛；PR 模板勾选"已跑 axe 本地" |
| Cookie 劫持 | httpOnly + Secure + SameSite + CSRF 双提交 |

---

## 11. 覆盖 Stories

- US-NFR-05 全链路可观测（前端 RUM 分支）
- US-NFR-03 多租户强隔离（前端 Team 切换 + queryClient.clear）
- US-00-01 / US-00-02 首页 + 注册登录（LCP + 鉴权 SLA）
- US-06-01 章节流式（TTFT + 流畅度）
