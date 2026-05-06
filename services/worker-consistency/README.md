# worker-consistency (U5)

Cross-chapter consistency scan worker. Consumes `consistency-queue`, calls
Sonnet 4.6 via Bedrock Converse + Tool Use, persists `ConsistencyReport` and
N × `ConflictItem` to DynamoDB, and emits `consistency.report_ready` on
EventBridge.

## Key files

| Path | Purpose |
|---|---|
| `src/worker_consistency/main.py` | SQS consumer, scan orchestration, batched TransactWrite |
| `src/worker_consistency/scan_cursor.py` | `GEN_SCAN#` conditional update — serializes scans per generation |
| `src/worker_consistency/agent.py` | Sonnet 4.6 Converse + `emit_consistency_report` Tool Use |
| `src/worker_consistency/context.py` | Assemble 10 chapter texts + memory facts + character snapshots |
| `src/worker_consistency/prompts/consistency.md` | 6 ConflictType scan prompt |

## Serialization guarantee

`advance_scan(..., scan_to)` uses a DDB conditional update
`last_scan_to < :new`. Duplicate or out-of-order messages are silently
dropped — the worker returns before invoking Bedrock.

## Memory degradation (R7)

If U3 `MemoryFacade.recall()` or `get_character()` raises, the worker
passes `memory_unavailable=true` in the prompt context. The agent
degrades to adjacent-chapter text diff and the resulting report sets
`memory_unavailable: true` so UI can surface the warning.

## Environment

| Env var | Purpose |
|---|---|
| `AWS_REGION` | default `us-east-1` |
| `NOVELGEN_ENV` | `dev` / `stage` / `prod` |
| `CONSISTENCY_QUEUE_URL` | SQS input queue |
| `TENANCY_TABLE` | DDB table for CONSISTENCY# / CONFLICT# / GEN_SCAN# |
| `CHAPTER_BUCKET` | S3 bucket for chapter markdown |
| `EVENT_BUS` | default `novelgen-default-bus` |
