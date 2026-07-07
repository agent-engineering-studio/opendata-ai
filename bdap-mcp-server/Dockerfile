FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Build context is the repo root (set via docker-compose) so that the shared
# opendata-core package can be copied in alongside this service's source.
COPY opendata_core/pyproject.toml opendata_core/README.md /opendata_core/
COPY opendata_core/src /opendata_core/src
RUN pip install --upgrade pip && pip install /opendata_core

COPY bdap-mcp-server/pyproject.toml bdap-mcp-server/README.md ./
COPY bdap-mcp-server/src ./src
RUN pip install .

RUN useradd --system --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

ENV TRANSPORT=streamable-http \
    HOST=0.0.0.0 \
    PORT=8080 \
    MCP_PATH=/mcp \
    LOG_LEVEL=INFO

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" > /dev/null || exit 1

CMD ["bdap-mcp-server"]
