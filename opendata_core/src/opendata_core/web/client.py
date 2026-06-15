"""Async web-search + fetch client for the marketing-territoriale source (Pezzo 10).

The default provider is a **self-hosted SearXNG** meta-search instance (free, no
third-party API key). The provider is abstracted via ``WEB_SEARCH_PROVIDER`` so a
hosted API (Tavily / Brave) can be slotted in later by adding a branch in
``WebClient.search`` — no change needed in web-mcp or the backend.

This module is intentionally framework-free (no FastMCP, no FastAPI): it is shared
by the ``web-mcp`` server and any direct consumer, per the opendata_core invariant.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx

DEFAULT_TIMEOUT = float(os.getenv("WEB_HTTP_TIMEOUT", "30"))
DEFAULT_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "searxng").lower()
DEFAULT_SEARXNG_BASE_URL = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
DEFAULT_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "8"))
USER_AGENT = os.getenv(
    "WEB_USER_AGENT",
    "web-mcp/0.1 (+https://github.com/agent-engineering-studio)",
)

# Maximum bytes to download from web_fetch before truncating (default 512 KB).
MAX_FETCH_BYTES = int(os.getenv("WEB_MAX_FETCH_BYTES", str(512 * 1024)))

# Hard cap so the agent never floods its context window regardless of the request.
MAX_RESULTS_HARD_CAP = 15

SUPPORTED_PROVIDERS = ("searxng",)


class WebSearchError(RuntimeError):
    """Raised on a transport error or an unusable response from the search backend."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_SEARXNG_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base + "/"


class WebClient:
    """Async client over a web-search provider (SearXNG by default) + a fetch helper."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        max_results: int | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._provider = (provider or DEFAULT_PROVIDER).lower()
        self._base_url = base_url or DEFAULT_SEARXNG_BASE_URL
        self._max_results = max_results or DEFAULT_MAX_RESULTS
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WebClient":
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        categories: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a web search and return a list of ``{title, url, snippet, date, engine}``.

        Results are deliberately slim so the LLM context stays small. ``query`` may
        carry operators the backend prefers (e.g. ``site:gov.it``).
        """
        if self._provider == "searxng":
            return await self._search_searxng(query, max_results=max_results, categories=categories)
        raise WebSearchError(
            f"Unsupported WEB_SEARCH_PROVIDER={self._provider!r}. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)} (Tavily/Brave hooks pending)."
        )

    async def _search_searxng(
        self,
        query: str,
        *,
        max_results: int | None,
        categories: str | None,
    ) -> list[dict[str, Any]]:
        if self._client is None:
            raise RuntimeError("WebClient must be used as async context manager")

        limit = min(int(max_results or self._max_results), MAX_RESULTS_HARD_CAP)
        url = urljoin(_normalize_base(self._base_url), "search")
        params: dict[str, Any] = {"q": query, "format": "json"}
        if categories:
            params["categories"] = categories
        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Transport error querying SearXNG at {url}: {exc}") from exc

        if resp.status_code >= 500:
            raise WebSearchError(f"SearXNG {resp.status_code}: {resp.text[:300]}")

        try:
            payload = resp.json()
        except ValueError as exc:
            # The most common cause is the `json` format not being enabled in
            # SearXNG's settings.yml (search.formats) — surface that explicitly.
            raise WebSearchError(
                f"Non-JSON response from SearXNG {url}. "
                f"Is `json` enabled under search.formats in settings.yml? Body: {resp.text[:200]}"
            ) from exc

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise WebSearchError(f"Unexpected SearXNG response shape from {url}: {payload!r}")

        slim: list[dict[str, Any]] = []
        for r in results[:limit]:
            if not isinstance(r, dict) or not r.get("url"):
                continue
            snippet = (r.get("content") or "").strip()
            slim.append(
                {
                    "title": (r.get("title") or "").strip() or r["url"],
                    "url": r["url"],
                    "snippet": snippet[:300],
                    "date": r.get("publishedDate") or r.get("date") or "",
                    "engine": r.get("engine") or "",
                }
            )
        return slim

    async def fetch(self, url: str, max_bytes: int = MAX_FETCH_BYTES) -> dict[str, Any]:
        """Fetch a URL and return its text content (truncated at *max_bytes*).

        Returns ``{url, content, truncated, size_bytes, content_type}``. Used to read
        the body of a promising search hit (e.g. another comune's press release).
        """
        if self._client is None:
            raise RuntimeError("WebClient must be used as async context manager")

        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise WebSearchError(f"Failed to fetch {url}: {exc}") from exc

        raw = resp.content
        truncated = len(raw) > max_bytes
        text = raw[:max_bytes].decode("utf-8", errors="replace")
        return {
            "url": str(resp.url),  # after redirects
            "content": text,
            "truncated": truncated,
            "size_bytes": len(raw),
            "content_type": resp.headers.get("content-type", ""),
        }
