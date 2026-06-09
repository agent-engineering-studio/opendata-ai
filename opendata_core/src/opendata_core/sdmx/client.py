"""Async HTTP client for the ISTAT SDMX 2.1 REST API.

Handles content negotiation (SDMX-JSON for metadata, SDMX-CSV for data),
in-memory caching of metadata lookups, and graceful error propagation.

Official endpoint (as of 2025): https://esploradati.istat.it/SDMXWS/rest
Docs: https://github.com/ondata/guida-api-istat

Known ISTAT server behaviours:
  - Rate limit: 5 queries/minute per IP; exceeding blocks access for 1-2 days.
  - SSL certificate issues: verify=False is the recommended workaround.
  - Bug: endPeriod=N returns data up to N+1; use endPeriod=N-1 to get up to N.
  - Format selection via Accept header only (the `format` query param is NOT supported).
  - availableconstraint with Accept: application/json returns empty data {};
    use the SDMX-specific Accept header instead.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from cachetools import TTLCache

DEFAULT_TIMEOUT = float(os.getenv("ISTAT_HTTP_TIMEOUT", "60"))
# Official ISTAT endpoint since 2025 — esploradati.istat.it replaces sdmx.istat.it
DEFAULT_BASE_URL = os.getenv(
    "ISTAT_SDMX_BASE_URL",
    "https://esploradati.istat.it/SDMXWS/rest",
)
USER_AGENT = os.getenv(
    "ISTAT_USER_AGENT",
    "istat-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
CACHE_TTL = int(os.getenv("ISTAT_CACHE_TTL_SECONDS", "3600"))
CACHE_MAXSIZE = int(os.getenv("ISTAT_CACHE_MAXSIZE", "512"))
# L2 persistent cache (file-based) — survives container restarts. Used only for
# slow, stable metadata listings (e.g. the full dataflow catalogue, which takes
# ~20s to fetch from esploradati.istat.it but rarely changes). Set the dir to
# empty string to disable persistence entirely.
PERSISTENT_CACHE_DIR = os.getenv("SDMX_PERSISTENT_CACHE_DIR", "/var/cache/sdmx")
PERSISTENT_CACHE_TTL = int(os.getenv("SDMX_PERSISTENT_CACHE_TTL_SECONDS", "86400"))  # 24h
def _is_persistent_path(path: str) -> bool:
    """Decide whether `path` is worth caching to disk (L2).

    We persist only the full agency catalogue (`dataflow/{agency}`): big response,
    slow to fetch, rarely changes. Per-flow lookups (`dataflow/{agency}/{id}/{ver}`)
    have too high cardinality and stay on L1 only.
    """
    p = path.strip("/")
    return p.startswith("dataflow/") and p.count("/") == 1
# ISTAT has SSL certificate issues; set ISTAT_VERIFY_SSL=true to re-enable.
VERIFY_SSL = os.getenv("ISTAT_VERIFY_SSL", "false").lower() not in {"0", "false", "no"}

# Accept headers validated against esploradati.istat.it (new endpoint, 2025):
#   version=1.0   → HTTP 500 when DB is up (valid, reaches DB layer)      ✅
#   version=1.0.0 → HTTP 406 always (rejected at content-negotiation)     ❌
#   charset=UTF-8 in Accept → rejected (belongs in Content-Type, not Accept)
# Official ISTAT page uses "version=1.0" in all REST examples.
ACCEPT_JSON = "application/vnd.sdmx.structure+json;version=1.0"
ACCEPT_CSV = "application/vnd.sdmx.data+csv;version=1.0.0;labels=both"

log = logging.getLogger("istat-mcp.sdmx")


class SdmxError(RuntimeError):
    """Raised when the SDMX endpoint returns an unexpected payload or HTTP error."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


