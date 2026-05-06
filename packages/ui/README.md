# @novelgen/ui

NovelGen business UI components shared across `frontend-user` (U6) and future admin SPA (U7).

## Primitives
- `Button` (4 variants × 3 sizes)
- `Dialog` (native `<dialog>` modal with backdrop dismiss)
- `Toast` (4 variants with ARIA `status`)
- `Spinner`, `Badge`

## Business components
| Component | Purpose | Heavy deps |
|---|---|---|
| `StreamingText` | Growing text buffer + blinking cursor + aria-live | — |
| `ConflictPanel` | 6 ConflictType chips + Ignore / Rewrite with frozen grey-out | — |
| `StyleRadar` | ECharts radar, 6 dims | `echarts-for-react` (peer) |
| `CharacterGraph` | React Flow circular layout | `@xyflow/react` (peer, lazy-loaded) |
| `ChapterReader` | Markdown renderer with 3 themes + adjustable font | `react-markdown` (peer) |

## Tailwind
Consumers must:
1. Include `node_modules/@novelgen/ui/src/**/*.{ts,tsx}` in their Tailwind `content` array.
2. Import `@novelgen/ui/styles.css` for theme tokens (light + dark).

## Peer deps
`react 18.3+`, `react-dom 18.3+`, `@xyflow/react 12+`, `echarts 5.5+`, `echarts-for-react 3+`, `react-markdown 9+`, `remark-gfm 4+`.
