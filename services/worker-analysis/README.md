# worker-analysis

U3 Understanding Worker — consumes `analysis-queue`, runs a Supervisor (Opus 4.7) that orchestrates
6 sub-agents via Bedrock Tool Use, writes to MemoryFacade (AgentCore Memory + Neptune + OpenSearch).

## Structure

- `memory/` — MemoryFacade concrete implementation
  - `agentcore_memory.py` — AgentCore Memory wrapper (SDK placeholder)
  - `neptune_client.py` — openCypher + self-signed SigV4 via botocore
  - `opensearch_client.py` — kNN + bulk write + RRF hybrid
  - `facade_impl.py` — `MemoryFacadeImpl` with tiered degradation (F8=A)
- `agents/` — 9 tools registered for Supervisor
  - `rough_read.py` — Haiku-driven adaptive sampling (F2=C)
  - `classification.py` — multi-label with confidence (F3=A)
  - `character_global.py` — rough-read Profile drafts (F4=A)
  - `map_global.py` — places + factions + edges
  - `style.py` — 6-dim style vector (F6=A)
  - `chapter_all.py` — single-call composite extraction (F7=A)
  - `profile_rewrite.py` — rare rewrite (R4.4)
  - `memory_writer.py` — MemoryFacade batch flush
  - `_bedrock.py` — shared Converse Tool Use helper
- `prompts/` — Markdown system prompts; load via `load_prompt(name)`
- `supervisor.py`, `main.py`, `checkpoint.py`, `agentcore_registration.py` — landing in Round 2

## Testing

```bash
uv run pytest services/worker-analysis
```

Tests avoid real Bedrock calls; schema validation + sampling bounds are deterministic.
