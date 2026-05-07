# worker-moderation: Python 3.12 worker.
# U1 pre-builds this image for V2 readiness; service runs at desired_count=0
# by default (see aidlc-docs/construction/U5-critic/nfr-design/logical-components.md).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY packages/shared-types-py /app/packages/shared-types-py
COPY packages/auth-adapter /app/packages/auth-adapter
COPY packages/storage-adapter /app/packages/storage-adapter
COPY packages/observability-adapter /app/packages/observability-adapter
COPY packages/memory-facade /app/packages/memory-facade
COPY services/worker-moderation /app/services/worker-moderation
COPY pyproject.toml /app/pyproject.toml

RUN uv pip install --system \
    -e /app/packages/shared-types-py \
    -e /app/packages/auth-adapter \
    -e /app/packages/storage-adapter \
    -e /app/packages/observability-adapter \
    -e /app/packages/memory-facade \
    -e /app/services/worker-moderation

STOPSIGNAL SIGTERM

CMD ["python", "-m", "worker_moderation.main"]
