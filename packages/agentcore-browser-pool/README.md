# novelgen-browser-pool

Global AgentCore Browser concurrency pool with DynamoDB CAS counter.

- Upper bound 10 concurrent sessions (admin configurable via SSM).
- `acquire()` spins 10 attempts with exponential backoff + jitter.
- `release()` is best-effort and idempotent.
- `cleanup_expired()` reclaims slots held by crashed workers.

## Usage

```python
from novelgen_browser_pool import BrowserPool

pool = BrowserPool(table_name="novelgen_dev_jobs")

async with pool.slot(job_id):
    # use AgentCore Browser
    ...
```
