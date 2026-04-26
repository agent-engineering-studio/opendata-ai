"""FastAPI wrapper exposing the agent as a REST service."""

from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

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
_URL_RE = re.compile(r'https?://[^\s\)\]>"\']+')
_EXT_FORMAT = {
    ".csv": "CSV", ".json": "JSON", ".geojson": "GEOJSON", ".txt": "TXT",
    ".pdf": "PDF", ".shp": "SHP", ".xlsx": "XLSX", ".xls": "XLS",
    ".zip": "ZIP", ".kml": "KML", ".xml": "XML", ".rdf": "RDF",
}


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
        lower = url.lower()
        fmt = next((v for k, v in _EXT_FORMAT.items() if lower.endswith(k)), "UNKNOWN")
        name = url.rstrip("/").split("/")[-1] or url
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
        if not isinstance(items, list):
            raise ValueError(f"Expected JSON array, got {type(items).__name__}")
        resources = [Resource(**item) for item in items]
    except Exception:
        log.warning("parse_agent_reply: could not parse resource block", exc_info=True)
        return raw, []
    text = _RESOURCES_RE.sub("", raw).strip()
    return text, resources


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
