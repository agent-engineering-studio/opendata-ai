"""Siti contaminati e bonifiche (SIN-SIR) via MOSAICO ISPRA — ArcGIS FeatureServer (#128 Fase 2a).

Interroga il FeatureServer pubblico di MOSAICO (ISPRA, ArcGIS Enterprise):
- layer SIN (poligoni): il punto ricade in un Sito di Interesse Nazionale? → segnale
  poligono-preciso;
- layer PROCEDIMENTO (punti, attributo ``comune_istat``): procedimenti di bonifica
  regionali (SIR) nel comune → segnale a scala comunale.

Risponde a "perché un'area è dismessa" (causa **contaminazione**) e attiva la
classificazione **BROWNFIELD** (§4.4). Motore puro: httpx async + cache TTL,
fail-safe (errore/timeout → None). Endpoint e schema verificati live (2026-07-11):
Taranto → SIN presente (matrice SSAS) + 25 procedimenti (9 in stato CONT).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from cachetools import TTLCache

from .models import ContaminationInfo

REGIONE_LICENZA = "ISPRA MOSAICO — siti contaminati (CC BY-SA 3.0 IT)"
FEATURESERVER = os.getenv(
    "MOSAICO_FEATURESERVER_URL",
    "https://sinacloud.isprambiente.it/arcgisgeo/rest/services/SitiContaminati_UtenteGenerico/FeatureServer",
)
LAYER_SIN = int(os.getenv("MOSAICO_LAYER_SIN", "1"))
LAYER_PROCEDIMENTO = int(os.getenv("MOSAICO_LAYER_PROCEDIMENTO", "0"))
STATO_CONTAMINATO = "CONT"  # valore di stato_cont_corr per "contaminato"
USER_AGENT = os.getenv(
    "MOSAICO_USER_AGENT",
    "opendata-ai/1.0 (+https://github.com/agent-engineering-studio)",
)
DEFAULT_TIMEOUT = float(os.getenv("MOSAICO_HTTP_TIMEOUT", "30"))
CACHE_TTL = int(os.getenv("MOSAICO_CACHE_TTL_SECONDS", "86400"))
CACHE_MAXSIZE = int(os.getenv("MOSAICO_CACHE_MAXSIZE", "512"))

log = logging.getLogger("opendata-core.sin_sir")


class SinSirClient:
    """Interrogazione MOSAICO (siti contaminati SIN + procedimenti SIR).

    Usage:
        async with SinSirClient() as c:
            info = await c.contamination_at(40.49, 17.24, "073027")  # None se non interrogabile
    """

    _cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, base_url: str | None = None) -> None:
        self._timeout = timeout
        self._base = (base_url or FEATURESERVER).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SinSirClient":
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

    async def _query(self, layer: int, params: dict[str, str]) -> dict[str, Any]:
        assert self._client is not None
        resp = await self._client.get(f"{self._base}/{layer}/query", params={**params, "f": "json"})
        resp.raise_for_status()
        return resp.json()

    async def _sin_at(self, lat: float, lon: float) -> tuple[bool, str | None, list[str]]:
        """Il punto ricade in un SIN? → (dentro, denominazione, matrici)."""
        payload = await self._query(LAYER_SIN, {
            "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "den_sin,matrice",
            "returnGeometry": "false",
        })
        feats = payload.get("features") or []
        if not feats:
            return False, None, []
        attrs = feats[0].get("attributes") or {}
        den = attrs.get("den_sin")
        matrici = sorted({(f.get("attributes") or {}).get("matrice") for f in feats} - {None, ""})
        return True, (str(den) if den is not None else None), matrici

    async def _procedimenti_comune(self, cod_comune: str) -> tuple[int, int]:
        """Procedimenti di bonifica (SIR) nel comune → (totale, contaminati). Cache per comune."""
        key = ("proc", self._base, cod_comune)
        if key in self._cache:
            return self._cache[key]  # type: ignore[return-value]
        tot = await self._query(LAYER_PROCEDIMENTO, {
            "where": f"comune_istat='{cod_comune}'", "returnCountOnly": "true",
        })
        cont = await self._query(LAYER_PROCEDIMENTO, {
            "where": f"comune_istat='{cod_comune}' AND stato_cont_corr='{STATO_CONTAMINATO}'",
            "returnCountOnly": "true",
        })
        out = (int(tot.get("count", 0)), int(cont.get("count", 0)))
        self._cache[key] = out
        return out

    async def contamination_at(
        self, lat: float, lon: float, cod_comune: str,
    ) -> ContaminationInfo | None:
        """Stato contaminazione del poligono/comune. Fail-safe: None se non interrogabile.

        Best-effort per query: se una delle due (SIN puntuale / procedimenti comunali)
        fallisce si usa l'altra; se falliscono entrambe → None."""
        if self._client is None:
            raise RuntimeError("SinSirClient must be used as an async context manager")
        sin, sin_den, matrici = False, None, []  # type: ignore[var-annotated]
        sin_ok = proc_ok = False
        try:
            sin, sin_den, matrici = await self._sin_at(lat, lon)
            sin_ok = True
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.info("MOSAICO SIN non interrogabile a (%s,%s): %s", lat, lon, exc)
        n_proc = n_cont = 0
        try:
            n_proc, n_cont = await self._procedimenti_comune(cod_comune)
            proc_ok = True
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.info("MOSAICO procedimenti non interrogabili per %s: %s", cod_comune, exc)
        if not sin_ok and not proc_ok:
            return None
        return ContaminationInfo(
            contaminato=bool(sin or n_cont > 0),
            sin=sin, sin_denominazione=sin_den,
            sir_procedimenti=n_proc, sir_contaminati=n_cont, matrici=matrici,
            source_url=f"{self._base}/{LAYER_SIN}", licenza=REGIONE_LICENZA,
        )
