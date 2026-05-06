# U3 Integration Notes

U3 adds resources by mutating existing U1 stacks via helpers in
`shared_constructs/u3_extensions.py`.

## Wiring snippets

```python
# stacks/data_stack.py — tail of __init__
from shared_constructs.u3_extensions import extend_data_stack
extend_data_stack(self, cfg)

# stacks/identity_stack.py
from shared_constructs.u3_extensions import extend_identity_stack
extend_identity_stack(self, cfg, self.worker_roles["analysis"])

# stacks/messaging_stack.py — after the analysis queue is created
from shared_constructs.u3_extensions import extend_messaging_stack
self.u3_metadata_fn, self.u3_analysis_sm = extend_messaging_stack(
    self, cfg,
    jobs_table=data.jobs_table,
    analysis_queue=self.queues["analysis"],
    sfn_role=identity.sfn_role,
)

# stacks/observability_stack.py
from shared_constructs.u3_extensions import extend_observability_stack
extend_observability_stack(self, cfg, alerts_topic=self.alerts_topic)

# stacks/agentcore_stack.py
from shared_constructs.u3_extensions import extend_agentcore_stack
extend_agentcore_stack(self, cfg)
```

## ASL

The complete AnalysisStateMachine lives in `infra/cdk/asl/analysis_workflow.json`
and is loaded via `sfn.DefinitionBody.from_string(...)`. Runtime substitutes
variables (`$.jobs_table`, `$.metadata_lambda_arn`, `$.analysis_queue_url`) — they
must be passed in the `StartExecution` input by ApiService.

## Incremental deploy

After merge: `cdk deploy --all` finishes in ~4 minutes additional time
(mostly waiting on SFN ASL replacement + new Lambda package upload).
