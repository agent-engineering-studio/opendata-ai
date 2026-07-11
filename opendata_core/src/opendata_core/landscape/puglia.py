"""Adattatore Puglia — vincoli paesaggistici dal PPTR via ArcGIS identify (#128 Fase 2b).

Interroga PUNTUALMENTE il MapServer del PPTR (SIT Puglia) e restituisce le tutele
paesaggistiche VINCOLANTI (beni paesaggistici art. 136/142/143) che intersecano il
punto. Distingue i layer di tutela dai layer descrittivi (Figure/Ambiti/Città
consolidata) via allowlist di parole chiave — robusto rispetto alle versioni DGR
(il MapServer espone tutte le versioni storiche con gli stessi nomi-layer).

Motore puro come gli altri connettori: httpx async + cache TTL, fail-safe
(timeout/errore/forma inattesa → None). Endpoint e schema verificati live
(2026-07-11): punto costiero → {Territori costieri, Immobili di notevole interesse
pubblico, ...}; centro urbano → nessuna tutela (Città consolidata, esclusa).
"""

from __future__ import annotations

import logging
import os

import httpx
from cachetools import TTLCache

from .models import LandscapeConstraint

REGIONE = "Puglia"
LICENZA = "Regione Puglia — PPTR (SIT Puglia)"
PPTR_IDENTIFY_URL = os.getenv(
    "PPTR_PUGLIA_IDENTIFY_URL",
    "https://webapps.sit.puglia.it/arcgis/rest/services/Operationals/PPTR_APPROVATO/MapServer/identify",
)
USER_AGENT = os.getenv(
    "PPTR_USER_AGENT",
    "opendata-ai/1.0 (+https://github.com/agent-engineering-studio)",
)
DEFAULT_TIMEOUT = float(os.getenv("PPTR_HTTP_TIMEOUT", "30"))
CACHE_TTL = int(os.getenv("PPTR_CACHE_TTL_SECONDS", "86400"))
CACHE_MAXSIZE = int(os.getenv("PPTR_CACHE_MAXSIZE", "512"))

# Semi-lato del mapExtent attorno al punto (in gradi, sr=4326).
_MAP_DELTA = 0.02

# Parole chiave (minuscole) dei layer di TUTELA vincolanti del PPTR: beni
# paesaggistici (art. 142 aree tutelate per legge, art. 136 notevole interesse
# pubblico) + ulteriori contesti + componenti geomorfologiche/culturali tutelate.
# Esclude per costruzione i layer descrittivi (figure, ambiti, città consolidata,
# stato pianificazione, "pptr aggiornato...", componenti "6.x", siti di rilevanza
# naturalistica), che NON marcano un vincolo.
_TUTELE_KEYWORDS = (
    "beni paesaggistici", "notevole interesse pubblico", "ulteriori contesti",
    "bosch", "fiumi e torrenti", "acque pubbliche", "reticolo idrografico",
    "territori costieri", "cordoni dunari", "contermini ai laghi",
    "zone umide", "ramsar", "parchi e riserve", "aree protette", "usi civici",
    "interesse archeologico", "tratturi", "grott", "dolin", "inghiottitoi",
    "lame e gravine", "geositi", "sorgenti", "versanti", "vincolo idrogeologico",
    "storico culturali", "stratificazione insediativa", "paesaggi rurali",
    "aree di rispetto",
)

log = logging.getLogger("opendata-core.landscape.puglia")


def _is_tutela(layer_name: str | None) -> bool:
    if not layer_name:
        return False
    low = layer_name.lower()
    return any(k in low for k in _TUTELE_KEYWORDS)


def _parse_identify(payload: object, source_url: str) -> LandscapeConstraint | None:
    """Risposta ArcGIS identify → LandscapeConstraint, o None se in errore/inattesa."""
    if not isinstance(payload, dict) or "results" not in payload:
        return None  # 'error' o forma inattesa: fonte non affidabile in questo punto
    results = payload.get("results") or []
    tutele = sorted(
        {(r.get("layerName") or "").strip() for r in results if _is_tutela(r.get("layerName"))}
        - {""}
    )
    return LandscapeConstraint(
        vincolato=bool(tutele), tutele=tutele, regione=REGIONE,
        source_url=source_url, licenza=LICENZA,
    )


class PugliaPPTRClient:
    """Interrogazione puntuale del PPTR Puglia (ArcGIS identify).

    Usage:
        async with PugliaPPTRClient() as c:
            v = await c.constraint_at(40.995, 17.221)  # None se non interrogabile
    """

    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = base_url or PPTR_IDENTIFY_URL
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "PugliaPPTRClient":
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
        d = _MAP_DELTA
        return {
            "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": "4326",
            "layers": "all", "tolerance": "3",
            "mapExtent": f"{lon - d},{lat - d},{lon + d},{lat + d}",
            "imageDisplay": "600,400,96", "returnGeometry": "false", "f": "json",
        }

    async def constraint_at(self, lat: float, lon: float) -> LandscapeConstraint | None:
        """Tutele paesaggistiche nel punto. Fail-safe: None su errore/timeout."""
        if self._client is None:
            raise RuntimeError("PugliaPPTRClient must be used as an async context manager")
        key = (self._base, round(lat, 5), round(lon, 5))
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        try:
            resp = await self._client.get(self._base, params=self._params(lat, lon))
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("PPTR Puglia non interrogabile a (%s,%s): %s", lat, lon, exc)
            return None
        info = _parse_identify(payload, str(resp.request.url))
        if info is not None:
            self._cache[key] = info
        return info
