FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Build context is the repo root (set via docker-compose) so that the shared
# opendata-core package can be copied in alongside this service's source.
COPY opendata_core/pyproject.toml opendata_core/README.md /opendata_core/
COPY opendata_core/src /opendata_core/src
RUN pip install --no-cache-dir /opendata_core

COPY osm-mcp/pyproject.toml ./
COPY osm-mcp/src/ src/
RUN pip install --no-cache-dir .

ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import socket,sys; socket.create_connection(('localhost',8080),3).close()" || exit 1

CMD ["python", "-m", "osm_mcp.server"]
