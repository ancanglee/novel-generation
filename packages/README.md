# Shared Packages

Cross-Unit shared libraries consumed via `uv workspace` path dependencies.

| Package | Purpose | Owner |
|---|---|---|
| `shared-types-py` | Pydantic domain models (Principal, Job, Fact, ...) | U1 |
| `shared-types-ts` | TypeScript mirrors of the above | U1 |
| `auth-adapter` | Cognito JWT + Principal + decorators | U1 |
| `storage-adapter` | S3 / DynamoDB adapters with tenant guards | U1 |
| `observability-adapter` | Structured logging + EMF metrics | U1 |
| `memory-facade` | Abstract interface; concrete impl in U3 | U1 + U3 |
| `api-client-ts` | Generated TS client from OpenAPI | U1 (generated) |
| `ui` | shadcn/ui + business components | U6 |

## Adding a new package

1. Create `packages/<name>/pyproject.toml` (or `package.json`) declaring the package
2. Add to `pyproject.toml` `[tool.uv.workspace] members` list at repo root
3. Consumers add `"novelgen-<name>"` to their `dependencies` and a `[tool.uv.sources]` entry
   pointing to `{ workspace = true }`
