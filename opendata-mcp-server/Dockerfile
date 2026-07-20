FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Build context is the repo root (set via docker-compose / CI) for consistency
# with the other MCP images (R1). This product server is a pure HTTP proxy to
# the backend, so it does NOT need the shared opendata_core package.
COPY opendata-mcp-server/pyproject.toml opendata-mcp-server/README.md ./
COPY opendata-mcp-server/src ./src
RUN pip install --upgrade pip && pip install .

RUN useradd --system --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

ENV TRANSPORT=streamable-http \
    HOST=0.0.0.0 \
    PORT=8093 \
    MCP_PATH=/mcp \
    OPENDATA_API_BASE_URL=http://opendata-backend:8000 \
    LOG_LEVEL=INFO

EXPOSE 8093

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" > /dev/null || exit 1

CMD ["opendata-mcp-server"]
