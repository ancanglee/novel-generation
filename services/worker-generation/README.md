# worker-generation

U4 Generation Worker — consumes generation-queue + review-queue, orchestrates Outline / Chapter stream /
Self-Critique / Outline Review agents, publishes streaming events to EventBridge.

## Structure

- `mode.py` — `Mode.CLEAN_ROOM` / `Mode.CONTINUATION`
- `cancel_cache.py` — TTLCache(8s) + DDB fallback for cancel checks
- `style_injection.py` — 6-dim StyleVector prefix + memory block + previous chapter tail
- `event_publisher.py` — EventBridge PutEvents helper (streaming events)
- `agents/`
  - `_bedrock_stream.py` — Converse Tool Use invoker + converse_stream generator
  - `outline.py` — Opus 4.7 full-book outline with Tool Use
  - `chapter.py` — Sonnet 4.7 converse_stream with cancel-aware event publishing
  - `self_critique.py` — Sonnet 4.6 structured critique
  - `outline_review.py` — F3=B advisory review (warn / info)
- `prompts/` — 5 Markdown prompts: clean_room, continuation, outline, self_critique, outline_review
- `main.py` — dual-queue SQS consumer, kind-based routing, SFN send_task_success/failure

## Testing

```bash
uv run pytest services/worker-generation
```

Tests cover style injection block building, cancel cache invalidation semantics, and JSON
schema validity of every agent's Tool Use schema.
