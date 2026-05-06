# worker-ingestion

Consumes `ingestion-queue`, performs upload/download/crawl, writes Novel + Chapter rows.

## Structure

- `parsers/` — TXT / MD / EPUB / PDF / DOCX / HTML parsers, each registering itself on import
- `fetchers/` — Tier 1 httpx + Tier 2 AgentCore Browser + orchestrator (downgrade logic)
- `search/` — 5 public-domain / search-engine sources (filled in Round 2)
- `robots.py` — robots.txt compliance with 24h TTL cache
- `url_normalizer.py` — crawl-cache sha256 key (tracking-param stripped)
- `chapter_splitter.py` — heuristic chapter splitter (4 regex patterns)
- `llm_chapter_splitter.py` — Bedrock-backed fallback when heuristic confidence < 0.6
- `main.py` — asyncio SQS consumer loop (filled in Round 2)

## Testing

```bash
uv run pytest services/worker-ingestion
```

Fixtures live under `tests/fixtures/`; add small sample files (TXT/EPUB/PDF) when adding parser tests.
