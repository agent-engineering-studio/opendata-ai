"""Parse the narrative + RESOURCES_JSON contract emitted by each specialist.

Kept symmetrical with ckan_agent.api and istat_agent.api — duplicated by design
(side-by-side layout, no shared package).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel

log = logging.getLogger("orchestrator.parsing")

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

_DOWNLOADABLE_FORMATS = frozenset({
    "CSV", "JSON", "GEOJSON", "TXT",
    "XML", "RDF", "KML", "WMS", "WFS", "WCS",
})

_MAX_CONTENT_BYTES = 200_000
_DOWNLOAD_TIMEOUT_SECONDS = 20.0
_DOWNLOAD_CONCURRENCY = 4

_BINARY_MAGIC = (
    b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08",
    b"\x1f\x8b", b"%PDF", b"\xd0\xcf\x11\xe0",
    b"7z\xbc\xaf'\x1c", b"Rar!\x1a\x07", b"BZh",
    b"\x89PNG", b"\xff\xd8\xff", b"GIF8",
)


SourceTag = Literal["ckan", "istat", "eurostat", "oecd"]


class Resource(BaseModel):
    name: str
    url: str
    format: str
    content: str | None = None
    source: SourceTag | None = None
    # Optional human description (portal notes / SDMX dataflow name) if an agent emits it.
    description: str | None = None


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
    """Split a specialist reply into (narrative, resources).

    Happy path: extract the JSON array between `<!--RESOURCES_JSON-->` markers.
    Fallback: if marker is missing, regex-scan URLs from the narrative and infer
    a format from the file extension.
    Failure: malformed JSON → return raw text and an empty resources list.
    """
    matches = list(_RESOURCES_RE.finditer(raw))
    if not matches:
        resources = _extract_urls_fallback(raw)
        if resources:
            log.info(
                "parse_agent_reply: no marker block; extracted %d URLs", len(resources)
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


async def fill_missing_content(resources: list[Resource]) -> None:
    """Mutate `resources` in place: download text-format entries with content=None."""
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
