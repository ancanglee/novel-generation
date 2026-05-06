# frontend-user (U6)

React 18 + Vite + TanStack Query + Zustand SPA for NovelGen end users.

## Develop
```bash
pnpm --filter @novelgen/frontend-user dev
# open http://localhost:5173
```
Dev server proxies `/api`, `/auth`, `/telemetry` to `http://localhost:3000` (bff-user).

## Build
```bash
pnpm --filter @novelgen/frontend-user build
```

## Routes & chunks (D2=A)

| Route | Chunk | Notes |
|---|---|---|
| `/` Dashboard | 首屏 | sync, ≤ 200 KB gzipped |
| `/novels`, `/novels/:id` | chunk-novels | IngestForm 3 mode |
| `/novels/:id/analysis` | chunk-analysis | **React Flow** + **ECharts** lazy |
| `/generations/:gid/outline` | chunk-outline | inline-edit + approve |
| `/generations/:gid/chapters/:n` | chunk-chapter | SSE + ConflictPanel |
| `/read/:gid` | chunk-reader | markdown + 3 themes |
| `/settings` | chunk-settings | profile + team |

## State model
- **Server state** — TanStack Query via `qk.*` factory in `lib/queryKeys.ts`
- **Client state** — Zustand stores (`sessionStore`, `chapterStreamStore`, `conflictPanelStore`, `modalStore`)

## Observability
- `lib/telemetry.ts::emit` sends one POST per metric (D4=B) via `sendBeacon` with fetch fallback; `emitOnce` deduplicates per session.
- `ErrorBoundary` emits `UnhandledJsError` for any uncaught render error.

## i18n
- V1 is zh-CN only (N5=A). All strings live under `src/strings/` — migrate to `react-i18next` when English is prioritized.
