"""FastAPI app entry point."""

from __future__ import annotations

import os

from fastapi import FastAPI
from novelgen_auth import CognitoJwtVerifier, JwtVerifierConfig
from novelgen_auth.principal import set_verifier

from novelgen_api.errors import install as install_errors
from novelgen_api.routers import admin, conflicts, consistency, critique, novels


def create_app() -> FastAPI:
    app = FastAPI(title="NovelGen API", version="0.1.0")
    install_errors(app)

    @app.on_event("startup")
    def _init_auth() -> None:
        set_verifier(
            CognitoJwtVerifier(
                JwtVerifierConfig(
                    user_pool_id=os.environ["COGNITO_USER_POOL_ID"],
                    app_client_id=os.environ["COGNITO_APP_CLIENT_ID"],
                    region=os.environ.get("AWS_REGION", "us-east-1"),
                )
            )
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(novels.router)
    app.include_router(critique.router)
    app.include_router(consistency.router)
    app.include_router(conflicts.router)
    app.include_router(admin.router, prefix="/api/v1")
    return app


app = create_app()
