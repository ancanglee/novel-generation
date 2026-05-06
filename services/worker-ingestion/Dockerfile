FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Native deps for lxml (libxml2/libxslt) and pdfplumber (poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 libxslt1-dev libxml2-dev \
    poppler-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy the monorepo pieces this service needs
COPY packages/shared-types-py /app/packages/shared-types-py
COPY packages/auth-adapter /app/packages/auth-adapter
COPY packages/storage-adapter /app/packages/storage-adapter
COPY packages/observability-adapter /app/packages/observability-adapter
COPY packages/agentcore-browser-pool /app/packages/agentcore-browser-pool
COPY services/worker-ingestion /app/services/worker-ingestion
COPY pyproject.toml /app/pyproject.toml

RUN uv pip install --system -e /app/packages/shared-types-py \
                             -e /app/packages/auth-adapter \
                             -e /app/packages/storage-adapter \
                             -e /app/packages/observability-adapter \
                             -e /app/packages/agentcore-browser-pool \
                             -e /app/services/worker-ingestion

STOPSIGNAL SIGTERM

CMD ["python", "-m", "worker_ingestion.main"]
