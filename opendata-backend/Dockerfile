FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Build context is the repo root.
COPY opendata_core/pyproject.toml opendata_core/README.md /opendata_core/
COPY opendata_core/src /opendata_core/src
RUN pip install --upgrade pip && pip install /opendata_core

COPY opendata-backend/pyproject.toml opendata-backend/README.md ./
COPY opendata-backend/src ./src
RUN pip install --pre ".[azure,claude]"

RUN useradd --system --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT}/health" || exit 1

CMD ["opendata-backend-api"]
