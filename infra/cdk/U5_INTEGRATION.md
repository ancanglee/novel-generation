# U5 Integration Notes

U5 (Critic & Consistency) adds resources by mutating existing U1 stacks via helpers
in `shared_constructs/u5_extensions.py`. The `consistency.trigger` EventBridge Rule
is retrofitted into `shared_constructs/u4_extensions.py::extend_messaging_stack`
because the event source is U4 ChapterAgent (I3=C decision).

---

## 1. Wiring snippets

### `stacks/data_stack.py`
```python
from shared_constructs.u5_extensions import extend_data_stack as apply_u5_data
apply_u5_data(self, cfg)
```

### `stacks/identity_stack.py`
```python
from shared_constructs.u5_extensions import extend_identity_stack as apply_u5_identity
apply_u5_identity(
    self, cfg,
    worker_critic_role=self.worker_roles["critic"],
    worker_consistency_role=self.worker_roles["consistency"],
    api_role=self.api_task_role,
)
```

### `stacks/messaging_stack.py`
Update the existing U4 wiring to pass `consistency_queue`:
```python
(review_q, topic, chapter_sm, outline_sm, context_lambda) = extend_messaging_stack(
    self, cfg,
    jobs_table=data.jobs_table,
    tenancy_table=data.tenancy_table,
    generation_queue=self.queues["generation"],
    sfn_role=identity.sfn_role,
    consistency_queue=self.queues["consistency"],  # U5 retrofit
)
```

### `stacks/observability_stack.py`
```python
from shared_constructs.u5_extensions import extend_observability_stack as apply_u5_obs
apply_u5_obs(self, cfg, alerts_topic=self.alerts_topic)
```

---

## 2. Required env additions (ComputeStack)

### worker-critic container
- `CRITIC_QUEUE_URL  = messaging.queues["critic"].queue_url`
- `TENANCY_TABLE     = data.tenancy_table.table_name`
- `CHAPTER_BUCKET    = data.novels_bucket.bucket_name`
- `OUTLINE_BUCKET    = data.novels_bucket.bucket_name`
- `EVENT_BUS         = "default"`
- `NOVELGEN_ENV      = cfg.env_name`

### worker-consistency container
- `CONSISTENCY_QUEUE_URL = messaging.queues["consistency"].queue_url`
- `TENANCY_TABLE         = data.tenancy_table.table_name`
- `CHAPTER_BUCKET        = data.novels_bucket.bucket_name`
- `EVENT_BUS             = "default"`
- `NOVELGEN_ENV          = cfg.env_name`

### api-service container (U5 additions)
- `CHAPTER_REWRITE_MAX   = "3"`  (SSM `/novelgen/{env}/config/conflict-rewrite-max-attempts` — already set; exposed via env to avoid extra IAM round-trip)

---

## 3. Resource delta summary

| Type | Count | Owner |
|---|---|---|
| SSM parameters | 3 | U5 (`extend_data_stack`) |
| CloudWatch Alarms | 4 | U5 (`extend_observability_stack`) |
| EventBridge Rule | 1 (`consistency-trigger`) | U4 retrofit |
| IAM grants | 2 worker roles + api role | U5 (`extend_identity_stack`) |

All other U5 resources reuse U1 pre-built (queues, ECS services, DDB table).

---

## 4. Incremental deploy

Expect `cdk diff` to show:
- `AWS::SSM::Parameter` × 3 added
- `AWS::CloudWatch::Alarm` × 4 added
- `AWS::Events::Rule` × 1 added (U4 stack)
- `AWS::IAM::Policy` × 2–3 updated (added statements)

Deploy time: ~5 minutes after merge.
