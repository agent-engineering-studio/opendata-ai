"""Async HTTP client for the OpenDataSoft Explore API v2.1.

Works with any OpenDataSoft portal exposing /api/explore/v2.1/* (many Italian and
European regional/city portals run on ODS). Base URL is resolved per-call so a
single server instance can serve multiple portals — same design as `CkanClient`.

Docs: https://help.opendatasoft.com/apis/ods-explore-v2/
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx

DEFAULT_TIMEOUT = float(os.getenv("ODS_HTTP_TIMEOUT", "30"))
DEFAULT_BASE_URL = os.getenv("ODS_DEFAULT_BASE_URL", "https://public.opendatasoft.com")
USER_AGENT = os.getenv(
    "ODS_USER_AGENT",
    "ods-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)

_EXPLORE = "api/explore/v2.1"
# limit massimo accettato dall'API ODS per pagina.
_MAX_LIMIT = 100


class OpenDataSoftError(RuntimeError):
    """Raised when the ODS API returns an error or a transport error occurs."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base + "/"


class OpenDataSoftClient:
    """Thin async wrapper around the OpenDataSoft Explore API v2.1."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OpenDataSoftClient":
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

    async def _get(self, path: str, *, base_url: str | None, params: dict[str, Any]) -> Any:
        if self._client is None:
            raise RuntimeError("OpenDataSoftClient must be used as async context manager")
        url = urljoin(_normalize_base(base_url), path)
        clean = {k: v for k, v in params.items() if v is not None}
        try:
            resp = await self._client.get(url, params=clean)
        except httpx.HTTPError as exc:
            raise OpenDataSoftError(f"Transport error on {url}: {exc}") from exc

        if resp.status_code >= 400:
            # ODS error body: {"message": "...", "error_code": "..."}.
            detail = resp.text[:300]
            try:
                body = resp.json()
                detail = body.get("message") or body.get("error_code") or detail
            except ValueError:
                pass
            raise OpenDataSoftError(f"ODS {resp.status_code} on {url}: {detail}")

        try:
            return resp.json()
        except ValueError as exc:
            raise OpenDataSoftError(f"Non-JSON response from {url}: {resp.text[:300]}") from exc

    async def search_datasets(
        self,
        *,
        base_url: str | None = None,
        where: str | None = None,
        limit: int = 10,
        offset: int = 0,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        """Search the catalog of datasets. `where` is an ODSQL clause (a bare string
        does full-text search). Returns {total_count, results:[…]}.
        """
        params = {
            "where": where,
            "limit": max(0, min(int(limit), _MAX_LIMIT)),
            "offset": max(0, int(offset)),
            "order_by": order_by,
        }
        return await self._get(f"{_EXPLORE}/catalog/datasets", base_url=base_url, params=params)

    async def dataset(self, dataset_id: str, *, base_url: str | None = None) -> dict[str, Any]:
        """Full metadata for a single dataset (fields, metas, attachments)."""
        return await self._get(
            f"{_EXPLORE}/catalog/datasets/{dataset_id}", base_url=base_url, params={}
        )

    async def records(
        self,
        dataset_id: str,
        *,
        base_url: str | None = None,
        where: str | None = None,
        select: str | None = None,
        order_by: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query rows of a dataset. `where`/`select`/`order_by` are ODSQL clauses.
        Returns {total_count, results:[…]}.
        """
        params = {
            "where": where,
            "select": select,
            "order_by": order_by,
            "limit": max(0, min(int(limit), _MAX_LIMIT)),
            "offset": max(0, int(offset)),
        }
        return await self._get(
            f"{_EXPLORE}/catalog/datasets/{dataset_id}/records", base_url=base_url, params=params
        )
