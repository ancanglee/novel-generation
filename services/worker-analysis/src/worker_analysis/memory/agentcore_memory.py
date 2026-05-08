"""AgentCore Memory client — real SDK-based implementation.

Wraps `bedrock-agentcore` data-plane APIs:
- `create_event` — append a single conversational or blob event to a session.
- `retrieve_memory_records` — semantic/hybrid retrieval over aggregated memory records.
- `list_events` — raw event history for diagnostics.

Multi-tenancy: we derive `actorId = f"{team_id}:{novel_id}"` for namespace scoping.
The Memory's `memoryStrategies` are configured once at CDK deploy time with namespaces
`["{actorId}/{sessionId}", "{actorId}"]`, which means `RetrieveMemoryRecords` naturally
scopes by team+novel when called with the appropriate namespace string.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import aioboto3
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@dataclass(frozen=True)
class MemoryItem:
    fact_key: str
    content: dict[str, Any]
    fact_type: str | None = None
    source_chapter: int | None = None


@dataclass(frozen=True)
class MemoryRecord:
    """Result returned from RetrieveMemoryRecords."""
    record_id: str
    namespace: str
    content_text: str
    score: float
    metadata: dict[str, Any]


class MemoryWriteError(Exception):
    """Raised when CreateEvent fails after retries — caller must route to DLQ."""


class MemoryReadError(Exception):
    """Raised when RetrieveMemoryRecords fails after retries."""


_TRANSIENT_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "InternalServerException",
    "ServiceUnavailableException",
}


class _TransientAws(Exception):
    """Internal marker for tenacity retry."""


def _is_transient(e: BaseException) -> bool:
    resp = getattr(e, "response", None) or {}
    code = (resp.get("Error") or {}).get("Code")
    if code in _TRANSIENT_CODES:
        return True
    name = type(e).__name__
    return name in {"ReadTimeoutError", "EndpointConnectionError", "ConnectTimeoutError"}


def _retryer() -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        retry=retry_if_exception_type(_TransientAws),
        reraise=True,
    )


class AgentCoreMemoryClient:
    """Async wrapper around AgentCore Memory data plane."""

    def __init__(
        self,
        *,
        memory_id: str | None = None,
        region: str = "us-west-2",
    ) -> None:
        self._region = region
        self._memory_id = memory_id or os.environ.get("AGENTCORE_MEMORY_ID", "")
        self._session = aioboto3.Session()

    @property
    def memory_id(self) -> str:
        if not self._memory_id:
            raise RuntimeError(
                "AGENTCORE_MEMORY_ID env var is not set and no memory_id was passed"
            )
        return self._memory_id

    @staticmethod
    def actor_id(team_id: UUID, novel_id: UUID) -> str:
        return f"{team_id}:{novel_id}"

    @staticmethod
    def namespace(team_id: UUID, novel_id: UUID) -> str:
        """Namespace string matching the strategy namespace template configured at CreateMemory."""
        return f"{team_id}/{novel_id}"

    # ---------------------------------------------------------------- write

    async def put_event(
        self,
        team_id: UUID,
        novel_id: UUID,
        *,
        session_id: str,
        items: list[MemoryItem],
    ) -> None:
        """Append items as a single CreateEvent (conversational payload list).

        If items is empty, this is a no-op.
        """
        if not items:
            return
        payload = [self._item_to_payload(it) for it in items]
        actor = self.actor_id(team_id, novel_id)
        async with self._session.client(
            "bedrock-agentcore", region_name=self._region
        ) as data:
            try:
                async for attempt in _retryer():
                    with attempt:
                        try:
                            await data.create_event(
                                memoryId=self.memory_id,
                                actorId=actor,
                                sessionId=session_id,
                                eventTimestamp=datetime.now(tz=UTC),
                                payload=payload,
                            )
                        except Exception as e:
                            if _is_transient(e):
                                raise _TransientAws(str(e)) from e
                            raise
            except _TransientAws as e:
                raise MemoryWriteError(f"CreateEvent transient after retries: {e}") from e
            except Exception as e:
                raise MemoryWriteError(f"CreateEvent failed: {e}") from e

    async def put_batch(
        self,
        team_id: UUID,
        novel_id: UUID,
        items: list[MemoryItem],
        *,
        session_id: str,
        chunk_size: int = 20,
    ) -> None:
        """Split items into per-CreateEvent chunks (AgentCore caps payload size)."""
        for i in range(0, len(items), chunk_size):
            await self.put_event(
                team_id, novel_id, session_id=session_id, items=items[i : i + chunk_size]
            )

    # ----------------------------------------------------------------- read

    async def retrieve(
        self,
        team_id: UUID,
        novel_id: UUID,
        *,
        query: str,
        top_k: int = 20,
        namespace_suffix: str | None = None,
    ) -> list[MemoryRecord]:
        """Semantic/hybrid retrieve from the configured strategy.

        `namespace_suffix` (optional) is joined to the base `{team}/{novel}` namespace
        to target a more specific strategy slot like "chapters".
        """
        base_ns = self.namespace(team_id, novel_id)
        ns = f"{base_ns}/{namespace_suffix}" if namespace_suffix else base_ns

        async with self._session.client(
            "bedrock-agentcore", region_name=self._region
        ) as data:
            try:
                async for attempt in _retryer():
                    with attempt:
                        try:
                            resp = await data.retrieve_memory_records(
                                memoryId=self.memory_id,
                                namespace=ns,
                                searchCriteria={"searchQuery": query, "topK": top_k},
                            )
                        except Exception as e:
                            if _is_transient(e):
                                raise _TransientAws(str(e)) from e
                            raise
            except _TransientAws as e:
                raise MemoryReadError(f"RetrieveMemoryRecords transient: {e}") from e
            except Exception as e:
                raise MemoryReadError(f"RetrieveMemoryRecords failed: {e}") from e

        results: list[MemoryRecord] = []
        for rec in resp.get("memoryRecordSummaries", []) or resp.get("memoryRecords", []):
            content = rec.get("content") or {}
            text = content.get("text") if isinstance(content, dict) else str(content)
            results.append(
                MemoryRecord(
                    record_id=rec.get("memoryRecordId", ""),
                    namespace=rec.get("namespace", ns),
                    content_text=text or "",
                    score=float(rec.get("score", 0.0)),
                    metadata={k: v for k, v in rec.items() if k not in ("content",)},
                )
            )
        return results

    async def list_events(
        self,
        team_id: UUID,
        novel_id: UUID,
        *,
        session_id: str,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        actor = self.actor_id(team_id, novel_id)
        async with self._session.client(
            "bedrock-agentcore", region_name=self._region
        ) as data:
            resp = await data.list_events(
                memoryId=self.memory_id,
                actorId=actor,
                sessionId=session_id,
                maxResults=max_results,
            )
        return resp.get("events", [])

    # ---------------------------------------------------------------- utils

    @staticmethod
    def _item_to_payload(item: MemoryItem) -> dict[str, Any]:
        content = {
            "fact_key": item.fact_key,
            "content": item.content,
        }
        if item.fact_type:
            content["fact_type"] = item.fact_type
        if item.source_chapter is not None:
            content["source_chapter"] = item.source_chapter
        return {
            "conversational": {
                "role": "USER",
                "content": {"text": json.dumps(content, ensure_ascii=False)},
            }
        }
