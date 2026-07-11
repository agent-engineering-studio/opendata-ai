"""Copertura del suolo PUNTUALE via WMS GetFeatureInfo — Corine Land Cover ISPRA.

Connettore Fase 2c (#128): interroga il layer CLC nazionale del GeoServer SDI
ISPRA in un punto (lat/lon del centroide del poligono candidato) e ne ricava la
macroclasse di copertura → flag ``impermeabilizzato``. Risolve il nodo
"edificato/impermeabilizzato" §4.3 lasciato "da verificare" in Fase 1.

Motore puro come gli altri connettori: ``httpx`` async + cache TTL, licenza
dichiarata, **fail-safe** (timeout/errore/feature assente → ``None``, così la sua
assenza degrada la confidenza del record senza bloccare il report). Endpoint e
schema verificati live (2026-07-11): vedi ``mapping.py``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from cachetools import TTLCache

from .mapping import (
    LC_CODE_FIELD,
    LC_LAYER,
    LC_LICENZA,
    LC_MACROCLASSI,
    LC_WMS_BASE_URL,
)
from .models import LandCoverInfo

DEFAULT_TIMEOUT = float(os.getenv("ISPRA_HTTP_TIMEOUT", "30"))
LC_BASE_URL = os.getenv("ISPRA_LANDCOVER_WMS_URL", LC_WMS_BASE_URL)
LC_LAYER_NAME = os.getenv("ISPRA_LANDCOVER_LAYER", LC_LAYER)
USER_AGENT = os.getenv(
    "ISPRA_USER_AGENT",
    "ispra-mcp-server/0.1 (+https://github.com/agent-engineering-studio)",
)
CACHE_TTL = int(os.getenv("ISPRA_CACHE_TTL_SECONDS", "86400"))  # dato stabile
CACHE_MAXSIZE = int(os.getenv("ISPRA_CACHE_MAXSIZE", "512"))

# Semi-lato del bbox attorno al punto (~150 m): GetFeatureInfo campiona il pixel
# centrale (i=j=50 su 101×101), il bbox serve solo a definire la scala del pixel.
_BBOX_DELTA = 0.0015

log = logging.getLogger("opendata-core.ispra.landcover")


def _parse_clc(payload: dict[str, Any], source_url: str) -> LandCoverInfo | None:
    """Feature JSON di GetFeatureInfo → LandCoverInfo, o None se non interpretabile."""
    feats = payload.get("features") or []
    if not feats:
        return None
    code_raw = (feats[0].get("properties") or {}).get(LC_CODE_FIELD)
    if code_raw is None:
        return None
    code = str(code_raw).strip()
    if not code[:1].isdigit():
        return None
    macro = int(code[0])
    return LandCoverInfo(
        clc_code=code,
        macroclasse=macro,
        descrizione=LC_MACROCLASSI.get(macro, "Classe di copertura non riconosciuta"),
        impermeabilizzato=(macro == 1),  # macroclasse 1 = superfici artificiali
        source_url=source_url,
        licenza=LC_LICENZA,
    )


class LandCoverClient:
    """Interrogazione puntuale del WMS Corine Land Cover ISPRA.

    Usage:
        async with LandCoverClient() as c:
            lc = await c.land_cover_at(41.9028, 12.4964)  # None se non disponibile
    """

    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(
        self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None, layer: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._base = base_url or LC_BASE_URL
        self._layer = layer or LC_LAYER_NAME
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "LandCoverClient":
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

    def _params(self, lat: float, lon: float) -> dict[str, str]:
        # WMS 1.3.0 + CRS geografico (EPSG:4258) → ordine assi lat,lon nel bbox.
        bbox = f"{lat - _BBOX_DELTA},{lon - _BBOX_DELTA},{lat + _BBOX_DELTA},{lon + _BBOX_DELTA}"
        return {
            "service": "WMS", "version": "1.3.0", "request": "GetFeatureInfo",
            "layers": self._layer, "query_layers": self._layer, "crs": "EPSG:4258",
            "bbox": bbox, "width": "101", "height": "101", "i": "50", "j": "50",
            "info_format": "application/json",
        }

    async def land_cover_at(self, lat: float, lon: float) -> LandCoverInfo | None:
        """Copertura del suolo nel punto (lat/lon). Fail-safe: None su errore/timeout."""
        if self._client is None:
            raise RuntimeError("LandCoverClient must be used as an async context manager")
        key = (self._base, self._layer, round(lat, 5), round(lon, 5))
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        try:
            resp = await self._client.get(self._base, params=self._params(lat, lon))
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("land cover non disponibile a (%s,%s): %s", lat, lon, exc)
            return None  # confidenza degradata a monte, mai bloccante
        info = _parse_clc(payload, str(resp.request.url))
        if info is not None:
            self._cache[key] = info
        return info
