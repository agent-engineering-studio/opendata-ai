"""Async HTTP client for Socrata's open-data APIs (Discovery + Views + SODA).

Works with any Socrata-hosted portal (many US city/state/federal open-data
portals, plus a handful of Italian/European ones, run on Socrata). Base URL
is resolved per-call so a single server instance can serve multiple portals
— same design as `CkanClient` / `OpenDataSoftClient`.

Three APIs are involved, all served on the portal's own domain:
  - Discovery/Catalog API (`/api/catalog/v1`) — dataset search, scoped by
    default to the target portal's own domain via `domains=`.
  - Views/Metadata API (`/api/views/{id}.json`) — full dataset metadata +
    column schema.
  - SODA resource API (`/resource/{id}.json`) — tabular rows, filtered with
    SoQL (`$where`, `$select`, `$order`, `$q`).

Docs: https://dev.socrata.com/docs/endpoints.html
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

DEFAULT_TIMEOUT = float(os.getenv("SOCRATA_HTTP_TIMEOUT", "30"))
DEFAULT_BASE_URL = os.getenv("SOCRATA_DEFAULT_BASE_URL", "https://opendata.socrata.com")
USER_AGENT = os.getenv(
    "SOCRATA_USER_AGENT",
    "socrata-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)

# limite massimo di righe/risultati per pagina che il client richiede all'API.
_MAX_LIMIT = 100


class SocrataError(RuntimeError):
    """Raised when the Socrata API returns an error or a transport error occurs."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base + "/"


def _host(base_url: str | None) -> str:
    """Hostname del portale target, usato per delimitare la ricerca catalogo."""
    return urlparse(_normalize_base(base_url)).netloc


class SocrataClient:
    """Thin async wrapper around the Socrata Discovery, Views and SODA APIs."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SocrataClient":
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

    async def _get(self, url: str, *, params: dict[str, Any]) -> Any:
        if self._client is None:
            raise RuntimeError("SocrataClient must be used as async context manager")
        clean = {k: v for k, v in params.items() if v is not None}
        try:
            resp = await self._client.get(url, params=clean)
        except httpx.HTTPError as exc:
            raise SocrataError(f"Transport error on {url}: {exc}") from exc

        if resp.status_code >= 400:
            # Errore SODA/catalog tipico: {"error": true, "message": "..."}.
            detail = resp.text[:300]
            try:
                body = resp.json()
                if isinstance(body, dict):
                    detail = body.get("message") or body.get("error") or detail
            except ValueError:
                pass
            raise SocrataError(f"Socrata {resp.status_code} on {url}: {detail}")

        try:
            return resp.json()
        except ValueError as exc:
            raise SocrataError(f"Non-JSON response from {url}: {resp.text[:300]}") from exc

    async def search_datasets(
        self,
        *,
        base_url: str | None = None,
        q: str | None = None,
        domains: str | None = None,
        limit: int = 10,
        offset: int = 0,
        order: str | None = None,
    ) -> dict[str, Any]:
        """Search the Discovery/Catalog API (`/api/catalog/v1`).

        Scoped by default to the target portal's own domain (`domains`); pass
        `domains` explicitly to search across other/additional Socrata
        domains too. Returns `{total_count, results:[…]}`.
        """
        url = urljoin(_normalize_base(base_url), "api/catalog/v1")
        params = {
            "q": q,
            "domains": domains or _host(base_url),
            "limit": max(0, min(int(limit), _MAX_LIMIT)),
            "offset": max(0, int(offset)),
            "order": order,
        }
        body = await self._get(url, params=params)
        return {
            "total_count": body.get("resultSetSize", 0),
            "results": body.get("results", []),
        }

    async def dataset(self, dataset_id: str, *, base_url: str | None = None) -> dict[str, Any]:
        """Full metadata for one dataset (name, description, columns) via the Views API."""
        url = urljoin(_normalize_base(base_url), f"api/views/{dataset_id}.json")
        return await self._get(url, params={})

    async def records(
        self,
        dataset_id: str,
        *,
        base_url: str | None = None,
        where: str | None = None,
        select: str | None = None,
        order_by: str | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query rows of a dataset (SODA resource API, `/resource/{id}.json`) via SoQL.

        `where`/`select`/`order_by`/`q` map to the `$where`/`$select`/`$order`/`$q`
        SoQL parameters. Returns the list of row records (already capped server-side).
        """
        url = urljoin(_normalize_base(base_url), f"resource/{dataset_id}.json")
        params = {
            "$where": where,
            "$select": select,
            "$order": order_by,
            "$q": q,
            "$limit": max(0, min(int(limit), _MAX_LIMIT)),
            "$offset": max(0, int(offset)),
        }
        result = await self._get(url, params=params)
        return result if isinstance(result, list) else []
