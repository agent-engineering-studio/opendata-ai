"""Thin async HTTP client to the opendata-ai backend REST API.

The product MCP server is a **proxy** (issue #131, Option A): it reuses the
backend's orchestration, LLM provider resolution, Redis cache, fail-safe and
API-key auth/billing instead of duplicating any logic. This client forwards the
configured API key as a Bearer token and turns any transport/HTTP failure into
a clean ``BackendError`` (the tools surface it as an MCP error, never a crash).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("opendata-mcp.client")

DEFAULT_BASE_URL = os.getenv("OPENDATA_API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("OPENDATA_API_KEY") or None
#: Report/assessment call LLMs and multi-source fan-outs — allow a long timeout.
DEFAULT_TIMEOUT = float(os.getenv("OPENDATA_API_TIMEOUT", "300"))


class BackendError(RuntimeError):
    """Raised when the backend is unreachable or returns an error response."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "http://" + base
    return base


class BackendClient:
    """Async wrapper over the backend REST API. Use as an async context manager."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base = _normalize_base(base_url)
        self._api_key = api_key if api_key is not None else API_KEY
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BackendClient":
        headers = {"User-Agent": "opendata-mcp-server/0.1", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base, timeout=self._timeout, headers=headers,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("BackendClient must be used as an async context manager")
        url = self._base + path
        try:
            resp = await self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise BackendError(
                f"Timeout dopo {self._timeout:.0f}s chiamando {path} — il backend è lento "
                "o irraggiungibile."
            ) from exc
        except httpx.HTTPError as exc:
            raise BackendError(f"Errore di rete su {url}: {exc}") from exc

        if resp.status_code in (401, 403):
            raise BackendError(
                f"HTTP {resp.status_code} su {path}: autenticazione rifiutata — verifica "
                "OPENDATA_API_KEY (o abilita il dev-bypass sul backend)."
            )
        if resp.status_code >= 400:
            snippet = resp.text[:300].replace("\n", " ")
            raise BackendError(f"HTTP {resp.status_code} su {path}: {snippet}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise BackendError(f"Risposta non-JSON da {path}: {resp.text[:200]}") from exc
        return data

    # ─────────────────────────────── endpoints ─────────────────────────────

    async def search_datasets(
        self, query: str, *, base_url: str | None = None, prefer_geo: bool | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query}
        if base_url:
            body["base_url"] = base_url
        if prefer_geo is not None:
            body["prefer_geo"] = prefer_geo
        return await self._post("/datasets/search", body)

    async def territory_report(
        self, *, istat_code: str, temi: list[str] | None = None,
        anno_da: int | None = None, anno_a: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"istat_code": istat_code}
        if temi:
            body["temi"] = temi
        if anno_da is not None:
            body["anno_da"] = anno_da
        if anno_a is not None:
            body["anno_a"] = anno_a
        return await self._post("/territory/report", body)

    async def maturity_assess(
        self, *, entity: str, base_url: str | None = None, istat_code: str | None = None,
        comune_nome: str | None = None, force: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"entity": entity, "force": force}
        if base_url:
            body["base_url"] = base_url
        if istat_code:
            body["istat_code"] = istat_code
        if comune_nome:
            body["comune_nome"] = comune_nome
        return await self._post("/maturity/assess", body)

    async def quality_profile(
        self, *, content: str | None = None, url: str | None = None, fmt: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if content is not None:
            body["content"] = content
        if url:
            body["url"] = url
        if fmt:
            body["format"] = fmt
        return await self._post("/quality/profile", body)

    async def classify(
        self, *, source: str, dataset_id: str, dataset_name: str,
        taxonomy: list[str], dataset_description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "source": source, "dataset_id": dataset_id, "dataset_name": dataset_name,
            "taxonomy": taxonomy,
        }
        if dataset_description:
            body["dataset_description"] = dataset_description
        return await self._post("/datasets/classify", body)
