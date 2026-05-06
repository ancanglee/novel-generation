# novelgen-storage-adapter

S3 + DynamoDB adapters enforcing team-scope prefix checks at runtime.

## Guard Semantics

Every write/read must be given an explicit `team_id` and carries:
- For S3: key must start with `teams/{team_id}/`
- For DynamoDB: PK must start with `TEAM#{team_id}`

Violations raise `TeamScopeViolation` (HTTP 403).

## Usage

```python
from uuid import UUID
from novelgen_storage import S3Adapter, DynamoDBAdapter, build_s3_prefix, build_team_pk

s3 = S3Adapter(bucket="novelgen-novels-dev")
team = UUID("...")
await s3.put_object(team, f"{build_s3_prefix(team)}novels/abc/raw.md", b"# Title\n...")

ddb = DynamoDBAdapter(table_name="novelgen_tenancy_dev")
await ddb.put(team, {"pk": f"{build_team_pk(team)}", "sk": "NOVEL#abc", "title": "..."})
```
