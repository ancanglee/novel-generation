# bff-user (U6)

Node 20 + Fastify BFF: thin reverse proxy + Cognito session + SSE relay + CSRF + telemetry.

## Develop
```bash
pnpm --filter @novelgen/bff-user dev
# listens on :3000
```

Required environment:
```
NOVELGEN_ENV=dev
API_BASE_URL=http://localhost:8000
APP_BASE_URL=http://localhost:5173
COGNITO_USER_POOL_ID=ap-northeast-1_xxx
COGNITO_APP_CLIENT_ID=xxxxxxxx
COGNITO_DOMAIN=novelgen-dev.auth.ap-northeast-1.amazoncognito.com
COGNITO_REGION=ap-northeast-1
SESSION_SIGNING_KEY=<32+ chars>
```

## Architecture (F1=A 薄 BFF)

- `session/store.ts` — LRU cache (5k entries, 6h TTL, `updateAgeOnGet`)
- `session/middleware.ts` — verifies `sid` cookie → loads/refreshes tokens
- `security/csrf.ts` — double-submit CSRF with exempt path list
- `proxy/standard.ts` — undici reverse proxy; `X-Upstream-Error` header on 5xx/network
- `proxy/sse.ts` — streaming proxy with `Last-Event-ID` passthrough and client-abort cleanup
- `routes/telemetry.ts` — zod-validated event → CloudWatch EMF

## Test
```bash
pnpm --filter @novelgen/bff-user test
```
Covers cookie signer, session LRU, CSRF guard, EMF shape.
