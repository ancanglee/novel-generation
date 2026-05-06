# Tests

| Directory | Purpose | Scope |
|---|---|---|
| `tests/security/` | Penetration tests for multi-tenant isolation (US-NFR-03) | Cross-team access matrix; Principal enforcement |
| `tests/integration/` | Cross-package integration + adapter smoke | Type + fact_key + model mapping sanity |
| `tests/e2e/` | End-to-end tests via deployed stacks (Playwright) | Populated per P0 story in U6/U7 |

## Running

```bash
uv run pytest tests/security -ra
uv run pytest tests/integration -ra
```

## CI

`.github/workflows/ci.yaml` runs all tests on every PR. Security tests are **blocking** —
any cross-team guard failure fails the pipeline.
