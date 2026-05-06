"""EventBridge PutEvents helper for U5 Consistency."""

from __future__ import annotations

import json
from uuid import UUID

import aioboto3


class ConsistencyEventPublisher:
    def __init__(self, bus_name: str = "default", region: str = "us-east-1") -> None:
        self._bus = bus_name
        self._region = region
        self._session = aioboto3.Session()

    async def publish_report_ready(
        self,
        *,
        generation_id: UUID,
        team_id: UUID,
        scan_from: int,
        scan_to: int,
        conflict_count: int,
        memory_unavailable: bool,
    ) -> None:
        detail = {
            "generation_id": str(generation_id),
            "team_id": str(team_id),
            "scan_from": scan_from,
            "scan_to": scan_to,
            "conflict_count": conflict_count,
            "memory_unavailable": memory_unavailable,
        }
        async with self._session.client("events", region_name=self._region) as client:
            await client.put_events(
                Entries=[
                    {
                        "Source": "novelgen.consistency",
                        "DetailType": "consistency.report_ready",
                        "Detail": json.dumps(detail, default=str),
                        "EventBusName": self._bus,
                    }
                ]
            )
