# novelgen-api

FastAPI service for `/api/v1/*`.

## Routes (U2 scope)

- `POST /api/v1/novels/upload` (multipart, `Idempotency-Key`, `?force=true`)
- `POST /api/v1/novels/download` `{title, engines?}`
- `POST /api/v1/novels/download/confirm` `{title, source, url}`
- `POST /api/v1/novels/crawl` `{url}`
- `GET /api/v1/novels`
- `GET /api/v1/novels/{id}`
- `DELETE /api/v1/novels/{id}`
- `GET /healthz`

## Environment

```
COGNITO_USER_POOL_ID / COGNITO_APP_CLIENT_ID
NOVELS_BUCKET / TENANCY_TABLE / JOBS_TABLE
INGESTION_STATE_MACHINE_ARN
AWS_REGION (default us-east-1)
```

## Run locally

```bash
uv run uvicorn novelgen_api.main:app --reload --port 8000
```
