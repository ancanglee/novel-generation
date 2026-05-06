# novelgen-types

Shared Pydantic domain models used across every Python service and Lambda in NovelGen.

## Exports

- `identity`: `User`, `Team`, `Principal`, `GlobalRole`, `TeamRole`
- `job`: `Job`, `JobStatus`, `JobType`, `is_valid_transition`
- `audit`: `AuditEvent`, `AuditAction`
- `fact`: `Fact`, `FactType`, `build_fact_key`
- `config`: `ModelConfig`, `ConcurrencyConfig`, `AlertRule`, `DEFAULT_MODEL_MAPPING`
- `novel`: `Novel`, `NovelStatus`, `NovelSourceType`
- `errors`: `NovelGenError`, `TeamScopeViolation`, `ForbiddenCrossTeamAccess`, ...
