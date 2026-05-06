"""EventBridge PutEvents helper."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import aioboto3


@dataclass(frozen=True)
class GenerationEvent:
    detail_type: str
    generation_id: UUID
    team_id: UUID
    chapter_idx: int | None
    payload: dict[str, Any]
    event_id: str


class EventPublisher:
    def __init__(self, bus_name: str = "default", region: str = "us-east-1") -> None:
        self._bus = bus_name
        self._region = region
        self._session = aioboto3.Session()

    async def publish(self, event: GenerationEvent) -> None:
        detail = {
            "generation_id": str(event.generation_id),
            "team_id": str(event.team_id),
            "chapter_idx": event.chapter_idx,
            "event_id": event.event_id,
            **event.payload,
        }
        async with self._session.client("events", region_name=self._region) as client:
            await client.put_events(
                Entries=[
                    {
                        "Source": "novelgen.generation",
                        "DetailType": event.detail_type,
                        "Detail": json.dumps(detail, default=str),
                        "EventBusName": self._bus,
                    }
                ]
            )
