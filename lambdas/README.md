# AWS Lambda Functions

| Function | Trigger | Purpose |
|---|---|---|
| `pre-signup` | Cognito PreSignUp | Auto-create personal Team + User row on first sign-up |
| `daily-cost-aggregator` | EventBridge cron (02:00 UTC) | Aggregate per-team Bedrock token usage → DynamoDB `novelgen_*_config` |
| `daily-audit-archiver` | EventBridge cron (03:00 UTC) | Archive 90d-old audit events from DynamoDB to S3 Glacier |

## Packaging

CDK deploys each lambda via `Code.from_asset("../../lambdas/<name>")` (see `infra/cdk/stacks/`).
Dependencies are installed from the lambda's own `pyproject.toml` by the CDK asset bundler.

## Local testing

```bash
cd lambdas/pre-signup
uv run pytest
```

Tests use [`moto`](https://github.com/getmoto/moto) to mock AWS services.
