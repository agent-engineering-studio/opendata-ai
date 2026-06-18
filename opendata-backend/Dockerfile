# ── Build stage: toolchain C + Rust per le estensioni native ──
# Alcune dipendenze transitive (es. wkb-wkt-converter, pyo3/maturin) NON hanno
# wheel precompilati per tutte le piattaforme e vanno compilate da sorgente →
# servono un linker C (`cc`) e il toolchain Rust. Restano nel solo builder;
# l'immagine runtime resta slim.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Toolchain Rust (cargo/rustc) per le build pyo3/maturin.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Build context is the repo root.
COPY opendata_core/pyproject.toml opendata_core/README.md /opendata_core/
COPY opendata_core/src /opendata_core/src
RUN pip install --upgrade pip && pip install /opendata_core

COPY opendata-backend/pyproject.toml opendata-backend/README.md opendata-backend/alembic.ini ./
COPY opendata-backend/src ./src
COPY opendata-backend/migrations ./migrations
COPY opendata-backend/scripts ./scripts
RUN pip install --pre ".[azure,claude]"

# ── Runtime stage: slim, senza toolchain ──
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pacchetti Python installati + console scripts (alembic, opendata-backend-api…)
# dal builder. Il pacchetto opendata_backend è installato in site-packages, quindi
# a runtime servono solo i file non pacchettizzati (alembic.ini, migrations, scripts).
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY opendata-backend/alembic.ini ./
COPY opendata-backend/migrations ./migrations
COPY opendata-backend/scripts ./scripts

RUN chmod +x ./scripts/migrate.sh \
    && useradd --system --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT}/health" || exit 1

CMD ["./scripts/migrate.sh"]
