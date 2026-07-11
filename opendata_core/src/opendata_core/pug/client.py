"""Consultazione DAL VIVO della zonizzazione PUG/PRG come open data (#129, Fase 3).

Principio vincolante (pivot del progetto): il PUG è una fonte **interrogabile dal
vivo** o è "non pubblicato" — nessun knowledge graph, nessun upload di documenti,
nessuna analisi "memorizzata" come surrogato. Il connettore cerca sul portale CKAN
regionale il dataset di zonizzazione del comune e ne legge i poligoni; se non lo
trova (o non è interpretabile) ritorna ``None`` → il chiamante lo tratta come "non
pubblicato" e lo registra come domanda di riuso non soddisfatta (Fase 5).

Motore puro: riusa `CkanClient` (nessun nuovo client HTTP) + `point_in_geojson`.
Fail-safe: qualunque errore/timeout → ``None``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..ckan.client import CkanClient
from ..osm.client import point_in_geojson
from .models import PugZoning

log = logging.getLogger("opendata-core.pug")

# Termini che qualificano un dataset di zonizzazione urbanistica.
_ZONING_TERMS = ("zonizzazione", "zone omogenee", "pug", "prg", "piano urbanistic", "azzonamento")
# Attributi candidati (schema NON standard tra portali) che portano la zona omogenea.
_ZONE_KEYS = (
    "zto", "zona", "zona_omog", "zona_om", "sigla", "sigla_zto", "tipo_zona",
    "destinazione", "des_zona", "zona_urb", "classe", "zona_dgr",
)
_GEOJSON_FORMATS = {"geojson", "json"}
_SEARCH_ROWS = 25


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_zoning_package(pkg: dict[str, Any], comune_nome: str) -> bool:
    """Il pacchetto è una zonizzazione DEL comune indicato?"""
    blob = f"{_norm(pkg.get('title'))} {_norm(pkg.get('notes'))}"
    if not any(t in blob for t in _ZONING_TERMS):
        return False
    # il comune deve comparire nel titolo/note/organizzazione (evita zonizzazioni di altri comuni)
    com = _norm(comune_nome)
    org = _norm((pkg.get("organization") or {}).get("title"))
    return bool(com) and (com in blob or com in org)


def _geojson_resource_url(pkg: dict[str, Any]) -> str | None:
    for res in pkg.get("resources") or []:
        fmt = _norm(res.get("format"))
        url = res.get("url")
        if url and (fmt in _GEOJSON_FORMATS or str(url).lower().endswith(".geojson")):
            return str(url)
    return None


def _detect_zone_key(features: list[dict]) -> str | None:
    if not features:
        return None
    props = {k.lower(): k for k in (features[0].get("properties") or {})}
    for cand in _ZONE_KEYS:
        if cand in props:
            return props[cand]
    return None


async def fetch_zoning(
    *, comune_nome: str, base_url: str, client: CkanClient | None = None,
) -> PugZoning | None:
    """Cerca e legge la zonizzazione PUG/PRG del comune dal portale CKAN `base_url`.

    Ritorna ``PugZoning`` se trovata e interpretabile, altrimenti ``None`` (non
    pubblicata / non interrogabile). Sempre fail-safe."""
    if not comune_nome or not base_url:
        return None

    async def _work(c: CkanClient) -> PugZoning | None:
        q = " OR ".join(_ZONING_TERMS[:4])
        result = await c.action(
            "package_search", base_url=base_url,
            params={"q": f"({q}) {comune_nome}", "rows": str(_SEARCH_ROWS)},
        )
        packages = (result or {}).get("results") or []
        pkg = next((p for p in packages if _is_zoning_package(p, comune_nome)), None)
        if pkg is None:
            return None
        url = _geojson_resource_url(pkg)
        if url is None:
            return None  # trovato ma senza risorsa GeoJSON interrogabile → non usabile
        dl = await c.download_resource(url)
        try:
            data = json.loads(dl.get("content") or "")
        except (ValueError, TypeError):
            return None  # non-JSON o troncato → non interpretabile
        features = data.get("features") if isinstance(data, dict) else None
        if not features:
            return None
        zone_key = _detect_zone_key(features)
        if zone_key is None:
            return None  # schema non riconosciuto → trattato come non interrogabile
        return PugZoning(
            zone_key=zone_key, features=features, dataset_title=str(pkg.get("title") or ""),
            source_url=url, licenza=str((pkg.get("license_title") or pkg.get("license_id") or "n/d")),
        )

    try:
        if client is not None:
            return await _work(client)
        async with CkanClient() as c:
            return await _work(c)
    except Exception as exc:  # noqa: BLE001 — fail-safe: PUG assente/non interrogabile → None
        log.info("zonizzazione PUG non consultabile su %s per %s: %s", base_url, comune_nome, exc)
        return None


def zone_at(zoning: PugZoning, lat: float, lon: float) -> str | None:
    """Zona omogenea (valore di `zone_key`) del poligono che contiene il punto, o None."""
    for feat in zoning.features:
        geom = feat.get("geometry")
        if geom and point_in_geojson(lat, lon, geom):
            val = (feat.get("properties") or {}).get(zoning.zone_key)
            if val is not None and str(val).strip():
                return str(val).strip()
    return None
