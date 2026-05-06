# novelgen-obs-adapter

Structured JSON logging and CloudWatch EMF metric emission.

All metrics go under the `NovelGen` namespace via Log Metric Filters (zero PutMetricData cost).

## Usage

```python
from novelgen_obs import get_logger, set_request_id, emit_bedrock_tokens, emit_cross_team_denied

set_request_id("req-abc")
log = get_logger("api-service")
log.info("processing request", extra={"route": "/api/v1/novels"})

emit_bedrock_tokens(team_id="t1", stage="chapter", model="claude-sonnet-4-7",
                   input_tokens=1200, output_tokens=3100)
emit_cross_team_denied(team_id="t1")
```
