"""Unified exception handlers for FastAPI (R10)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from novelgen_types.errors import NovelGenError


def install(app: FastAPI) -> None:
    @app.exception_handler(NovelGenError)
    async def handle_novelgen_error(request: Request, exc: NovelGenError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": str(exc.message or exc),
                    "request_id": request.headers.get("x-request-id", ""),
                }
            },
        )
