"""U7 Admin router sub-package.

Exposes a single APIRouter (`router`) that aggregates all admin sub-routers
under the `/admin` prefix. Mount from `main.py`:

    app.include_router(admin.router)
"""

from fastapi import APIRouter

from . import (
    alerts,
    audit,
    concurrency,
    model_configs,
    monitoring,
    schemas,
    teams,
    templates,
    users,
)

router = APIRouter(prefix="/admin", tags=["admin"])
for sub in (
    users,
    teams,
    model_configs,
    schemas,
    templates,
    audit,
    monitoring,
    alerts,
    concurrency,
):
    router.include_router(sub.router)

__all__ = ["router"]
