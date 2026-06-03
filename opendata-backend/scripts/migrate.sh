#!/usr/bin/env bash
# Container entrypoint that runs Alembic migrations before booting uvicorn.
# Used as `CMD` in the production Dockerfile.
set -euo pipefail

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "Running database migrations…"
  alembic -c /app/alembic.ini upgrade head || {
    echo "FATAL: alembic upgrade failed" >&2
    exit 1
  }
else
  echo "DATABASE_URL not set; skipping migrations."
fi

exec opendata-backend-api
