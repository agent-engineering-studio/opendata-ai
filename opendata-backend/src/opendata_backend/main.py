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
from fastapi.responses import JSONResponse

from .config import get_settings
from .db.session import create_database, set_session_factory
from .factory import OrchestratorSession
from .routers import api_keys, datasets, me, webhooks
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


app = FastAPI(title="opendata-backend", version="0.1.0", lifespan=lifespan)


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
app.include_router(me.router)
app.include_router(api_keys.router)
app.include_router(webhooks.router)


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
