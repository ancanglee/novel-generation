# U6 Frontend + BFF — 非功能设计模式（NFR Design Patterns）

**Unit**：U6 Frontend + BFF
**阶段**：NFR Design
**日期**：2026-04-30

---

## 1. BFF 会话模型（D1=A 进程内 LRU）

### 1.1 数据结构
```ts
interface ServerSession {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresAt: number;      // ms epoch
  principal: PrincipalDto;
  createdAt: number;
  lastSeenAt: number;
  csrfToken: string;      // 双提交 CSRF token（明文 cookie）
}

const sessionStore = new LRU<string, ServerSession>({
  max: 5_000,             // 最多 5k 活跃会话
  maxSize: 100 * 1024 * 1024, // 100 MB
  sizeCalculation: () => 20 * 1024, // 每会话约 20KB
  ttl: 6 * 60 * 60 * 1000,   // 6h 绝对过期
  updateAgeOnGet: true,
});
```

### 1.2 登录与刷新
- **登录完成** → 生成 `sessionId = uuid v4` → 写 LRU → 返回 httpOnly `sid = sign(sessionId)` cookie
- **请求入口中间件**：
  1. 验证 `sid` cookie 签名（HS256，Secrets Manager 密钥 30d 轮换）
  2. 从 LRU 取 session；失效 / 未找到 → 401 + 清 cookie
  3. 若 `now > session.expiresAt - 5 min` → 调 Cognito refresh_token endpoint 刷新；失败 → 401
  4. 把 `session.idToken` 作为 `Authorization: Bearer` 转发 ApiService
- **登出** `POST /auth/logout`：LRU delete + 清 cookie + 302 /

### 1.3 多实例后果
ECS 两实例 A/B 不共享 LRU。ALB sticky session（cookie `AWSALB`）保证同会话路由到同实例。实例重启则该实例的 session 全失效 → 用户会被强制重新登录。可接受，因为 rolling update 时 ALB 先 drain，正常情况不触发。

---

## 2. 路由级 Code Split（D2=A）

### 2.1 拆分策略
```tsx
// apps/frontend-user/src/router.tsx
import { createBrowserRouter } from 'react-router-dom';
import RootLayout from './layouts/RootLayout';
import Dashboard from './pages/Dashboard';   // 首屏关键路径 — 同步加载

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, Component: Dashboard },
      { path: 'novels', lazy: () => import('./pages/novels') },
      { path: 'novels/:id/analysis', lazy: () => import('./pages/analysis') },
      { path: 'generations/:gid/outline', lazy: () => import('./pages/outline') },
      { path: 'generations/:gid/chapters/:n', lazy: () => import('./pages/chapter') },
      { path: 'read/:gid', lazy: () => import('./pages/reader') },
      { path: 'settings', lazy: () => import('./pages/settings') },
    ],
  },
]);
```

### 2.2 图形库懒加载
- React Flow 仅在 `/novels/:id/analysis` 路由内 import — 自动进入 `chunk-analysis` chunk
- ECharts `import { EChartsCore } from 'echarts/core'` + 按需 `echarts/charts/radar` + `echarts/components/geo`（tree-shake）
- `chapter` 路由按需 `import('react-markdown')`

### 2.3 Vite 配置
```ts
// vite.config.ts
build: {
  target: 'es2022',
  rollupOptions: {
    output: {
      manualChunks: {
        react: ['react', 'react-dom', 'react-router-dom'],
        query: ['@tanstack/react-query', 'zustand'],
        ui: ['@novelgen/ui'],
      },
    },
  },
},
```

---

## 3. SSE 客户端（D3=A 原生 EventSource）

### 3.1 最简封装
```ts
// apps/frontend-user/src/lib/sse.ts
export function openChapterStream(
  gid: string,
  idx: number,
  handlers: {
    onDelta(eventId: string, text: string): void;
    onPhase(phase: 'start' | 'completed' | 'cancelled' | 'error', data?: unknown): void;
  }
): () => void {
  const url = `/api/v1/generations/${gid}/chapters/${idx}/stream`;
  const es = new EventSource(url, { withCredentials: true });

  es.addEventListener('delta', (evt) => {
    handlers.onDelta(evt.lastEventId, JSON.parse(evt.data).text);
  });
  for (const phase of ['start', 'completed', 'cancelled', 'error'] as const) {
    es.addEventListener(phase, (evt) => {
      handlers.onPhase(phase, JSON.parse((evt as MessageEvent).data ?? 'null'));
      if (phase !== 'start') es.close();
    });
  }
  return () => es.close();
}
```

