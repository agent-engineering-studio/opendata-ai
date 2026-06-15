"""Async HTTP client per IdroGEO (ISPRA) — indicatori di rischio comunali.

Vedi ``mapping.py`` per gli esiti della discovery (endpoint, nomi chiave,
divergenza sul consumo di suolo). Stesso impianto degli altri client del
repo: httpx async, retry/backoff, cache TTL condivisa, ``source_url``
risolvibile in ogni risultato.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from cachetools import TTLCache

from .mapping import (
    FRANE_AREA_KEYS,
    FRANE_CLASSI,
    FRANE_POP_KEYS,
    IDRAULICA_AREA_KEYS,
    IDRAULICA_CLASSI,
    IDRAULICA_POP_KEYS,
    LICENZA,
    comune_uid,
)
from .models import HazardSlice, RiskIndicators

DEFAULT_TIMEOUT = float(os.getenv("ISPRA_HTTP_TIMEOUT", "30"))
DEFAULT_BASE_URL = os.getenv(
    "ISPRA_IDROGEO_BASE_URL", "https://idrogeo.isprambiente.it/api"
)
USER_AGENT = os.getenv(
    "ISPRA_USER_AGENT",
    "ispra-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
CACHE_TTL = int(os.getenv("ISPRA_CACHE_TTL_SECONDS", "86400"))  # dato stabile
CACHE_MAXSIZE = int(os.getenv("ISPRA_CACHE_MAXSIZE", "512"))
MAX_RETRIES = 3

log = logging.getLogger("opendata-core.ispra")


class IspraError(RuntimeError):
    """Endpoint IdroGEO in errore o payload inatteso."""


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    return base


class IspraClient:
    """Thin async wrapper sull'API IdroGEO.

    Usage:
        async with IspraClient() as c:
            ind = await c.risk_indicators("072006")
    """

    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = _normalize_base(base_url)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "IspraClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_json(self, path: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("IspraClient must be used as an async context manager")
        key = (self._base, path)
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        url = f"{self._base}/{path.lstrip('/')}"
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.get("/" + path.lstrip("/"))
            except httpx.HTTPError as exc:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2.0**attempt)
                    continue
                raise IspraError(f"Transport error on GET {url}: {exc}") from exc
            if resp.status_code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2.0 ** (attempt + 1))
                continue
            if resp.status_code == 404:
                raise IspraError(
                    f"Not found: {url} — verifica il codice ISTAT del comune."
                )
            if resp.status_code >= 400:
                raise IspraError(f"HTTP {resp.status_code} on GET {url}: {resp.text[:200]}")
            try:
                payload = resp.json()
            except ValueError as exc:
                raise IspraError(f"Non-JSON response from {url}: {resp.text[:200]}") from exc
            if not isinstance(payload, dict):
                raise IspraError(f"Payload inatteso da {url}: {str(payload)[:200]}")
            self._cache[key] = payload
            return payload
        raise IspraError(f"IdroGEO non disponibile dopo {MAX_RETRIES} tentativi su {url}")

    def source_url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    # ───────────────────────── indicatori di rischio ─────────────────────────

    @staticmethod
    def _slice(
        raw: dict[str, Any], classe: str, area_keys: tuple[str, str], pop_keys: tuple[str, str] | None
    ) -> HazardSlice:
        def f(k: str) -> float | None:
            v = raw.get(k)
            return float(v) if isinstance(v, (int, float)) else None

        pop = pop_pct = None
        if pop_keys:
            p = raw.get(pop_keys[0])
            pop = int(p) if isinstance(p, (int, float)) else None
            pop_pct = f(pop_keys[1])
        return HazardSlice(
            classe=classe,
            area_kmq=f(area_keys[0]),
            area_pct=f(area_keys[1]),
            popolazione=pop,
            popolazione_pct=pop_pct,
        )

    async def risk_indicators(self, cod_comune: str | int) -> RiskIndicators:
        """Indicatori di pericolosità frane + idraulica per il comune (1 chiamata)."""
        uid = comune_uid(cod_comune)
        path = f"pir/comuni/{uid}"
        raw = await self._get_json(path)
        frane = [
            self._slice(raw, c, FRANE_AREA_KEYS[c], FRANE_POP_KEYS[c]) for c in FRANE_CLASSI
        ]
        idraulica = [
            self._slice(raw, c, IDRAULICA_AREA_KEYS[c], IDRAULICA_POP_KEYS[c])
            for c in IDRAULICA_CLASSI
        ]
        pop_keys_p3p4 = ("popfr_p3p4", "popfrp3p4p")
        return RiskIndicators(
            cod_comune=str(cod_comune).strip(),
            nome=raw.get("nome") or str(uid),
            area_kmq=raw.get("ar_kmq"),
            popolazione_residente=raw.get("pop_res021") or raw.get("pop_res011"),
            frane=frane,
            frane_p3p4=self._slice(raw, "p3p4", FRANE_AREA_KEYS["p3p4"], pop_keys_p3p4),
            idraulica=idraulica,
            source_url=self.source_url(path),
            licenza=LICENZA,
        )

    @classmethod
    def cache_clear(cls) -> None:
        cls._cache.clear()
