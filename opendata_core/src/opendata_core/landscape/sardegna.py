"""Adattatore Sardegna — vincoli paesaggistici dal PPR via WFS (SITR) (#166).

Interroga PUNTUALMENTE il GeoServer del Piano Paesaggistico Regionale (SITR,
Regione Autonoma della Sardegna) e restituisce le tutele paesaggistiche
VINCOLANTI (beni paesaggistici D.Lgs 42/2004 artt. 136/142/143) i cui poligoni
intersecano il punto.

A differenza della Puglia (ArcGIS `identify` su un unico MapServer), la Sardegna
espone i beni paesaggistici come **layer WFS distinti** (uno per tipo di tutela):
l'adattatore interroga in parallelo un'**allowlist** di layer poligonali con una
`GetFeature` BBOX minima attorno al punto (GeoJSON) e raccoglie le tutele colpite.

Motore puro come gli altri connettori: httpx async + cache TTL, **fail-safe per
layer** (timeout/errore su un layer → quel layer è saltato, non blocca). Semantica
onesta: se TUTTI i layer falliscono e nessuna tutela è emersa → `None` (fonte non
interrogabile, confidenza degradata), distinto da `vincolato=False` (interrogato,
nessuna tutela). Endpoint e query verificati live (2026-07): punto costiero
(Cagliari-Poetto) → art. 136 "CAGLIARI - MOLENTARGIUS" (DM 24/03/1977) + fascia
costiera; punto interno (Nuoro) → nessuna tutela.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from cachetools import TTLCache

from .models import LandscapeConstraint

REGIONE = "Sardegna"
LICENZA = "Regione Autonoma della Sardegna — PPR (SITR, GeoServer WFS)"
WFS_URL = os.getenv(
    "PPR_SARDEGNA_WFS_URL",
    "https://webgis.regione.sardegna.it/geoserver/ows",
)
USER_AGENT = os.getenv(
    "PPR_USER_AGENT",
    "opendata-ai/1.0 (+https://github.com/agent-engineering-studio)",
)
# Il GeoServer SITR ha latenza variabile (alcuni layer, es. fascia costiera con
# la geometria dell'intera isola, sono lenti). Timeout come l'adattatore Puglia;
# un layer lento oltre soglia è saltato (fail-safe), non blocca il report.
DEFAULT_TIMEOUT = float(os.getenv("PPR_SARDEGNA_HTTP_TIMEOUT", "30"))
CACHE_TTL = int(os.getenv("PPR_CACHE_TTL_SECONDS", "86400"))
CACHE_MAXSIZE = int(os.getenv("PPR_CACHE_MAXSIZE", "512"))

# Semi-lato della bbox attorno al punto (gradi, EPSG:4326).
_BBOX_DELTA = 0.0004

#: Allowlist dei layer WFS poligonali di TUTELA vincolante → etichetta normalizzata.
#: Solo beni paesaggistici (artt. 136/142/143 D.Lgs 42/2004), non i layer
#: descrittivi (ambiti di paesaggio, toponimi, uso del suolo). Verificati nelle
#: capabilities del GeoServer SITR.
_TUTELE_LAYERS: dict[str, str] = {
    "aree_vincolate_ex_art136": "Immobili e aree di notevole interesse pubblico (art. 136)",
    "benipaesaggisticiexart143_plg": "Beni paesaggistici individuati dal PPR (art. 143)",
    "fasciacostiera": "Fascia costiera (art. 142 c.1 lett. a)",
    "art142_fascia_150m_fiumi_indic": "Fascia fluviale 150 m (art. 142 c.1 lett. c)",
}

log = logging.getLogger("opendata-core.landscape.sardegna")


class SardegnaPPRClient:
    """Interrogazione puntuale del PPR Sardegna (WFS GetFeature BBOX per layer).

    Usage:
        async with SardegnaPPRClient() as c:
            v = await c.constraint_at(39.205, 9.166)  # None se non interrogabile
    """

    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = base_url or WFS_URL
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SardegnaPPRClient":
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

    def _params(self, layer: str, lat: float, lon: float) -> dict[str, str]:
        d = _BBOX_DELTA
        # WFS 2.0 con urn EPSG::4326 → ordine assi lat,lon (miny,minx,maxy,maxx).
        bbox = f"{lat - d},{lon - d},{lat + d},{lon + d},urn:ogc:def:crs:EPSG::4326"
        return {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": f"dbu:{layer}", "count": "1",
            "outputFormat": "application/json",
            "srsName": "urn:ogc:def:crs:EPSG::4326", "bbox": bbox,
        }

    async def _layer_hit(self, layer: str, lat: float, lon: float) -> tuple[bool | None, str]:
        """(hit, label): hit True/False se interrogato, None se il layer ha fallito."""
        assert self._client is not None
        label = _TUTELE_LAYERS[layer]
        try:
            resp = await self._client.get(self._base, params=self._params(layer, lat, lon))
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("PPR Sardegna layer %s non interrogabile a (%s,%s): %s", layer, lat, lon, exc)
            return None, label
        feats = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(feats, list):
            return None, label
        return (len(feats) > 0), label

    async def constraint_at(self, lat: float, lon: float) -> LandscapeConstraint | None:
        """Tutele paesaggistiche nel punto. Fail-safe: None se non interrogabile."""
        if self._client is None:
            raise RuntimeError("SardegnaPPRClient must be used as an async context manager")
        key = (self._base, round(lat, 5), round(lon, 5))
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]

        results = await asyncio.gather(
            *(self._layer_hit(layer, lat, lon) for layer in _TUTELE_LAYERS),
            return_exceptions=True,
        )
        tutele: set[str] = set()
        all_ok = True
        for res in results:
            if isinstance(res, BaseException):
                all_ok = False
                continue
            hit, label = res
            if hit is None:
                all_ok = False
                continue
            if hit:
                tutele.add(label)

        # Positivo definitivo: una tutela trovata è una tutela trovata.
        if tutele:
            info = LandscapeConstraint(
                vincolato=True, tutele=sorted(tutele), regione=REGIONE,
                source_url=self._base, licenza=LICENZA,
            )
        elif all_ok:
            # Tutti i layer hanno risposto, nessuna tutela → negativo definitivo.
            info = LandscapeConstraint(
                vincolato=False, tutele=[], regione=REGIONE,
                source_url=self._base, licenza=LICENZA,
            )
        else:
            # Nessuna tutela ma almeno un layer ha fallito → non affidabile: degrada
            # a None (confidenza ridotta) invece di un falso negativo.
            return None

        self._cache[key] = info
        return info