- 浏览器在 `es.readyState === CONNECTING` 时自动重连，自动带 `Last-Event-ID` header
- BFF 以 `retry: 3000` 指令告诉浏览器重试间隔 3s（相当于退避基底）
- 浏览器自己的指数退避策略已覆盖 NFR-U6-2.1 的 5 次限制（通过上限计数由 store 控制）

### 3.2 rAF 合批渲染（F3=A 决策）
```ts
// pages/chapter/useChapterStream.ts
const stream = useChapterStreamStore();
const pendingRef = useRef('');
const rafRef = useRef<number | null>(null);

function pushDelta(eventId: string, text: string) {
  pendingRef.current += text;
  stream.setLastEventId(eventId);
  if (rafRef.current != null) return;
  rafRef.current = requestAnimationFrame(() => {
    stream.appendBuffer(pendingRef.current);
    pendingRef.current = '';
    rafRef.current = null;
  });
}
```

### 3.3 Cancel 路径
- 用户按"取消"：
  1. `stream.requestCancel()` → phase='cancelling'
  2. `fetch('/api/.../cancel', {method: 'POST'})` —— 不等待响应
  3. SSE 流将自行收到 `cancelled` 事件（worker-generation 合流）
  4. 8s 超时 fallback：`setTimeout` 若仍在 cancelling → 强制 `es.close()` + phase='cancelled'

---

## 4. 遥测管道（D4=B 逐事件立即 POST）

### 4.1 前端发送
```ts
// apps/frontend-user/src/lib/telemetry.ts
export function emit(metric: TelemetryEvent): void {
  // D4=B: 立即发送，不批处理
  const payload = JSON.stringify(metric);
  if (navigator.sendBeacon('/telemetry', payload)) return;
  // sendBeacon unavailable → 回退到 fire-and-forget fetch
  fetch('/telemetry', {
    method: 'POST',
    body: payload,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
    keepalive: true,
  }).catch(() => {});
}
```

### 4.2 带宽缓解措施
- **客户端级去重**：组件 hook `useEmitOnce(metric)` 在同组件生命周期内同 key metric 只发一次
- **visibility 门**：`document.visibilityState === 'hidden'` 时缓存到 `sessionStorage`，下次 `visible` 合并发送
- **BFF 侧限流**：Fastify `@fastify/rate-limit` 全局 100 req/s/session；超过丢弃 + log
- **告警**：若 `/telemetry` QPS > 期望值的 3× → 触发 `U6-TelemetryQpsAnomalous` warning

### 4.3 BFF 写 CloudWatch
```ts
// apps/bff-user/src/routes/telemetry.ts
app.post('/telemetry', async (req, reply) => {
  const m = TelemetryEventSchema.parse(req.body);
  logger.info({
    _aws: {
      Timestamp: Date.now(),
      CloudWatchMetrics: [
        {
          Namespace: 'novelgen/frontend',
          Dimensions: [['Env', 'Route', 'Metric']],
          Metrics: [{ Name: m.name, Unit: m.unit }],
        },
      ],
    },
    Env: process.env.NOVELGEN_ENV,
    Route: m.route,
    Metric: m.name,
    [m.name]: m.value,
  });
  return reply.code(204).send();
});
```

---

## 5. BFF 错误透传（D5=A）

### 5.1 通用反向代理 handler
```ts
// apps/bff-user/src/proxy.ts
async function proxyToApi(req, reply, session) {
  const upstream = `${API_BASE}${req.url}`;
  try {
    const res = await undici.request(upstream, {
      method: req.method,
      headers: {
        authorization: `Bearer ${session.idToken}`,
        'x-team-id': session.principal.teamId,
        'content-type': req.headers['content-type'] ?? 'application/json',
      },
      body: req.body,
      bodyTimeout: 30_000,
      headersTimeout: 10_000,
    });
    reply.code(res.statusCode);
    for (const [k, v] of Object.entries(res.headers)) {
      if (!HOP_BY_HOP.has(k.toLowerCase())) reply.header(k, v as string);
    }
    if (res.statusCode >= 500) {
      reply.header('x-upstream-error', `apiservice:${res.statusCode}`);
    }
    return reply.send(res.body);
  } catch (err: any) {
    reply.header('x-upstream-error', `bff:${err.code ?? 'unknown'}`);
    reply.code(502).send({
      error: { code: 'UPSTREAM_UNREACHABLE', message: err.message },
    });
  }
}
```

- **5xx** 原样透传 status + body + 附 `X-Upstream-Error` header
- **网络错误** 502 + 结构化错误体
- **超时**：`bodyTimeout: 30s` 覆盖普通请求；**SSE 路径走独立 handler 无超时**

