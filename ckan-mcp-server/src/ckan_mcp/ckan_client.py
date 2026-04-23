"""Async HTTP client for the CKAN Action API.

Works with any CKAN portal exposing /api/3/action/*. Base URL is resolved per-call
so a single server instance can serve multiple portals.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx

DEFAULT_TIMEOUT = float(os.getenv("CKAN_HTTP_TIMEOUT", "30"))
DEFAULT_BASE_URL = os.getenv("CKAN_DEFAULT_BASE_URL", "https://www.dati.gov.it/opendata")
USER_AGENT = os.getenv("CKAN_USER_AGENT", "ckan-mcp-server/0.1 (+https://github.com/agent-engineering-studio)")


class CkanError(RuntimeError):
    """Raised when the CKAN API returns success=false or a transport error occurs."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base + "/"


class CkanClient:
    """Thin async wrapper around CKAN Action API endpoints."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CkanClient":
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

    async def action(
        self,
        action: str,
        *,
        base_url: str | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Call a CKAN action endpoint. Uses GET when only params, POST when json_body."""
        if self._client is None:
            raise RuntimeError("CkanClient must be used as async context manager")

        url = urljoin(_normalize_base(base_url), f"api/3/action/{action}")
        try:
            if json_body is not None:
                resp = await self._client.post(url, json=json_body, params=params)
            else:
                resp = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise CkanError(f"Transport error calling {action} on {url}: {exc}") from exc

        if resp.status_code >= 500:
            raise CkanError(f"CKAN {resp.status_code} on {action}: {resp.text[:300]}")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise CkanError(f"Non-JSON response from {url}: {resp.text[:300]}") from exc

        if not isinstance(payload, dict) or "success" not in payload:
            raise CkanError(f"Unexpected CKAN response shape from {url}: {payload!r}")

        if not payload.get("success"):
            err = payload.get("error") or {}
            raise CkanError(f"CKAN action '{action}' failed: {err}")

        return payload.get("result")