class SdmxClient:
    """Thin async wrapper around the SDMX 2.1 REST endpoints exposed by ISTAT.

    Usage:
        async with SdmxClient() as c:
            dfs = await c.get_json("dataflow/IT1")
    """

    # Shared cache across instances — metadata is stable enough that we want
    # subsequent tool calls in the same process to benefit.
    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = _normalize_base(base_url)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SdmxClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            verify=VERIFY_SSL,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ────────────────────────────── core HTTP ──────────────────────────────

    async def _get(self, path: str, *, accept: str, params: dict[str, Any] | None = None) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("SdmxClient must be used as an async context manager")
        url = str(self._client.base_url).rstrip("/") + "/" + path.lstrip("/")
        log.debug("SDMX GET %s params=%s", url, params)
        try:
            resp = await self._client.get(
                path,
                headers={"Accept": accept},
                params=params,
            )
        except httpx.HTTPError as exc:
            log.error("SDMX transport error GET %s: %s", url, exc)
            raise SdmxError(f"Transport error on GET {path}: {exc}") from exc

        log.debug(
            "SDMX response %s → HTTP %s content-type=%s size=%d bytes",
            url, resp.status_code, resp.headers.get("content-type", "?"), len(resp.content),
        )
        if resp.status_code == 404:
            log.warning("SDMX 404 on %s", url)
            raise SdmxError(f"Not found on SDMX endpoint: {path}")
        if resp.status_code >= 400:
            snippet = resp.text[:300].replace("\n", " ")
            # 503 with "Cannot serve content type" is a content-negotiation failure,
            # not a server overload — log it clearly to avoid confusion.
            if resp.status_code == 503 and "Cannot serve content type" in snippet:
                log.error(
                    "SDMX content-negotiation failure on %s: server rejected Accept='%s'. "
                    "This is NOT a server overload — the endpoint does not support the "
                    "requested media type. Response: %s",
                    url, accept, snippet,
                )
                raise SdmxError(
                    f"SDMX endpoint at {url} does not support the requested content type "
                    f"(Accept: {accept}). Server message: {snippet}"
                )
            log.error("SDMX HTTP %s on %s: %s", resp.status_code, url, snippet)
            raise SdmxError(f"HTTP {resp.status_code} on GET {path}: {snippet}")
        return resp

    async def get_json(self, path: str, *, params: dict[str, Any] | None = None, cache: bool = True) -> dict[str, Any]:
        """GET an SDMX endpoint requesting SDMX-JSON.

        Caching is a two-tier hierarchy:
          L1: in-memory TTLCache (process-local, short TTL, all paths)
          L2: persistent file cache on disk (survives restarts, long TTL,
              gated to the full catalogue listings via `_is_persistent_path`).

        Lookup order: L1 → L2 → network. Writes happen to whichever tier the
        path qualifies for; an L2 hit is promoted to L1.
        """
        key = ("json", self._base, path, tuple(sorted((params or {}).items())))

        if cache and key in self._cache:
            return self._cache[key]  # type: ignore[return-value]

        persistent = cache and _is_persistent_path(path) and bool(PERSISTENT_CACHE_DIR)
        if persistent:
            hit = self._persistent_read(key)
            if hit is not None:
                self._cache[key] = hit
                log.info("SDMX persistent cache HIT for %s", path)
                return hit

        resp = await self._get(path, accept=ACCEPT_JSON, params=params)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SdmxError(f"Non-JSON response from {path}: {resp.text[:300]}") from exc

        if cache:
            self._cache[key] = payload
        if persistent:
            self._persistent_write(key, payload)
        return payload

    # ───────────────────────── persistent (L2) cache ──────────────────────────

    @staticmethod
    def _key_hash(key: tuple) -> str:
        # Stable digest of the cache key tuple — used as a flat filename.
        raw = json.dumps(key, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:32]

    @classmethod
    def _persistent_path(cls, key: tuple) -> Path:
        return Path(PERSISTENT_CACHE_DIR) / f"{cls._key_hash(key)}.json"

    @classmethod
    def _persistent_read(cls, key: tuple) -> dict[str, Any] | None:
        path = cls._persistent_path(key)
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            log.warning("SDMX persistent cache stat failed for %s: %s", path, exc)
            return None
        if time.time() - stat.st_mtime > PERSISTENT_CACHE_TTL:
            log.debug("SDMX persistent cache expired for %s", path.name)
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as exc:
            log.warning("SDMX persistent cache read failed for %s: %s", path, exc)
            return None

    @classmethod
    def _persistent_write(cls, key: tuple, payload: dict[str, Any]) -> None:
        path = cls._persistent_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            tmp.replace(path)  # atomic on POSIX
            log.info("SDMX persistent cache STORED %s (%d bytes)", path.name, path.stat().st_size)
        except OSError as exc:
            log.warning("SDMX persistent cache write failed for %s: %s", path, exc)

    async def get_csv(self, path: str, *, params: dict[str, Any] | None = None) -> str:
        """GET an SDMX data endpoint requesting SDMX-CSV. Never cached (can be large)."""
        resp = await self._get(path, accept=ACCEPT_CSV, params=params)
        return resp.text

    # ────────────────────────────── cache mgmt ─────────────────────────────

    @classmethod
    def cache_stats(cls) -> dict[str, Any]:
        c = cls._cache
        l2_files = 0
        l2_dir = Path(PERSISTENT_CACHE_DIR) if PERSISTENT_CACHE_DIR else None
        if l2_dir is not None and l2_dir.is_dir():
            l2_files = sum(1 for _ in l2_dir.glob("*.json"))
        return {
            "l1": {
                "size": len(c),
                "maxsize": c.maxsize,
                "ttl_seconds": c.ttl,
                "hits_approx": getattr(c, "hits", None),
                "misses_approx": getattr(c, "misses", None),
            },
            "l2": {
                "dir": str(l2_dir) if l2_dir else None,
                "files": l2_files,
                "ttl_seconds": PERSISTENT_CACHE_TTL,
            },
        }

    @classmethod
    def cache_clear(cls) -> None:
        cls._cache.clear()
        l2_dir = Path(PERSISTENT_CACHE_DIR) if PERSISTENT_CACHE_DIR else None
        if l2_dir is not None and l2_dir.is_dir():
            for f in l2_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass


# ──────────────────────────── SDMX path helpers ───────────────────────────
#
# Identifier grammar used by ISTAT SDMX:
#   dataflowRef:     {agency}/{id}/{version}   eg. IT1/101_12/1.0
#   structureRef:    {agency}/{id}/{version}
#   dataKey:         dim1.dim2.dim3.…          (dots between dimensions, empty = ALL)
#
# All identifiers are already URL-safe in practice but we escape defensively.


def df_ref(agency: str, flow_id: str, version: str = "latest") -> str:
    return f"{quote(agency, safe='')}/{quote(flow_id, safe='')}/{quote(version, safe='')}"


def data_path(dataflow_id: str, key: str | None = None) -> str:
    """Build /data/{dataflowId}/{key} — key defaults to 'all'."""
    k = key.strip() if key else "all"
    return f"data/{quote(dataflow_id, safe='/')}/{quote(k, safe='.+')}"
