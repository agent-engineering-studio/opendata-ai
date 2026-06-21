"""FastAPI entry point for the unified opendata-backend.

Lifespan wires the multi-source `OrchestratorSession` (CKAN + ISTAT
[+ Eurostat + OECD]) and exposes it to routers via `state.session_holder`.

Endpoints are split per domain into `routers/*`. `/health` lives here as the
single public endpoint that must answer before Clerk auth is enforced.
"""

from __future__ import annotations

import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import redis.asyncio as redis

from .cache.state import set_redis
from .config import get_settings
from .db.session import create_database, set_session_factory
from .factory import OrchestratorSession
from .routers import (
    account,
    api_keys,
    community,
    datasets,
    maturity,
    me,
    programma,
    quality,
    showcases,
    territorio,
    territory,
    usecases,
    value,
    webhooks,
)
from .state import session_holder

log = logging.getLogger("opendata-backend")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    session_holder.settings = settings
    log.info(
        "Starting opendata-backend | provider=%s ckan_mcp=%s istat_mcp=%s db=%s",
        settings.llm_provider,
        settings.ckan_mcp_url,
        settings.istat_mcp_url,
        "configured" if settings.database_url else "off",
    )

    # Database — optional at boot (endpoints that need it will return 503 when
    # it's missing, see `db.session.get_session_factory`).
    if settings.database_url:
        db = create_database(settings.database_url)
        set_session_factory(db.sessionmaker)
        session_holder.database = db
    else:
        log.warning("DATABASE_URL not set — /me/*, /api-keys/* and /datasets/classify will 503")

    # Redis — optional at boot. When missing, caches no-op and rate-limit
    # dependency lets every request through.
    if settings.redis_url:
        try:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            set_redis(redis_client)
            session_holder.redis = redis_client
            log.info("Redis connected at %s", settings.redis_url)
        except Exception:
            log.warning("REDIS_URL set but Redis is unreachable; cache + rate-limit disabled",
                        exc_info=True)
    else:
        log.warning("REDIS_URL not set — cache + rate-limit disabled")

    try:
        session_holder.session = OrchestratorSession(settings)
        await session_holder.session.__aenter__()
        log.info("OrchestratorSession ready — endpoints are now open")
    except Exception:
        log.exception("FATAL: OrchestratorSession failed to start")
        raise
    try:
        yield
    finally:
        if session_holder.session is not None:
            log.info("Shutting down OrchestratorSession")
            await session_holder.session.__aexit__(None, None, None)
            session_holder.session = None
        if session_holder.database is not None:
            await session_holder.database.dispose()
            set_session_factory(None)
            session_holder.database = None
        if session_holder.redis is not None:
            await session_holder.redis.aclose()
            set_redis(None)
            session_holder.redis = None


app = FastAPI(title="opendata-backend", version="0.1.0", lifespan=lifespan)

_allowed_origins = [
    o.strip() for o in get_settings().cors_allow_origins.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[type-arg]
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - t0) * 1000
    log.debug(
        "← %s %s status=%s %.0fms",
        request.method, request.url.path, response.status_code, elapsed,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "Unhandled exception on %s %s:\n%s",
        request.method, request.url.path, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500, content={"detail": str(exc), "type": type(exc).__name__}
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(datasets.router)
app.include_router(account.router)
app.include_router(me.router)
app.include_router(api_keys.router)
app.include_router(webhooks.router)
app.include_router(programma.router)
app.include_router(territorio.router)
app.include_router(maturity.router)
app.include_router(quality.router)
app.include_router(value.router)
app.include_router(territory.router)
app.include_router(showcases.router)
app.include_router(usecases.router)
app.include_router(community.router)

# Mount A2A protocol routes: AgentCard discovery at /.well-known/agent-card.json
# and JSON-RPC under /a2a/. No-op when settings.a2a_enabled is False.
# The auth middleware guards /a2a/ (JSON-RPC) with the same Clerk-JWT / API-key
# rules as the REST surface; AgentCard discovery stays public.
from .a2a import register_a2a, register_a2a_auth  # noqa: E402 — late import
register_a2a(app, get_settings())
register_a2a_auth(app, get_settings())


def run() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    uvicorn.run(
        "opendata_backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
