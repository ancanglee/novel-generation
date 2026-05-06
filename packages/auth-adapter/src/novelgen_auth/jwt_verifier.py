"""Cognito JWT verification with JWKs caching.

Meets NFR-3.1 (p99 < 200ms authentication) by caching JWKs locally.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from cachetools import TTLCache
from jwt.algorithms import RSAAlgorithm

from novelgen_types.errors import AuthError


@dataclass(frozen=True)
class JwtVerifierConfig:
    user_pool_id: str
    app_client_id: str
    region: str = "us-east-1"
    jwks_ttl_seconds: int = 900  # 15 minutes
    leeway_seconds: int = 30

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer}/.well-known/jwks.json"


class CognitoJwtVerifier:
    """Verifies Cognito id_token signatures. Caches JWKs in-process."""

    def __init__(self, config: JwtVerifierConfig, http_client: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http_client or httpx.Client(timeout=5.0)
        self._jwks_cache: TTLCache[str, dict[str, Any]] = TTLCache(
            maxsize=1, ttl=config.jwks_ttl_seconds
        )

    def _fetch_jwks(self) -> dict[str, Any]:
        cached = self._jwks_cache.get("jwks")
        if cached is not None:
            return cached
        resp = self._http.get(self._config.jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
        self._jwks_cache["jwks"] = jwks
        return jwks

    def _get_signing_key(self, kid: str) -> Any:
        jwks = self._fetch_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(key)
        # Refresh once in case of key rotation
        self._jwks_cache.pop("jwks", None)
        jwks = self._fetch_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(key)
        raise AuthError(f"no matching JWK for kid={kid}")

    def verify(self, token: str) -> dict[str, Any]:
        """Return verified claims or raise AuthError."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as e:
            raise AuthError(f"invalid token header: {e}") from e

        kid = header.get("kid")
        if not kid:
            raise AuthError("missing kid in token header")

        signing_key = self._get_signing_key(kid)

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._config.app_client_id,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthError("token expired") from e
        except jwt.InvalidTokenError as e:
            raise AuthError(f"invalid token: {e}") from e

        if claims.get("token_use") != "id":
            raise AuthError("expected id_token")

        # Cache-side check for timing attacks (rare)
        if claims.get("iss") != self._config.issuer:
            raise AuthError("issuer mismatch")

        return claims

    def close(self) -> None:
        self._http.close()
