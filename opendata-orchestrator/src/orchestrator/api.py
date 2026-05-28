"""FastAPI wrapper exposing the orchestrator as a REST service on port 8000.

Endpoint contract is symmetric with ckan_agent.api so the existing Next.js UI
(`opendata-ai-ui`) can repoint AGENT_API_URL at us without code changes:

    POST /chat  {query, base_url?}  ->  {text, resources: [{name,url,format,content?,source?}]}
    GET  /health                    ->  {"status":"ok"}
"""

from __future__ import annotations

import logging
import time
import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Settings, get_settings
from .factory import OrchestratorSession
from .osm_map import attach_maps
from .parsing import (
    Resource,
    fill_missing_content,
    parse_agent_reply,
    upgrade_sdmx_resources,
)

log = logging.getLogger("opendata-orchestrator-api")


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None


class ChatResponse(BaseModel):
    text: str
    resources: list[Resource]


_session: OrchestratorSession | None = None
_settings: Settings | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _session, _settings
    settings = get_settings()
    _settings = settings
    log.info(
        "Starting orchestrator | provider=%s ckan_mcp=%s istat_mcp=%s",
        settings.llm_provider, settings.ckan_mcp_url, settings.istat_mcp_url,
    )
    try:
        _session = OrchestratorSession(settings)
        await _session.__aenter__()
        log.info("OrchestratorSession ready — POST /chat is now open")
    except Exception:
        log.exception("FATAL: OrchestratorSession failed to start")
        raise
    try:
        yield
    finally:
        if _session is not None:
            log.info("Shutting down OrchestratorSession")
            await _session.__aexit__(None, None, None)
            _session = None


app = FastAPI(title="opendata-orchestrator", version="0.1.0", lifespan=lifespan)


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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _session is None:
        raise HTTPException(status_code=503, detail="Orchestrator session not initialised")
    query = req.query
    if req.base_url:
        # Forwarded only to the CKAN specialist as a portal hint; ISTAT ignores it
        # (its base_url is a separate setting wired into the MCP server).
        query = (
            f"PORTAL_HINT: use base_url={req.base_url} for all CKAN tool calls.\n"
            f"USER QUERY: {query}"
        )
    log.info("chat query: %r", query[:200])
    t0 = time.perf_counter()
    raw = await _session.run(query)
    elapsed = (time.perf_counter() - t0) * 1000
    log.info("orchestrator reply ready in %.0fms, length=%d chars", elapsed, len(raw))
    text, resources = parse_agent_reply(raw)
    await fill_missing_content(resources)
    # Upgrade SDMX data resources from the LLM sample to the full series (for the UI).
    try:
        await upgrade_sdmx_resources(resources)
    except Exception:
        log.warning("upgrade_sdmx_resources failed", exc_info=True)
    # Render OSM maps for any GeoJSON resources (best-effort, no LLM).
    if _settings is not None and _settings.enable_osm_maps:
        try:
            n = await attach_maps(_settings.osm_mcp_url, text, resources)
            if n:
                log.info("attached %d OSM map(s)", n)
        except Exception:
            log.warning("attach_maps failed", exc_info=True)
    return ChatResponse(text=text, resources=resources)


def run() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    uvicorn.run(
        "orchestrator.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
