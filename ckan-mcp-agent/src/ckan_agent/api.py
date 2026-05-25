"""FastAPI wrapper exposing the agent as a REST service."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import get_settings
from .factory import AgentSession

log = logging.getLogger("ckan-agent-api")

_RESOURCES_RE = re.compile(
    r"<!--RESOURCES_JSON-->\s*(.*?)\s*<!--/RESOURCES_JSON-->",
    re.DOTALL,
)
_URL_RE = re.compile(r"https?://[^\s\)\]>\"'`]+")
_EXT_FORMAT = {
    ".csv": "CSV", ".json": "JSON", ".geojson": "GEOJSON", ".txt": "TXT",
    ".pdf": "PDF", ".shp": "SHP", ".xlsx": "XLSX", ".xls": "XLS",
    ".zip": "ZIP", ".kml": "KML", ".xml": "XML", ".rdf": "RDF",
}
_SEGMENT_FORMAT = {
    "csv": "CSV", "json": "JSON", "geojson": "GEOJSON", "txt": "TXT",
    "pdf": "PDF", "shp": "SHP", "xlsx": "XLSX", "xls": "XLS",
    "zip": "ZIP", "kml": "KML", "xml": "XML", "rdf": "RDF",
    "wfs": "WFS", "wms": "WMS", "wcs": "WCS",
}
_NON_DATA_HOSTS = frozenset({
    "creativecommons.org", "opensource.org", "www.gnu.org",
    "www.w3.org", "schema.org", "purl.org",
})

# Formats where the file content is plain text and worth embedding inline.
_DOWNLOADABLE_FORMATS = frozenset({
    "CSV", "JSON", "GEOJSON", "TXT",
    "XML", "RDF", "KML", "WMS", "WFS", "WCS",
})

# Cap embedded content per resource to keep responses bounded. CKAN files can
# easily exceed several MB; truncating preserves the schema/header for the
# caller while keeping the JSON payload manageable.
_MAX_CONTENT_BYTES = 200_000  # ~200 KB per resource
_DOWNLOAD_TIMEOUT_SECONDS = 20.0
_DOWNLOAD_CONCURRENCY = 4


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None


class Resource(BaseModel):
    name: str
    url: str
    format: str
    content: str | None = None


class ChatResponse(BaseModel):
    text: str
    resources: list[Resource]


def _extract_urls_fallback(text: str) -> list[Resource]:
    seen: set[str] = set()
    resources = []
    for url in _URL_RE.findall(text):
        if url in seen:
            continue
        seen.add(url)
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower().lstrip("www.")
        except Exception:
            host = ""
        if host in _NON_DATA_HOSTS:
            continue
        lower = url.lower()
        segment = lower.rstrip("/").split("/")[-1].split("?")[0]
        fmt = (
            next((v for k, v in _EXT_FORMAT.items() if segment.endswith(k)), None)
            or _SEGMENT_FORMAT.get(segment)
        )
        if fmt is None:
            continue
        name = url.rstrip("/").split("/")[-1].split("?")[0] or url
        resources.append(Resource(name=name, url=url, format=fmt, content=None))
    return resources


def parse_agent_reply(raw: str) -> tuple[str, list[Resource]]:
    matches = list(_RESOURCES_RE.finditer(raw))
    if not matches:
        resources = _extract_urls_fallback(raw)
        if resources:
            log.info("parse_agent_reply: no marker block found; extracted %d URLs from text", len(resources))
        return raw, resources
    if len(matches) > 1:
        log.warning("parse_agent_reply: %d resource blocks found; only first used", len(matches))
    json_block = matches[0].group(1)
    try:
        items = json.loads(json_block)
        if isinstance(items, dict):
            # model wrapped array: {"resources": [...]} or {"data": [...]}
            for key in ("resources", "data", "items", "results"):
                if isinstance(items.get(key), list):
                    items = items[key]
                    break
            else:
                raise ValueError(f"Expected JSON array, got object with keys: {list(items)}")
        if not isinstance(items, list):
            raise ValueError(f"Expected JSON array, got {type(items).__name__}")
        resources = [Resource(**item) for item in items]
    except Exception:
        log.warning("parse_agent_reply: could not parse resource block", exc_info=True)
        return raw, []
    text = _RESOURCES_RE.sub("", raw).strip()
    return text, resources


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str | None:
    """GET a URL and return up to _MAX_CONTENT_BYTES of decoded text.

    Returns None on any error (timeout, non-2xx, decode failure, oversize fetch).
    """
    try:
        resp = await client.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("download failed for %s: %s", url, exc)
        return None

    raw = resp.content[:_MAX_CONTENT_BYTES]
    encoding = resp.encoding or "utf-8"
    try:
        text = raw.decode(encoding, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")

    if len(resp.content) > _MAX_CONTENT_BYTES:
        text += f"\n\n[…truncated at {_MAX_CONTENT_BYTES} bytes; original size {len(resp.content)} bytes]"
    return text


async def _fill_missing_content(resources: list[Resource]) -> None:
    """Mutate `resources` in place: download CSV/JSON/GEOJSON/TXT entries with
    content=None. Failures leave content as None.

    Concurrency capped at _DOWNLOAD_CONCURRENCY to be polite to portals.
    """
    targets = [
        r for r in resources
        if r.content is None and r.format.upper() in _DOWNLOADABLE_FORMATS
    ]
    if not targets:
        return

    log.info("Downloading %d resources whose content was missing", len(targets))
    sem = asyncio.Semaphore(_DOWNLOAD_CONCURRENCY)

    async with httpx.AsyncClient() as client:
        async def fetch_one(resource: Resource) -> None:
            async with sem:
                resource.content = await _fetch_text(client, resource.url)

        await asyncio.gather(*(fetch_one(r) for r in targets), return_exceptions=False)


_session: AgentSession | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _session
    settings = get_settings()
    log.info("Starting CKAN agent with provider=%s", settings.llm_provider)
    _session = AgentSession(settings)
    await _session.__aenter__()
    try:
        yield
    finally:
        if _session is not None:
            await _session.__aexit__(None, None, None)
            _session = None


app = FastAPI(title="CKAN Agent API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _session is None:
        raise HTTPException(status_code=503, detail="Agent session not initialised")
    query = req.query
    if req.base_url:
        query = f"[Target portal: {req.base_url}] {query}"
    query += (
        "\n\n[SYSTEM REMINDER] After your answer, you MUST append this block "
        "(replace [] with the actual resources array — empty array [] if none found):\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    raw = await _session.run(query)
    text, resources = parse_agent_reply(raw)
    await _fill_missing_content(resources)
    return ChatResponse(text=text, resources=resources)


def run() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )
    uvicorn.run(
        "ckan_agent.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
