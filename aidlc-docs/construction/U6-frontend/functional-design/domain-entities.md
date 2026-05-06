# U6 Frontend + BFF — 领域实体（Domain Entities）

**Unit**：U6 Frontend + BFF
**阶段**：Functional Design
**日期**：2026-04-28

---

## 范围说明

U6 不产生新的后端领域实体。本文描述 **前端侧 DTO（从 `@novelgen/api-client` 生成）** 与 **SPA 运行时状态（UI state）**，并标注与后端 entity 的映射关系。

---

## 1. DTO（TypeScript，来自 `@novelgen/api-client`）

DTO 由 OpenAPI 规范经 `openapi-typescript` 自动生成，存放于 `packages/api-client-ts/src/generated.ts`。以下列出前端主要消费的 DTO：

| DTO | 对应后端 entity | 来源 API |
|---|---|---|
| `NovelDto` | Novel (U2) | `GET /novels`, `GET /novels/{id}` |
| `AnalysisReportDto` | AnalysisReport (U3) | `GET /novels/{id}/analysis` |
| `CharacterGraphDto` | Character + Relation (U3) | `GET /novels/{id}/characters` |
| `StyleVectorDto` | StyleVector (U3/U4) | `GET /novels/{id}/style` |
| `GenerationDto` | Generation (U4) | `GET /generations/{gid}` |
| `OutlineDto` | Outline (U4) | `GET /generations/{gid}/outline` |
| `ChapterDraftDto` | ChapterDraft (U4) | `GET /generations/{gid}/chapters/{n}` |
| `CritiqueReportDto` | CritiqueReport (U5) | `GET /generations/{gid}/chapters/{n}/critique` |
| `ConsistencyReportDto` | ConsistencyReport (U5) | `GET /generations/{gid}/consistency-reports` |
| `ConflictItemDto` | ConflictItem (U5) | 嵌在 ConsistencyReportDto |
| `JobDto` | Job (U1) | `GET /jobs/{id}` |
| `TeamMemberDto` | User + Team (U1) | `GET /teams/current` |

DTO 字段完全镜像后端 pydantic 模型（U1 `packages/shared-types-ts` 约定）。

---

## 2. UI State（Zustand stores）

> F7=A：跨页数据走 TanStack Query（server state），模态框 / Tab / 侧栏 / 流式缓冲等瞬态 UI state 走 Zustand。

### 2.1 `useSessionStore`
```ts
interface SessionState {
  principal: PrincipalDto | null;   // /auth/me 返回
  teamId: string | null;            // active team
  setPrincipal(p: PrincipalDto | null): void;
}
```

### 2.2 `useChapterStreamStore`（章节生成页核心）
```ts
interface ChapterStreamState {
  gid: string | null;
  chapterIdx: number | null;
  phase: 'idle' | 'connecting' | 'streaming' | 'completed' | 'cancelling' | 'cancelled' | 'failed';
  // live-streaming buffer (F3=A 逐 delta 渲染)
  buffer: string;
  lastEventId: string | null;       // for Last-Event-ID reconnect
  firstByteAt: number | null;
  completedAt: number | null;
  error: string | null;
  // actions
  start(gid: string, idx: number): void;
  appendDelta(eventId: string, delta: string): void;
  markCompleted(): void;
  markFailed(msg: string): void;
  requestCancel(): void;
  reset(): void;
}
```

### 2.3 `useConflictPanelStore`（F4=A 右侧面板）
```ts
interface ConflictPanelState {
  gid: string | null;
  open: boolean;
  selectedConflictId: string | null;   // 与章节正文高亮联动
  setSelected(id: string | null): void;
  toggleOpen(): void;
}
```

### 2.4 `useModalStore`（全局模态）
```ts
interface ModalState {
  kind: null | 'create_generation' | 'edit_outline' | 'rewrite_confirm' | 'export';
  payload: Record<string, unknown>;
  open(kind: ModalKind, payload?: Record<string, unknown>): void;
  close(): void;
}
```

---

## 3. BFF 侧类型

BFF 本身不维护复杂领域状态。它只做反向代理 + Cookie 封装（F1=A），必需结构：

### 3.1 `Session` (Cookie payload, stateless JWT passthrough)
```ts
interface Session {
  idToken: string;       // 保留用于向 ApiService 转发 Authorization
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}
```

会话仅凭 httpOnly cookie `sid` 存在；BFF 在每个请求入口验证签名，然后将 `idToken` 写入 `Authorization: Bearer ...` 转发给 ApiService。

### 3.2 `SseRelayContext`
```ts
interface SseRelayContext {
  upstreamUrl: string;          // ApiService SSE endpoint
  lastEventId: string | null;   // client-provided header
  abort: AbortController;
}
```

---

## 4. TanStack Query Keys 规范

为确保 invalidate 粒度可控，统一定义 query key 工厂：

```ts
export const qk = {
  novels: () => ['novels'] as const,
  novel: (id: string) => ['novels', id] as const,
  analysis: (novelId: string) => ['novels', novelId, 'analysis'] as const,
  characters: (novelId: string) => ['novels', novelId, 'characters'] as const,
  style: (novelId: string) => ['novels', novelId, 'style'] as const,
  generations: () => ['generations'] as const,
  generation: (gid: string) => ['generations', gid] as const,
  outline: (gid: string) => ['generations', gid, 'outline'] as const,
  chapter: (gid: string, n: number) => ['generations', gid, 'chapters', n] as const,
  critique: (gid: string, n: number) => ['generations', gid, 'chapters', n, 'critique'] as const,
  consistency: (gid: string, sinceChapter: number) =>
    ['generations', gid, 'consistency', sinceChapter] as const,
  job: (id: string) => ['jobs', id] as const,
} as const;
```

---

## 5. 不在此 Unit 的实体

以下仍是后端职责，前端仅消费：
- Fact / GraphNode / GraphEdge（在后端 Neptune 中，前端通过 CharacterGraphDto 的展开视图访问）
- Job 细粒度 step（前端只读 Job 状态机 5 态）
- Admin 域（users 管理、model-configs 管理、审计事件查询）—— **归 U7**
