# U4 Integration Notes

U4 adds resources by mutating existing U1 stacks via helpers in
`shared_constructs/u4_extensions.py`.

## Wiring snippets

```python
# stacks/data_stack.py
from shared_constructs.u4_extensions import extend_data_stack
extend_data_stack(self, cfg, self.novels_bucket)

# stacks/identity_stack.py
from shared_constructs.u4_extensions import extend_identity_stack
extend_identity_stack(self, cfg, self.worker_roles["generation"], self.api_task_role)

# stacks/messaging_stack.py
from shared_constructs.u4_extensions import extend_messaging_stack
(review_q, topic, chapter_sm, outline_sm, context_lambda) = extend_messaging_stack(
    self, cfg,
    jobs_table=data.jobs_table,
    tenancy_table=data.tenancy_table,
    generation_queue=self.queues["generation"],
    sfn_role=identity.sfn_role,
)
self.u4_review_queue = review_q
self.u4_topic = topic
self.u4_chapter_sm = chapter_sm
self.u4_outline_sm = outline_sm

# stacks/observability_stack.py
from shared_constructs.u4_extensions import extend_observability_stack
extend_observability_stack(self, cfg, alerts_topic=self.alerts_topic)
```

## Required env additions (ComputeStack)

worker-generation container env:
- `GENERATION_QUEUE_URL = messaging.queues["generation"].queue_url`
- `REVIEW_QUEUE_URL = messaging.u4_review_queue.queue_url`
- `NOVELS_BUCKET` / `TENANCY_TABLE` / `JOBS_TABLE` (already set by U1/U2)

api-service container env:
- `GENERATION_SNS_TOPIC_ARN = messaging.u4_topic.topic_arn`
- `OUTLINE_STATE_MACHINE_ARN = messaging.u4_outline_sm.state_machine_arn`
- `CHAPTER_STATE_MACHINE_ARN = messaging.u4_chapter_sm.state_machine_arn`

## Incremental deploy

~5 minutes after merge.