### 5.2 SSE 专用代理
```ts
async function proxySse(req, reply, session) {
  reply.raw.setHeader('Content-Type', 'text/event-stream');
  reply.raw.setHeader('Cache-Control', 'no-cache');
  reply.raw.setHeader('Connection', 'keep-alive');
  reply.raw.flushHeaders();

  const lastId = req.headers['last-event-id'];
  const upstream = await undici.request(`${API_BASE}${req.url}`, {
    method: 'GET',
    headers: {
      authorization: `Bearer ${session.idToken}`,
      'x-team-id': session.principal.teamId,
      ...(lastId ? { 'last-event-id': lastId as string } : {}),
    },
    bodyTimeout: 0,
    headersTimeout: 10_000,
  });
  // 透传上游 stream
  upstream.body.on('data', (chunk) => reply.raw.write(chunk));
  upstream.body.on('end', () => reply.raw.end());
  req.raw.on('close', () => upstream.body.destroy());
}
```

---

## 6. 安全头 / CSP 落地

### 6.1 Fastify helmet 配置
```ts
await app.register(helmet, {
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'wasm-unsafe-eval'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", 'data:', `https://s3.${REGION}.amazonaws.com`],
      connectSrc: ["'self'", `https://cognito-idp.${REGION}.amazonaws.com`],
      fontSrc: ["'self'", 'data:'],
      frameAncestors: ["'none'"],
    },
  },
  referrerPolicy: { policy: 'same-origin' },
  crossOriginEmbedderPolicy: false,   // 允许 React Flow 内联 svg
});
```

### 6.2 CSRF 双提交
- 登录时 BFF 生成 `csrfToken = nanoid(32)`，写明文 cookie `csrf=...`（非 HttpOnly）
- SPA 在每个非 GET 请求携带 `X-CSRF-Token: <cookie 值>` header
- BFF 中间件比对 `X-CSRF-Token` 与服务端 session.csrfToken；不匹配 → 403

### 6.3 XSS 纵深防御
- 章节 markdown 渲染前经 DOMPurify
- 用户输入永远 React 默认转义；不使用 `dangerouslySetInnerHTML`
- ECharts 标签使用 pure string（不含 HTML）

---

## 7. SPA 首屏优化

### 7.1 HTML 体积
- `index.html` 内联 CSS 关键路径（critters 插件）
- 预加载 `<link rel="modulepreload">` 首屏路由 chunk
- 字体使用 `font-display: swap` + 子集化（中文常用 6000 字）

### 7.2 图片
- `<img loading="lazy">` 默认
- 页面英雄图（如有）使用 `@vite-imagetools` 自动生成 WebP + srcset

### 7.3 渲染模式
- 纯 CSR（V1 不做 SSR）—— 初屏 CLS 通过骨架屏保障 ≤ 0.1

---

## 8. 可观测埋点清单

| 场景 | Metric 名 | Unit |
|---|---|---|
| 路由切换完成 | `RouteTransitionMs` | Milliseconds |
| API 请求 | `ApiRequestDurationMs` | Milliseconds |
| API 错误 | `ClientError` | Count |
| SSE 点击到首 delta 上屏 | `SseTtftMs` | Milliseconds |
| SSE 重连次数 | `SseReconnectCount` | Count |
| Rewrite 409 | `RewriteFrozen409` | Count |
| JS 运行时异常 | `UnhandledJsError` | Count |
| Web Vitals (LCP/INP/CLS) | `WebVital*` | Milliseconds / None |

---

## 9. 故障降级策略

| 故障 | UI 行为 |
|---|---|
| BFF 502 | toast "服务暂时不可用"；重试按钮；保留已加载数据 |
| Cognito 登录 302 循环 | 抬出 "请清理浏览器 cookies 后重试" |
| ApiService 分析接口 5xx | 分析页显示降级骨架 + 重试 |
| SSE 连续 5 次失败 | phase=failed + "刷新重试"按钮 |
| React Flow 加载失败 | 降级纯文本人物列表 |
| ECharts 加载失败 | 降级表格雷达六维数字 |

---

## 10. 多租户前端守护

### 10.1 队列锁
`queryClient.clear()` 在 Team 切换时同步执行；所有在飞请求经 `queryClient.cancelQueries()` 主动取消，防止旧 Team 响应污染新 Team UI。

### 10.2 显示过滤
Dashboard 聚合卡片的所有数据源都已经带 Team scope，但前端额外在组件层做断言：若 item.team_id !== session.active_team_id → 丢弃 + 告警（防御深度）。
