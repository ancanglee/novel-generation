"""EventBridge PutEvents helper for U5 Critic.

Emits:
- `critic.report_ready` — after CritiqueReport is persisted to DDB.
"""

from __future__ import annotations

import json
from uuid import UUID

import aioboto3


class CriticEventPublisher:
    def __init__(self, bus_name: str = "default", region: str = "us-east-1") -> None:
        self._bus = bus_name
        self._region = region
        self._session = aioboto3.Session()

    async def publish_report_ready(
        self,
        *,
        generation_id: UUID,
        team_id: UUID,
        chapter_idx: int,
        score: int,
        minimal: bool,
    ) -> None:
        detail = {
            "generation_id": str(generation_id),
            "team_id": str(team_id),
            "chapter_idx": chapter_idx,
            "score": score,
            "minimal": minimal,
        }
        async with self._session.client("events", region_name=self._region) as client:
            await client.put_events(
                Entries=[
                    {
                        "Source": "novelgen.critic",
                        "DetailType": "critic.report_ready",
                        "Detail": json.dumps(detail, default=str),
                        "EventBusName": self._bus,
                    }
                ]
            )
