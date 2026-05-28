"""FastAPI wrapper exposing the ISTAT agent as a REST service.

Response contract is symmetric with ckan-mcp-agent: every reply is a narrative
paragraph followed by a `<!--RESOURCES_JSON-->…<!--/RESOURCES_JSON-->` block.
The block is parsed out into a `resources` array; the narrative becomes `text`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import get_settings
from .factory import AgentSession

log = logging.getLogger("istat-agent-api")

_RESOURCES_RE = re.compile(
    r"<!--RESOURCES_JSON-->\s*(.*?)\s*<!--/RESOURCES_JSON-->",
    re.DOTALL,
)
_URL_RE = re.compile(r"https?://[^\s\)\]>\"'`]+")
_EXT_FORMAT = {
    ".csv": "CSV", ".json": "JSON", ".txt": "TXT", ".xml": "XML",
    ".pdf": "PDF", ".xlsx": "XLSX", ".xls": "XLS", ".zip": "ZIP",
}
_SEGMENT_FORMAT = {
    "csv": "CSV", "json": "JSON", "txt": "TXT", "xml": "XML",
    "pdf": "PDF", "xlsx": "XLSX", "xls": "XLS", "zip": "ZIP",
}
_NON_DATA_HOSTS = frozenset({
    "creativecommons.org", "opensource.org", "www.gnu.org",
    "www.w3.org", "schema.org", "purl.org",
})

_DOWNLOADABLE_FORMATS = frozenset({"CSV", "JSON", "TXT", "XML"})

_MAX_CONTENT_BYTES = 200_000  # ~200 KB per resource
_DOWNLOAD_TIMEOUT_SECONDS = 30.0
_DOWNLOAD_CONCURRENCY = 4

_BINARY_MAGIC = (
    b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",
    b"\x1f\x8b", b"%PDF", b"\xd0\xcf\x11\xe0",
    b"7z\xbc\xaf'\x1c", b"Rar!\x1a\x07", b"BZh",
    b"\x89PNG", b"\xff\xd8\xff", b"GIF8",
)


def _is_binary(raw: bytes) -> bool:
    if not raw:
        return False
    if any(raw.startswith(sig) for sig in _BINARY_MAGIC):
        return True
    sample = raw[:1024]
    if b"\x00" in sample:
        return True
    nonprintable = sum(
        1 for b in sample
        if b < 0x09 or (0x0e <= b < 0x20 and b not in (0x09, 0x0a, 0x0d))
    )
    return nonprintable / max(len(sample), 1) > 0.30


class ChatRequest(BaseModel):
    query: str
    base_url: str | None = None  # optional override for the SDMX endpoint


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
    resources: list[Resource] = []
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
            log.info(
                "parse_agent_reply: no marker block found; extracted %d URLs from text",
                len(resources),
            )
        return raw, resources
    if len(matches) > 1:
        log.warning(
            "parse_agent_reply: %d resource blocks found; only first used", len(matches)
        )
    json_block = matches[0].group(1)
    try:
        items = json.loads(json_block)
        if isinstance(items, dict):
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
    try:
        resp = await client.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("download failed for %s: %s", url, exc)
        return None

    raw = resp.content[:_MAX_CONTENT_BYTES]
    if _is_binary(raw):
        log.info("skip binary content for %s", url)
        return None

    encoding = resp.encoding or "utf-8"
    try:
        text = raw.decode(encoding, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")

    if len(resp.content) > _MAX_CONTENT_BYTES:
        text += (
            f"\n\n[…truncated at {_MAX_CONTENT_BYTES} bytes; "
            f"original size {len(resp.content)} bytes]"
        )
    return text


async def _fill_missing_content(resources: list[Resource]) -> None:
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
    log.info(
        "Starting ISTAT agent | provider=%s mcp_url=%s",
        settings.llm_provider, settings.mcp_server_url,
    )
    try:
        _session = AgentSession(settings)
        await _session.__aenter__()
        log.info("AgentSession ready — POST /chat is now open")
    except Exception:
        log.exception("FATAL: AgentSession failed to start")
        raise
    try:
        yield
    finally:
        if _session is not None:
            log.info("Shutting down AgentSession")
            await _session.__aexit__(None, None, None)
            _session = None


app = FastAPI(title="ISTAT Agent API", version="0.1.0", lifespan=lifespan)


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
        raise HTTPException(status_code=503, detail="Agent session not initialised")
    query = req.query
    if req.base_url:
        query = (
            f"SDMX_HINT: use base_url={req.base_url} for all ISTAT tool calls.\n"
            f"USER QUERY: {query}"
        )
    query += (
        "\n\n[SYSTEM REMINDER] After your narrative, you MUST append this block "
        "(replace [] with the actual resources array — empty array [] if none found):\n"
        "<!--RESOURCES_JSON-->\n"
        "[]\n"
        "<!--/RESOURCES_JSON-->"
    )
    log.info("chat query: %r", query[:200])
    t0 = time.perf_counter()
    raw = await _session.run(query)
    elapsed = (time.perf_counter() - t0) * 1000
    log.info("chat reply ready in %.0fms, length=%d chars", elapsed, len(raw))
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
        "istat_agent.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
