# U6 Frontend + BFF — 业务流程模型（Business Logic Model）

**Unit**：U6 Frontend + BFF
**阶段**：Functional Design
**日期**：2026-04-28

本文用 ASCII 流程图描述关键用户旅程的业务逻辑，便于跨职能对齐。

---

## Flow 1 — 登录与会话初始化

```
Browser                BFF (Node)                Cognito                 ApiService
   │                       │                        │                         │
   │─ GET /  (无 sid) ─────▶│                        │                         │
   │◀── 302 /auth/login ───│                        │                         │
   │                       │                        │                         │
   │─ GET /auth/login ─────▶│                        │                         │
   │                       │─ 302 Hosted UI ────────▶│                         │
   │◀─────── Cognito Hosted UI page ────────────────│                         │
   │  [用户输入 credentials]                          │                         │
   │─── POST /oauth2/token (code) ────────────────────▶                        │
   │◀── 302 /auth/callback?code=...                  │                         │
   │                       │                        │                         │
   │─ GET /auth/callback?code=...▶                   │                         │
   │                       │─ POST /oauth2/token ──▶│                         │
   │                       │◀── {id_token, access, refresh} ─────────────────│
   │                       │ SET-COOKIE sid=<signed>│                         │
   │◀── 302 / (httpOnly sid)│                        │                         │
   │                       │                        │                         │
   │─ GET /auth/me ────────▶│                        │                         │
   │                       │─ verify sid + decode JWT ──────────────────────▶│
   │                       │                        │                         │
   │◀── 200 { principal } ─│                        │                         │
   │                       │                        │                         │
   │  [SPA bootstraps useSessionStore.principal]     │                         │
```

---

## Flow 2 — 章节流式生成与 SSE 重连

```
Browser (useChapterStreamStore)    BFF /api/.../stream    ApiService SSE    worker-generation
       │                                 │                      │                    │
  phase=connecting                       │                      │                    │
       │─ new EventSource() ────────────▶│                      │                    │
       │                                 │─ GET upstream SSE ──▶│                    │
       │                                 │  Authorization=jwt   │                    │
       │                                 │  Last-Event-ID=null  │                    │
       │                                 │◀─ 200 text/event-stream               │
       │◀──── retry: 3000 ────────────────                       │                    │
       │◀──── event: start, id: gid:n:0 (heartbeat/phase)        │                    │
  phase=streaming                        │                      │                    │
       │◀──── event: delta, id: gid:n:1, data: {"text": "..."}   │                    │
       │   buffer += text (rAF batch)    │                      │                    │
       │   set lastEventId = "gid:n:1"   │                      │                    │
       │◀──── event: delta, id: gid:n:2, data: {"text": "..."}   │                    │
       │   ...                           │                      │                    │
       │                                 │                      │◀── stream delta ──│
       │                                 │                      │                    │
       │ ┌── network blip: EventSource 自动重连 (onerror)         │                    │
       │ ├── readyState=CONNECTING        │                      │                    │
       │ ├── 指数退避 1s/2s/4s/8s/16s     │                      │                    │
       │ └── 重连时 EventSource 自动带     │                      │                    │
       │     header Last-Event-ID: "gid:n:2"                    │                    │
       │─ GET /api/.../stream ──────────▶│─ GET upstream ──────▶│                    │
       │  Last-Event-ID=gid:n:2          │  Last-Event-ID=gid:n:2                   │
       │                                 │◀─ 200 replay from   │                    │
       │◀──── event: delta, id: gid:n:3, data: ...              │                    │
       │   ...                           │                      │                    │
       │◀──── event: completed, id: gid:n:LAST                  │                    │
  phase=completed                        │                      │                    │
       │── queryClient.invalidate(qk.chapter(gid,n)) ──────────────────────────────▶│
       │── queryClient.prefetch(qk.critique(gid,n))             │                    │
       │── queryClient.prefetch(qk.consistency(gid, n))         │                    │

[Cancel 分支]
  User clicks "取消"
       │─ POST /api/generations/{gid}/chapters/{n}/cancel ─▶│
  phase=cancelling                       │
       │◀── event: cancelled ───────────│
  phase=cancelled；保留 buffer 只读
```

---

## Flow 3 — Conflict Rewrite 触发与冻结反馈

