"""AgentCore Identity Workload Token client.

Wraps `bedrock-agentcore.get_workload_access_token` and
`bedrock-agentcore.get_resource_oauth2_token`, with a time-to-live cache so
repeated tool invocations don't hammer the data plane.

Usage:
    client = WorkloadIdentityClient(workload_name="novelgen-dev-agent-workload")
    token = await client.get_token("gateway")
    # Header: Authorization: Bearer {token.access_token}
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass

import aioboto3
from cachetools import TTLCache


@dataclass(frozen=True)
class WorkloadToken:
    access_token: str
    expires_at: int  # epoch seconds
    resource: str

    def is_fresh(self, safety_margin_seconds: int = 300) -> bool:
        return time.time() + safety_margin_seconds < self.expires_at


class WorkloadTokenError(Exception):
    """Raised when GetWorkloadAccessToken fails."""


class WorkloadIdentityClient:
    """Async client for AgentCore Workload identity tokens with in-process cache."""

    def __init__(
        self,
        *,
        workload_name: str | None = None,
        region: str = "us-west-2",
        cache_max: int = 128,
        cache_ttl_seconds: int = 3000,  # 50 min; tokens nominally valid 1h
    ) -> None:
        self._workload_name = workload_name or os.environ.get(
            "AGENTCORE_WORKLOAD_NAME", ""
        )
        self._region = region
        self._session = aioboto3.Session()
        self._cache: TTLCache[str, WorkloadToken] = TTLCache(
            maxsize=cache_max, ttl=cache_ttl_seconds
        )
        self._lock = asyncio.Lock()

    @property
    def workload_name(self) -> str:
        if not self._workload_name:
            raise RuntimeError("AGENTCORE_WORKLOAD_NAME not set")
        return self._workload_name

    async def get_token(
        self, resource: str, *, user_token: str | None = None
    ) -> WorkloadToken:
        """Return a cached or freshly-minted token for the given downstream resource.

        `user_token` (optional) is a Cognito JWT that AgentCore Identity uses to
        bind the workload token to a specific user (for audit). Passing None
        yields a pure workload-scoped token.
        """
        key = self._cache_key(resource, user_token)
        cached = self._cache.get(key)
        if cached and cached.is_fresh():
            return cached

        async with self._lock:
            cached = self._cache.get(key)
            if cached and cached.is_fresh():
                return cached

            token = await self._fetch(resource, user_token)
            self._cache[key] = token
            return token

    def invalidate(self, resource: str, *, user_token: str | None = None) -> None:
        self._cache.pop(self._cache_key(resource, user_token), None)

    async def _fetch(self, resource: str, user_token: str | None) -> WorkloadToken:
        async with self._session.client(
            "bedrock-agentcore", region_name=self._region
        ) as data:
            kwargs: dict = {"workloadName": self.workload_name}
            if user_token:
                kwargs["userToken"] = user_token
            try:
                resp = await data.get_workload_access_token(**kwargs)
            except Exception as e:
                raise WorkloadTokenError(
                    f"GetWorkloadAccessToken failed for {resource}: {e}"
                ) from e

        access_token = resp.get("workloadAccessToken") or resp.get("accessToken")
        if not access_token:
            raise WorkloadTokenError(
                f"missing workloadAccessToken in response for {resource}"
            )
        expires_in = int(resp.get("expiresIn", 3600))
        return WorkloadToken(
            access_token=access_token,
            expires_at=int(time.time()) + expires_in,
            resource=resource,
        )

    @staticmethod
    def _cache_key(resource: str, user_token: str | None) -> str:
        if not user_token:
            return f"{resource}::anon"
        digest = hashlib.sha256(user_token.encode("utf-8")).hexdigest()[:16]
        return f"{resource}::{digest}"
