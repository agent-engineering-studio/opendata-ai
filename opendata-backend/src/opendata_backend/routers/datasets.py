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

from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..cache import by_category as by_category_cache
from ..cache import fetch as fetch_cache
from ..classify import classify_dataset
from ..classify.anthropic_client import Classifier
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..orchestrator.parsing import (
    Resource,
    fill_missing_content,
    parse_agent_reply,
    upgrade_sdmx_resources,
)
from ..osm_map import attach_maps
from ..shared.ratelimit import enforce_rate_limit
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
    source: str
    dataset_id: str
    dataset_name: str
    dataset_description: str | None = None
    taxonomy: list[str]


class ClassifyResponse(BaseModel):
    source: str
    dataset_id: str
    scores: dict[str, float]
    model: str
    cached: bool


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
    user: ClerkUser = Depends(enforce_rate_limit),
) -> ChatResponse:
    """Back-compat alias of /datasets/search — used by the legacy frontend."""
    log.info("/chat subject=%s", user.subject)
    return await _run_orchestrator(req.query, req.base_url)


@router.post("/datasets/search", response_model=ChatResponse)
async def search(
    req: ChatRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> ChatResponse:
    """Multi-source fan-out (CKAN + ISTAT [+ Eurostat + OECD if enabled])."""
    log.info("/datasets/search subject=%s", user.subject)
    return await _run_orchestrator(req.query, req.base_url)


@router.post("/datasets/by-category", response_model=ChatResponse)
async def by_category(
    req: ByCategoryRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> ChatResponse:
    """Search restricted to a category (and optional region). 5-min Redis cache."""
    log.info("/datasets/by-category subject=%s category=%r", user.subject, req.category)
    cached = await by_category_cache.get(req.category, req.base_url, req.region)
    if cached is not None:
        log.info("by_category cache HIT category=%r", req.category)
        return ChatResponse.model_validate(cached)
    parts = [f"Find datasets about '{req.category}'"]
    if req.region:
        parts.append(f"in the region of {req.region}")
    parts.append("from the available open data portals.")
    query = " ".join(parts)
    response = await _run_orchestrator(query, req.base_url)
    await by_category_cache.set(
        req.category, req.base_url, req.region, response.model_dump()
    )
    return response


@router.post("/datasets/fetch", response_model=FetchResponse)
async def fetch(
    req: FetchRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> FetchResponse:
    """Download a single resource via the shared CkanClient — 6h Redis cache."""
    log.info("/datasets/fetch subject=%s url=%r", user.subject, req.url)
    cached = await fetch_cache.get(req.url)
    if cached is not None:
        log.info("fetch cache HIT url=%r", req.url)
        return FetchResponse(**cached)
    async with CkanClient() as client:
        result = await client.download_resource(req.url)
    await fetch_cache.set(req.url, result)
    return FetchResponse(**result)


@router.post("/datasets/classify", response_model=ClassifyResponse)
async def classify(
    req: ClassifyRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> ClassifyResponse:
    """Score a dataset against a caller-supplied taxonomy with Claude Haiku 4.5.

    Order of resolution: Redis cache (24h) → Postgres durable cache → Anthropic.
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="classify requires ANTHROPIC_API_KEY",
        )
    if not req.taxonomy:
        raise HTTPException(status_code=400, detail="taxonomy must be non-empty")

    classifier = Classifier(
        api_key=settings.anthropic_api_key,
        model=settings.claude_classify_model,
    )
    result = await classify_dataset(
        session,
        classifier,
        source=req.source,
        dataset_id=req.dataset_id,
        dataset_name=req.dataset_name,
        dataset_description=req.dataset_description,
        taxonomy=req.taxonomy,
    )
    log.info(
        "/datasets/classify subject=%s source=%s dataset=%s cached=%s",
        user.subject, req.source, req.dataset_id, result.cached,
    )
    return ClassifyResponse(
        source=result.source,
        dataset_id=result.dataset_id,
        scores=result.scores,
        model=result.model,
        cached=result.cached,
    )
