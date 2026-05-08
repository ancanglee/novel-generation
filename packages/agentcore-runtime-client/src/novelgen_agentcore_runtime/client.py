"""AgentCore Runtime async client.

Wraps:
- `bedrock-agentcore-control`: create / get / update / delete agent runtime.
- `bedrock-agentcore`: invoke_agent_runtime.

Retry policy: transient AWS exceptions (Throttling / InternalServer / ReadTimeout) are
retried up to 3 times with exponential backoff (base 0.5s, cap 4s). Non-transient errors
propagate immediately.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import aioboto3
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class AgentRuntimeNotReady(Exception):
    """Raised when a runtime ARN exists but its status != READY."""


class RuntimeInvokeError(Exception):
    """Raised when invoke_agent_runtime fails after retries."""


@dataclass(frozen=True)
class AgentRuntimeDescribe:
    arn: str
    runtime_id: str
    status: str
    container_uri: str | None
    role_arn: str | None


_TRANSIENT_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "InternalServerException",
    "ServiceUnavailableException",
    "ProvisionedThroughputExceededException",
}


def _is_transient(exc: BaseException) -> bool:
    # botocore ClientError
    response = getattr(exc, "response", None) or {}
    code = (response.get("Error") or {}).get("Code")
    if code in _TRANSIENT_ERROR_CODES:
        return True
    # read timeout / endpoint connection
    name = type(exc).__name__
    return name in {"ReadTimeoutError", "EndpointConnectionError", "ConnectTimeoutError"}


class _TransientRetry(Exception):
    """Internal marker type so tenacity's retry_if_exception_type can match."""


def _retryer() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type(_TransientRetry),
        reraise=True,
    )


class RuntimeClient:
    """Async boto3 wrapper for AgentCore Runtime.

    A single instance is safe to share across coroutines within one event loop.
    """

    def __init__(self, region: str = "us-west-2") -> None:
        self._region = region
        self._session = aioboto3.Session()

    # --------------------------------------------------------------- control

    async def ensure_runtime(
        self,
        *,
        name: str,
        container_uri: str,
        role_arn: str,
        environment: dict[str, str] | None = None,
        network_mode: str = "PUBLIC",
    ) -> AgentRuntimeDescribe:
        """Create runtime if absent, else return existing describe.

        Idempotency key: `name`. AgentCore control plane enforces unique name per account/region.
        """

        existing = await self._find_by_name(name)
        if existing is not None:
            return existing

        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            try:
                resp = await self._with_retry(
                    ctl.create_agent_runtime,
                    agentRuntimeName=name,
                    agentRuntimeArtifact={
                        "containerConfiguration": {"containerUri": container_uri}
                    },
                    roleArn=role_arn,
                    networkConfiguration={"networkMode": network_mode},
                    environmentVariables=environment or {},
                )
            except Exception:  # pragma: no cover - surfaced to caller
                raise

        return AgentRuntimeDescribe(
            arn=resp["agentRuntimeArn"],
            runtime_id=resp["agentRuntimeId"],
            status=resp.get("status", "CREATING"),
            container_uri=container_uri,
            role_arn=role_arn,
        )

    async def describe(self, runtime_id: str) -> AgentRuntimeDescribe:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            resp = await self._with_retry(ctl.get_agent_runtime, agentRuntimeId=runtime_id)
        return AgentRuntimeDescribe(
            arn=resp["agentRuntimeArn"],
            runtime_id=resp["agentRuntimeId"],
            status=resp.get("status", "UNKNOWN"),
            container_uri=(
                resp.get("agentRuntimeArtifact", {})
                .get("containerConfiguration", {})
                .get("containerUri")
            ),
            role_arn=resp.get("roleArn"),
        )

    async def wait_until_ready(
        self, runtime_id: str, timeout_seconds: int = 120, poll_seconds: float = 5.0
    ) -> AgentRuntimeDescribe:
        """Poll describe until status == READY, else raise AgentRuntimeNotReady."""
        loop_deadline = asyncio.get_event_loop().time() + timeout_seconds
        last: AgentRuntimeDescribe | None = None
        while asyncio.get_event_loop().time() < loop_deadline:
            last = await self.describe(runtime_id)
            if last.status.upper() == "READY":
                return last
            if last.status.upper() in {"CREATE_FAILED", "DELETED", "FAILED"}:
                raise AgentRuntimeNotReady(f"terminal status: {last.status}")
            await asyncio.sleep(poll_seconds)
        raise AgentRuntimeNotReady(
            f"timeout after {timeout_seconds}s, last status={last.status if last else 'unknown'}"
        )

    async def delete(self, runtime_id: str) -> None:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            await self._with_retry(ctl.delete_agent_runtime, agentRuntimeId=runtime_id)

    # ------------------------------------------------------------------ data

    async def invoke(
        self,
        *,
        runtime_arn: str,
        session_id: str,
        trace_id: str | None,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        """Invoke the runtime and stream back response chunks.

        Caller is responsible for joining / parsing the bytes stream.
        """
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        async with self._session.client(
            "bedrock-agentcore", region_name=self._region
        ) as data:
            kwargs: dict[str, Any] = {
                "agentRuntimeArn": runtime_arn,
                "runtimeSessionId": session_id,
                "payload": body,
            }
            if trace_id:
                kwargs["traceId"] = trace_id
            try:
                resp = await self._with_retry(data.invoke_agent_runtime, **kwargs)
            except Exception as e:
                raise RuntimeInvokeError(f"invoke_agent_runtime failed: {e}") from e

            stream = resp.get("response")
            if stream is None:
                # Some SDK responses shape as aiter bytes; fallback to empty.
                return
            async for chunk in stream:
                if isinstance(chunk, dict):
                    # Standard event-stream shape: {"chunk": {"bytes": b"..."}}
                    b = chunk.get("chunk", {}).get("bytes")
                    if b:
                        yield b
                elif isinstance(chunk, (bytes, bytearray)):
                    yield bytes(chunk)

    # ----------------------------------------------------------------- utils

    async def _find_by_name(self, name: str) -> AgentRuntimeDescribe | None:
        async with self._session.client(
            "bedrock-agentcore-control", region_name=self._region
        ) as ctl:
            token: str | None = None
            while True:
                kwargs: dict[str, Any] = {"maxResults": 50}
                if token:
                    kwargs["nextToken"] = token
                resp = await self._with_retry(ctl.list_agent_runtimes, **kwargs)
                for r in resp.get("agentRuntimes", []):
                    if r.get("agentRuntimeName") == name:
                        return AgentRuntimeDescribe(
                            arn=r["agentRuntimeArn"],
                            runtime_id=r["agentRuntimeId"],
                            status=r.get("status", "UNKNOWN"),
                            container_uri=None,
                            role_arn=None,
                        )
                token = resp.get("nextToken")
                if not token:
                    return None

    @staticmethod
    async def _with_retry(fn, /, **kwargs):
        async for attempt in _retryer():
            with attempt:
                try:
                    return await fn(**kwargs)
                except Exception as e:
                    if _is_transient(e):
                        raise _TransientRetry(str(e)) from e
                    raise
        raise RuntimeError("unreachable")  # pragma: no cover
