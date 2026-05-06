"""Unified exception handlers for FastAPI (R10)."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
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

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        # 业务路由一律用 detail={'error': {...}} 约定；若 detail 已是该结构，外层扁平化；
        # 否则退回 FastAPI 默认 {'detail': ...} 行为。
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
