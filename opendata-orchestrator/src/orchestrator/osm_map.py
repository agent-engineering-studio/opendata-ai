"""Render OSM map HTML for geographic resources via the osm-mcp server.

Renderer-only integration: no osm-agent, no LLM. We call the osm-mcp tool
`compose_map_from_resources` directly over MCP streamable-HTTP (the same 3-step
dance the osm-mcp-agent /compose-map endpoint uses) and pull the text/html
EmbeddedResource out of the result. The returned HTML is a self-contained
Leaflet + OpenStreetMap document, embedded inline in the UI as a sandboxed
iframe (`Resource.preview_html`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .parsing import Resource

log = logging.getLogger("orchestrator.osm_map")

_GEO_FORMATS = {"GEOJSON", "TOPOJSON"}
_RENDER_TIMEOUT = 30.0
_RENDER_CONCURRENCY = 3


def _looks_geojson(resource: Resource) -> bool:
    """True if the resource carries GeoJSON content we can hand to osm-mcp."""
    fmt = (resource.format or "").upper()
    if not resource.content:
        return False
    if fmt in _GEO_FORMATS:
        return True
    # Some portals label GeoJSON as plain JSON — sniff the content.
    if fmt == "JSON":
        head = resource.content.lstrip()[:200].lower()
        return '"featurecollection"' in head or '"type"' in head and "feature" in head
    return False


def _parse_streamable_http_response(resp: httpx.Response) -> dict[str, Any]:
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("application/json"):
        return resp.json()
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    return json.loads(payload)
        raise RuntimeError("empty SSE stream from osm-mcp")
    return resp.json()


async def _mcp_call(base_url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """3-step MCP streamable-HTTP tool call (initialize → initialized → tools/call)."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with httpx.AsyncClient(timeout=_RENDER_TIMEOUT) as client:
        init = {
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "opendata-orchestrator", "version": "0.1.0"},
            },
        }
        r1 = await client.post(base_url, json=init, headers=headers)
        r1.raise_for_status()
        session_id = r1.headers.get("Mcp-Session-Id") or r1.headers.get("mcp-session-id")
        sess = dict(headers)
        if session_id:
            sess["Mcp-Session-Id"] = session_id
        await client.post(
            base_url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=sess,
        )
        r3 = await client.post(
            base_url,
            json={
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            headers=sess,
        )
        r3.raise_for_status()
        return _parse_streamable_http_response(r3)


def _extract_html(result: dict[str, Any]) -> str | None:
    """Pull the text/html EmbeddedResource out of an MCP tool result."""
    if "error" in result:
        log.warning("osm-mcp returned error: %s", result["error"])
        return None
    blocks = (result.get("result") or {}).get("content") or []
    for block in blocks:
        if block.get("type") == "resource":
            res = block.get("resource") or {}
            if "html" in (res.get("mimeType") or "") and res.get("text"):
                return res["text"]
    return None


async def _render_one(osm_mcp_url: str, text: str, resource: Resource) -> str | None:
    try:
        result = await _mcp_call(
            osm_mcp_url,
            "compose_map_from_resources",
            {
                "text": text[:280],
                "resources": [resource.model_dump(exclude_none=True, include={"name", "url", "format", "content"})],
                "title": resource.name[:120] if resource.name else None,
            },
        )
        return _extract_html(result)
    except Exception:
        log.warning("osm map render failed for %s", resource.name, exc_info=True)
        return None


async def attach_maps(osm_mcp_url: str, text: str, resources: list[Resource]) -> int:
    """For each GeoJSON resource, render an OSM map and set `preview_html` in place.

    Returns the number of maps successfully attached. Best-effort: failures leave
    `preview_html` as None and never raise.
    """
    targets = [r for r in resources if r.preview_html is None and _looks_geojson(r)]
    if not targets:
        return 0
    log.info("Rendering OSM maps for %d geographic resource(s)", len(targets))
    sem = asyncio.Semaphore(_RENDER_CONCURRENCY)

    async def one(r: Resource) -> bool:
        async with sem:
            html = await _render_one(osm_mcp_url, text, r)
            if html:
                r.preview_html = html
                return True
            return False

    results = await asyncio.gather(*(one(r) for r in targets))
    return sum(results)
