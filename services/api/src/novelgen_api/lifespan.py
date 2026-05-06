"""FastAPI lifespan: manages SSE relay (SNS subscribe on startup, cleanup on shutdown)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from novelgen_api.services.sse_relay import SseRelay


@asynccontextmanager
async def lifespan(app: FastAPI):
    relay = SseRelay()
    app.state.sse_relay = relay
    try:
        await relay.start()
        yield
    finally:
        await relay.stop()
