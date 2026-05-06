# novelgen-auth-adapter

Cognito JWT verification + Principal resolution + authorization decorators.

## Usage

```python
from fastapi import FastAPI
from novelgen_auth import (
    CognitoJwtVerifier,
    JwtVerifierConfig,
    PrincipalDep,
    require_role,
    require_team_access,
)
from novelgen_auth.principal import set_verifier
from novelgen_types.identity import GlobalRole, Principal

app = FastAPI()

@app.on_event("startup")
def _init_auth() -> None:
    set_verifier(CognitoJwtVerifier(JwtVerifierConfig(
        user_pool_id="...", app_client_id="...", region="us-east-1"
    )))

@app.get("/api/v1/teams/{team_id}/novels")
@require_team_access("team_id")
async def list_novels(team_id: str, principal: Principal = PrincipalDep) -> list:
    return []

@app.get("/api/v1/admin/users")
@require_role(GlobalRole.ADMIN)
async def admin_users(principal: Principal = PrincipalDep) -> list:
    return []
```
