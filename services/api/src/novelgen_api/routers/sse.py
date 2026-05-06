"""SSE endpoints (per-job + per-chapter) using sse-starlette."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, Request
from novelgen_auth.principal import PrincipalDep
from novelgen_types.identity import Principal
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["sse"])

HEARTBEAT_INTERVAL_SECONDS = 15


@router.get("/api/v1/jobs/{job_id}/stream")
async def job_stream(
    job_id: UUID,
    request: Request,
    principal: Principal = PrincipalDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    relay = request.app.state.sse_relay
    subscriber = relay.register(job_id=str(job_id))

    if last_event_id:
        await relay.replay_since(subscriber, last_event_id)

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS
                    )
                    yield {
                        "event": event["type"],
                        "data": event["data"],
                        "id": event["data"].get("event_id", ""),
                    }
                except TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            relay.unregister(subscriber.subscriber_id)

    return EventSourceResponse(event_gen())


@router.get("/api/v1/generations/{gid}/chapters/{n}/stream")
async def chapter_stream(
    gid: UUID,
    n: int,
    request: Request,
    principal: Principal = PrincipalDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    relay = request.app.state.sse_relay
    subscriber = relay.register(generation_id=str(gid), chapter_idx=n)

    if last_event_id:
        await relay.replay_since(subscriber, last_event_id)

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS
                    )
                    yield {
                        "event": event["type"],
                        "data": event["data"],
                        "id": event["data"].get("event_id", ""),
                    }
                except TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            relay.unregister(subscriber.subscriber_id)

    return EventSourceResponse(event_gen())
