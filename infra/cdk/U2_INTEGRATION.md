# U2 Integration Notes

U2 adds resources by mutating existing U1 stacks via helpers in
`shared_constructs/u2_extensions.py`. To wire them:

```python
# stacks/data_stack.py — at the end of __init__
from shared_constructs.u2_extensions import extend_data_stack
extend_data_stack(self, cfg, novels_bucket=self.novels_bucket, jobs_table=self.jobs_table)

# stacks/messaging_stack.py
from shared_constructs.u2_extensions import extend_messaging_stack
self.queues["ingestion"], self.dlqs["ingestion"] = extend_messaging_stack(
    self, cfg, jobs_table=data.jobs_table
)

# stacks/identity_stack.py
from shared_constructs.u2_extensions import extend_identity_stack
self.worker_roles["ingestion"] = extend_identity_stack(self, cfg)
# then grant DDB + S3 access in IdentityStack init
for table in [data.tenancy_table, data.jobs_table, data.config_table]:
    table.grant_read_write_data(self.worker_roles["ingestion"])
for bucket in [data.novels_bucket, data.exports_bucket]:
    bucket.grant_read_write(self.worker_roles["ingestion"])

# stacks/compute_stack.py
from shared_constructs.u2_extensions import extend_compute_stack
extend_compute_stack(
    self, cfg,
    cluster=self.cluster,
    worker_role=identity.worker_roles["ingestion"],
    exec_role=identity.ecs_exec_role,
    security_group=network.sg_ecs_worker,
    ingestion_queue_url=messaging.queues["ingestion"].queue_url,
    novels_bucket_name=data.novels_bucket.bucket_name,
    tenancy_table_name=data.tenancy_table.table_name,
    jobs_table_name=data.jobs_table.table_name,
)

# stacks/observability_stack.py
from shared_constructs.u2_extensions import extend_observability_stack
extend_observability_stack(self, cfg, alerts_topic=self.alerts_topic)
```

## IngestionStateMachine ASL

U1 ships a skeleton. The complete Choice-branched definition lives in
`aidlc-docs/construction/U2-ingestion/infrastructure-design/infrastructure-design.md §3`.
Port that JSON into CDK via `sfn.DefinitionBody.from_chainable(...)` or
`sfn.StateMachine(..., definition_body=sfn.DefinitionBody.from_file("ingestion.asl.json"))`.

## Incremental deploy time

`cdk deploy --all` after U2 merge: approximately 8 extra minutes (ECR repo + Fargate
task + scaling policy + CustomResource).
