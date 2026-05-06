"""Authentication & authorization adapter for NovelGen."""

from novelgen_auth.decorators import require_role, require_team_access
from novelgen_auth.jwt_verifier import CognitoJwtVerifier, JwtVerifierConfig
from novelgen_auth.principal import build_principal_from_claims, verify_principal
from novelgen_auth.workload_identity import WorkloadIdentityClient

__all__ = [
    "CognitoJwtVerifier",
    "JwtVerifierConfig",
    "WorkloadIdentityClient",
    "build_principal_from_claims",
    "require_role",
    "require_team_access",
    "verify_principal",
]
