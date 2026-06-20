"""Dataset endpoints — search, fetch, classify.

POST /chat is kept as an alias of /datasets/search so the existing frontend
keeps working unchanged during the migration; it will be removed in step 8.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from opendata_core.ckan import CkanClient

from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..cache import by_category as by_category_cache
from ..cache import fetch as fetch_cache
from ..classify import classify_dataset
from ..classify.anthropic_client import Classifier
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..llm_access import LLMAccess, acquire_orchestrator, require_llm_access
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
    # True when the request comes from the /mappa page: the orchestrator biases
    # the agents toward geographic resources (GeoJSON / Shapefile / KML / WMS)
    # and administrative boundaries, instead of tabular CSV/JSON.
    prefer_geo: bool | None = None


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


_MAP_MODE_HINT = (
    "MAP_MODE: l'utente sta visualizzando una mappa. PREFERISCI risorse "
    "geografiche (GeoJSON, Shapefile, KML, GPX, WMS) e confini amministrativi "
    "(regioni, province, comuni) quando opportuno. Evita risorse puramente "
    "tabulari (CSV / JSON di valori) se sono disponibili alternative geografiche."
)


def _wrap_query(query: str, base_url: str | None, prefer_geo: bool | None) -> str:
    """Prepend portal + map-mode hints to the user query without altering its meaning.

    Hints are plain-text directives consumed by the specialist prompts (see
    config.py CKAN_/ISTAT_INSTRUCTIONS). They never run as code.
    """
    parts: list[str] = []
    if base_url:
        # Forwarded only to the CKAN specialist; ISTAT ignores it (its base_url
        # is a separate setting wired into the MCP server).
        parts.append(f"PORTAL_HINT: use base_url={base_url} for all CKAN tool calls.")
    if prefer_geo:
        parts.append(_MAP_MODE_HINT)
    parts.append(f"USER QUERY: {query}")
    return "\n".join(parts)


async def _run_orchestrator(
    sess, settings, query: str, base_url: str | None, prefer_geo: bool | None = None
) -> ChatResponse:
    if sess is None or settings is None:
        raise HTTPException(status_code=503, detail="Backend session not initialised")
    query = _wrap_query(query, base_url, prefer_geo)
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
    # Value card (Fase 2): additiva, best-effort, non blocca la ricerca.
    try:
        from ..value.cards import attach_value_cards

        attach_value_cards(resources)
    except Exception:
        log.warning("attach_value_cards failed", exc_info=True)
    return ChatResponse(text=text, resources=resources)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),
) -> ChatResponse:
    """Back-compat alias of /datasets/search — used by the legacy frontend."""
    log.info("/chat subject=%s byok=%s", user.subject, access.uses_byok)
    async with acquire_orchestrator(access, session_holder.settings) as sess:
        return await _run_orchestrator(
            sess, session_holder.settings, req.query, req.base_url, req.prefer_geo
        )


@router.post("/datasets/search", response_model=ChatResponse)
async def search(
    req: ChatRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),
) -> ChatResponse:
    """Multi-source fan-out (CKAN + ISTAT [+ Eurostat + OECD if enabled])."""
    log.info("/datasets/search subject=%s byok=%s", user.subject, access.uses_byok)
    async with acquire_orchestrator(access, session_holder.settings) as sess:
        return await _run_orchestrator(
            sess, session_holder.settings, req.query, req.base_url, req.prefer_geo
        )


@router.post("/datasets/search/stream")
async def search_stream(
    req: ChatRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),
) -> StreamingResponse:
    """Same as /datasets/search but yields NDJSON progress events while the
    orchestrator runs, then a final `result` line with the parsed payload.

    Stream format (one JSON object per line):
        {"event":"status","source":"ckan","phase":"start"}
        {"event":"status","source":"ckan","phase":"end"}
        {"event":"status","source":"istat","phase":"start"}
        ...
        {"event":"status","source":"synth","phase":"end"}
        {"event":"result","text":"...","resources":[...]}
    """
    log.info("/datasets/search/stream subject=%s byok=%s", user.subject, access.uses_byok)
    settings = session_holder.settings
    if settings is None:
        raise HTTPException(status_code=503, detail="Backend session not initialised")

    query = _wrap_query(req.query, req.base_url, req.prefer_geo)

    async def _one_event(ev):
        """Map an orchestrator event to its NDJSON line (parsing the final result)."""
        if ev.get("event") == "result":
            raw = ev.get("text") or ""
            text, resources = parse_agent_reply(raw)
            await fill_missing_content(resources)
            try:
                await upgrade_sdmx_resources(resources)
            except Exception:
                log.warning("upgrade_sdmx_resources failed", exc_info=True)
            if settings.enable_osm_maps:
                try:
                    await attach_maps(settings.osm_mcp_url, text, resources)
                except Exception:
                    log.warning("attach_maps failed", exc_info=True)
            payload = {
                "event": "result",
                "text": text,
                "resources": [r.model_dump() for r in resources],
            }
            return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        return (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")

    async def _events():
        t0 = time.perf_counter()
        try:
            async with acquire_orchestrator(access, settings) as sess:
                async for ev in sess.run_streaming(query):
                    yield await _one_event(ev)
            log.info("/datasets/search/stream reply in %.0fms", (time.perf_counter() - t0) * 1000)
        except Exception as exc:
            log.exception("/datasets/search/stream failed")
            err = {"event": "error", "message": str(exc)}
            yield (json.dumps(err, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(_events(), media_type="application/x-ndjson")


@router.post("/datasets/by-category", response_model=ChatResponse)
async def by_category(
    req: ByCategoryRequest,
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),
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
    async with acquire_orchestrator(access, session_holder.settings) as sess:
        response = await _run_orchestrator(sess, session_holder.settings, query, req.base_url)
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
    access: LLMAccess = Depends(require_llm_access),  # noqa: ARG001 — gate only
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


# ───────────────────────────── /datasets/proxy ─────────────────────────────
# Static-export frontend can't run Next.js API routes anymore; resources hosted
# on opendata portals usually don't send CORS headers either. We expose a
# server-side proxy here so the UI (e.g. /mappa GeoJSON/Shapefile fetch) can
# pull arbitrary file URLs through the backend's origin.

# Sane defaults — opendata files are sometimes large (shapefile zips, KML).
_PROXY_MAX_BYTES = 64 * 1024 * 1024  # 64 MB
_PROXY_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
# NB: we deliberately do NOT forward `content-length` (nor `content-encoding`).
# httpx with stream=True transparently decompresses gzip/br/deflate bodies, so
# the bytes we re-stream are longer than the upstream `content-length` →
# uvicorn raises "Response content longer than Content-Length" (500). Letting
# StreamingResponse use chunked transfer encoding avoids the mismatch.
_PROXY_FORWARD_HEADERS = {
    "content-type",
    "content-disposition",
    "etag",
    "last-modified",
}


def _validate_proxy_url(raw: str) -> str:
    """Reject obviously malicious / non-public targets before we hit the network."""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Solo schemi http(s) sono accettati")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Hostname mancante nell'URL")
    # Block hostnames that resolve to private/loopback/link-local addresses to
    # prevent the backend from being used as a relay onto internal networks.
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail=f"DNS lookup fallito: {exc}") from exc
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                status_code=403,
                detail=f"L'URL punta a una rete non pubblica ({ip})",
            )
    return raw


@router.get("/datasets/proxy")
async def proxy(
    url: str,
    user: ClerkUser = Depends(enforce_rate_limit),
) -> StreamingResponse:
    """Stream `url` through the backend, forwarding selected headers.

    Used by the static UI to fetch portal resources (GeoJSON, Shapefile zips,
    KML, GPX, CSV) that would otherwise fail browser-side CORS.
    """
    _validate_proxy_url(url)
    log.info("/datasets/proxy subject=%s url=%s", user.subject, url[:200])

    client = httpx.AsyncClient(
        timeout=_PROXY_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "opendata-ai-backend/0.1 (+proxy)"},
    )
    try:
        upstream_req = client.build_request("GET", url)
        upstream = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Errore upstream: {exc}") from exc

    if upstream.status_code >= 400:
        status = upstream.status_code
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=status, detail=f"upstream HTTP {status}")

    # If upstream advertised a length and it's too big, fail fast.
    cl = upstream.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > _PROXY_MAX_BYTES:
                await upstream.aclose()
                await client.aclose()
                raise HTTPException(
                    status_code=413,
                    detail=f"Risorsa troppo grande ({cl} byte > {_PROXY_MAX_BYTES})",
                )
        except ValueError:
            pass  # ignore malformed content-length

    forwarded = {
        k: v for k, v in upstream.headers.items() if k.lower() in _PROXY_FORWARD_HEADERS
    }
    media_type = upstream.headers.get("content-type", "application/octet-stream")

    async def _stream():
        sent = 0
        try:
            async for chunk in upstream.aiter_bytes(chunk_size=64 * 1024):
                sent += len(chunk)
                if sent > _PROXY_MAX_BYTES:
                    log.warning("proxy: aborting %s after %d bytes (limit hit)", url, sent)
                    return
                yield chunk
        finally:
            await upstream.aclose()

    async def _cleanup() -> None:
        await client.aclose()

    return StreamingResponse(
        _stream(),
        media_type=media_type,
        headers=forwarded,
        background=BackgroundTask(_cleanup),
    )
