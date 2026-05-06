# worker-critic (U5)

Layer-2 review worker. Consumes `critic-queue`, calls Claude Opus 4.7 via
Bedrock Converse + Tool Use, persists `CritiqueReport` to DynamoDB, and emits
`critic.report_ready` on EventBridge.

## Key files

| Path | Purpose |
|---|---|
| `src/worker_critic/main.py` | SQS long-poll, S3/DDB reads, agent invocation, DDB write, EventBridge emit |
| `src/worker_critic/agent.py` | Opus 4.7 Converse + `emit_critique_report` Tool Use + tenacity retries |
| `src/worker_critic/context.py` | Assemble chapter text + Layer-1 critique + 5 recent summaries + style vector |
| `src/worker_critic/prompts/critic_layer2.md` | Layer-2 prompt template (Chinese) |
| `src/worker_critic/ssm_config.py` | 60s-refresh SSM parameter cache |
| `src/worker_critic/metrics.py` | EMF emitters: CriticDurationMs / Score / FailureCount |
| `src/worker_critic/event_publisher.py` | `critic.report_ready` PutEvents |

## Environment

| Env var | Purpose |
|---|---|
| `AWS_REGION` | default `us-east-1` |
| `NOVELGEN_ENV` | `dev` / `stage` / `prod` (metric dim + SSM prefix) |
| `CRITIC_QUEUE_URL` | SQS input queue |
| `TENANCY_TABLE` | DDB table for CHAPTER# layer-1 + CRITIQUE# write |
| `CHAPTER_BUCKET` | S3 bucket containing `generations/{gid}/chapters/{idx:05d}.md` |
| `OUTLINE_BUCKET` | S3 bucket containing `generations/{gid}/outline.json` |
| `EVENT_BUS` | default `novelgen-default-bus` |

## Failure semantics (N3=A)

When Opus 4.7 fails all 3 retries, the worker writes a `minimal=True`
`CritiqueReport` with `score=0` and proceeds. The chapter's own status is
not touched — business continues.