```
Browser (ConflictPanel)          BFF              ApiService /api/v1/conflicts/*        DDB
      │                           │                          │                            │
      │  User clicks "Rewrite"    │                          │                            │
      │  on ConflictItem ci_1     │                          │                            │
      │─ Modal 确认 "重写将生成新章节" │                          │                            │
      │─ 确认 ─▶                   │                          │                            │
      │─ POST /api/v1/conflicts/ci_1/rewrite ────────────────▶│                            │
      │                           │─ auth + team-id header ─▶│                            │
      │                           │                          │─ find_by_id ──────────────▶│
      │                           │                          │◀──────── item ────────────│
      │                           │                          │─ request_rewrite:         │
      │                           │                          │   UpdateItem conditional  │
      │                           │                          │   rewrite_attempts+=1     │
      │                           │                          │   frozen = (attempts>=3)  │
      │                           │                          │──────────────────────────▶│
      │                           │                          │◀────── UPDATED_NEW ──────│
      │                           │                          │ if frozen:                 │
      │                           │                          │   emit ConflictLoopDetected│
      │                           │                          │─ httpx POST /api/v1/       │
      │                           │                          │   generations/{gid}/       │
      │                           │                          │   chapters/{n}/rewrite ──▶│
      │                           │                          │◀── 202 { generation_id }  │
      │◀── 202 {conflict_id, rewrite_attempts, frozen, job_ref}                          │
      │                           │                          │                            │
  [成功分支]                                                                                │
      │ store.setSelected(null)                                                            │
      │ toast "已触发重写，切到新章节流式"                                                        │
      │ useChapterStreamStore.reset(); setGid(...); setChapterIdx(n); phase='connecting'   │
      │                                                                                    │
  [409 冻结分支]                                                                            │
      │◀── 409 {CONFLICT_REWRITE_FROZEN}                                                  │
      │ 面板按钮灰化 + tooltip "多次尝试未解决，请手动编辑"                                       │
      │ Sentry breadcrumb 记录                                                             │
```

---

## Flow 4 — 小说库采集（上传 + 搜索 + URL）

```
Browser                          BFF                ApiService /api/v1/novels/*       Worker-Ingestion
   │                              │                          │                             │
   │─ 选本地文件 (.epub 50MB) ────▶│                          │                             │
   │─ POST /api/novels/upload     │                          │                             │
   │  (multipart 分片)            │─ pre-signed PUT? 或流式 ─▶│                             │
   │                              │  代理到 ApiService       │                             │
   │                              │                          │─ upload S3 multipart ──────▶│
   │                              │                          │  (initiate / chunks / complete)
   │                              │                          │─ enqueue SQS ingest ───────▶│
   │◀── 202 { job_id } ───────────│                          │                             │
   │                              │                          │                             │
   │ [polling loop]               │                          │                             │
   │─ GET /api/jobs/{id}          │                          │                             │
   │◀── 200 { status: RUNNING, progress: 40 }                │                             │
   │─ GET /api/jobs/{id}          │                          │                             │
   │◀── 200 { status: SUCCEEDED, result_ref: novel_id }      │                             │
   │ queryClient.invalidate(qk.novels())                     │                             │
   │ toast "已入库"                                                                         │
```

---

## Flow 5 — 导出（EPUB / PDF / Markdown / DOCX）

```
Browser                   BFF                 ApiService /exports
   │                       │                         │
   │─ POST /api/generations/{gid}/export?format=epub▶│
   │                       │                         │─ enqueue SQS export ─▶ worker
   │◀── 202 { job_id } ────│                         │
   │                       │                         │
   │ [polling loop]        │                         │
   │─ GET /api/jobs/{id}   │                         │
   │◀── SUCCEEDED { result_ref: "s3://.../xxx.epub" }│
   │                       │                         │
   │─ GET /api/exports/{job_id}/download ───────────▶│
   │                       │                         │─ generate pre-signed URL (5 min)
   │◀── 200 { url: "https://s3.../xxx.epub?sig=..." }│
   │                       │                         │
   │ [浏览器触发下载]        │                         │
```

---

## Flow 6 — 状态机总览（章节生成页 phase）

```
                                        start()
                                           │
         ┌──────────────────────────── idle ─┐
         │                                  │
         │           Cancel / completed     │ connect SSE
         ▼           / failed reset()       ▼
    cancelled ◀──── cancelling ◀─── streaming ────▶ completed
         ▲                │               ▲  │         │
         │                │               │  │         │  reset()
         │         failed ▼               │  │         ▼
         └────────── failed ──────────────┘  │       idle
                                          reconnect
                                          (blip)
```

**状态迁移表**

| From | Event | To |
|---|---|---|
| idle | start() | connecting |
| connecting | first SSE event | streaming |
| connecting | 5 次重试失败 | failed |
| streaming | SSE blip | connecting（自动） |
| streaming | event:completed | completed |
| streaming | event:error | failed |
| streaming | requestCancel() | cancelling |
| cancelling | event:cancelled | cancelled |
| cancelling | 8s 超时 | cancelled |
| any | reset() | idle |

---

## Flow 7 — 团队切换与缓存清理

```
TopBar TeamPicker                  Zustand                TanStack Query
       │                               │                        │
       │─ 用户选新 Team B ─────────────▶│                        │
       │                       setTeamId('B')                  │
       │                               │                        │
       │                               │─ queryClient.clear() ──▶│
       │                               │                        │ 清除所有 ['novels',...]
       │                               │                        │ ['generations',...] 缓存
       │                               │                        │
       │◀── 导航到 /                    │                        │
       │    (依赖的 hooks 重新 fetch)                              │
```
