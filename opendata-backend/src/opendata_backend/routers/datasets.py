"""Dataset endpoints — search, fetch, classify.

POST /chat is kept as an alias of /datasets/search so the existing frontend
keeps working unchanged during the migration; it will be removed in step 8.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from opendata_core.ckan import CkanClient

from ..auth import ClerkUser, require_user
from ..orchestrator.parsing import (
    Resource,
    fill_missing_content,
    parse_agent_reply,
    upgrade_sdmx_resources,
)
from ..osm_map import attach_maps
from ..state import session_holder

log = logging.getLogger("opendata-backend.datasets")

router = APIRouter(tags=["datasets"])


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None


class ChatResponse(BaseModel):
    text: str
    resources: list[Resource]


class ByCategoryRequest(BaseModel):
    category: str
    base_url: str | None = None
    region: str | None = None


class FetchRequest(BaseModel):
    url: str


class FetchResponse(BaseModel):
    url: str
    content: str
    truncated: bool
    size_bytes: int
    content_type: str


class ClassifyRequest(BaseModel):
    dataset_id: str
    taxonomy: list[str]


async def _run_orchestrator(query: str, base_url: str | None) -> ChatResponse:
    sess = session_holder.session
    settings = session_holder.settings
    if sess is None or settings is None:
        raise HTTPException(status_code=503, detail="Backend session not initialised")
    if base_url:
        # Forwarded only to the CKAN specialist as a portal hint; ISTAT ignores it
        # (its base_url is a separate setting wired into the MCP server).
        query = (
            f"PORTAL_HINT: use base_url={base_url} for all CKAN tool calls.\n"
            f"USER QUERY: {query}"
        )
    log.info("orchestrator query: %r", query[:200])
    t0 = time.perf_counter()
    raw = await sess.run(query)
    elapsed = (time.perf_counter() - t0) * 1000
    log.info("orchestrator reply ready in %.0fms, length=%d chars", elapsed, len(raw))
    text, resources = parse_agent_reply(raw)
    await fill_missing_content(resources)
    try:
        await upgrade_sdmx_resources(resources)
    except Exception:
        log.warning("upgrade_sdmx_resources failed", exc_info=True)
    if settings.enable_osm_maps:
        try:
            n = await attach_maps(settings.osm_mcp_url, text, resources)
            if n:
                log.info("attached %d OSM map(s)", n)
        except Exception:
            log.warning("attach_maps failed", exc_info=True)
    return ChatResponse(text=text, resources=resources)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: ClerkUser = Depends(require_user),
) -> ChatResponse:
    """Back-compat alias of /datasets/search — used by the legacy frontend."""
    log.info("/chat subject=%s", user.subject)
    return await _run_orchestrator(req.query, req.base_url)


@router.post("/datasets/search", response_model=ChatResponse)
async def search(
    req: ChatRequest,
    user: ClerkUser = Depends(require_user),
) -> ChatResponse:
    """Multi-source fan-out (CKAN + ISTAT [+ Eurostat + OECD if enabled])."""
    log.info("/datasets/search subject=%s", user.subject)
    return await _run_orchestrator(req.query, req.base_url)


@router.post("/datasets/by-category", response_model=ChatResponse)
async def by_category(
    req: ByCategoryRequest,
    user: ClerkUser = Depends(require_user),
) -> ChatResponse:
    """Search restricted to a category (and optional region)."""
    log.info("/datasets/by-category subject=%s category=%r", user.subject, req.category)
    parts = [f"Find datasets about '{req.category}'"]
    if req.region:
        parts.append(f"in the region of {req.region}")
    parts.append("from the available open data portals.")
    query = " ".join(parts)
    return await _run_orchestrator(query, req.base_url)


@router.post("/datasets/fetch", response_model=FetchResponse)
async def fetch(
    req: FetchRequest,
    user: ClerkUser = Depends(require_user),
) -> FetchResponse:
    """Download a single resource via the shared CkanClient — no LLM involved."""
    log.info("/datasets/fetch subject=%s url=%r", user.subject, req.url)
    async with CkanClient() as client:
        result = await client.download_resource(req.url)
    return FetchResponse(**result)


@router.post("/datasets/classify")
async def classify(
    req: ClassifyRequest,
    user: ClerkUser = Depends(require_user),
) -> dict[str, str]:
    """Stub — implemented in step 6 (Claude Haiku 4.5)."""
    raise HTTPException(
        status_code=501,
        detail="classify endpoint not implemented yet (step 6, Claude Haiku 4.5)",
    )
