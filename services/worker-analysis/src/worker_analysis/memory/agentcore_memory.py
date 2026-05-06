"""AgentCore Memory wrapper.

The AgentCore Memory Python SDK binding is not yet fully stable. This wrapper
exposes the put/get/query surface the rest of U3 needs. When the SDK matures,
swap the implementation without touching MemoryFacadeImpl.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import aioboto3


@dataclass(frozen=True)
class MemoryItem:
    fact_key: str
    content: dict[str, Any]


class AgentCoreMemoryClient:
    """Thin wrapper around bedrock-agentcore Memory APIs."""

    def __init__(self, region: str = "us-east-1") -> None:
        self._region = region
        self._session = aioboto3.Session()

    @staticmethod
    def namespace(team_id: UUID, novel_id: UUID) -> str:
        return f"{team_id}:{novel_id}"

    async def put_item(
        self, team_id: UUID, novel_id: UUID, fact_key: str, content: dict[str, Any]
    ) -> None:
        ns = self.namespace(team_id, novel_id)
        # Actual SDK call shape will follow bedrock-agentcore-control once public.
        # For now we expose the structured call so MemoryFacadeImpl can be tested
        # against a fake (subclass MemoryAgentCoreMemoryClient in tests).
        raise NotImplementedError(
            f"AgentCore Memory put_item pending SDK release (ns={ns}, key={fact_key})"
        )

    async def put_batch(
        self,
        team_id: UUID,
        novel_id: UUID,
        items: list[MemoryItem],
    ) -> None:
        for item in items:
            await self.put_item(team_id, novel_id, item.fact_key, item.content)

    async def query(
        self, team_id: UUID, novel_id: UUID, query_text: str, top_k: int = 20
    ) -> list[MemoryItem]:
        ns = self.namespace(team_id, novel_id)
        raise NotImplementedError(
            f"AgentCore Memory query pending SDK release (ns={ns}, q={query_text[:40]})"
        )
