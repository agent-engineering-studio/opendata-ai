"""Endpoint /territorio/* — selezione zona via tag OSM per la UI (spec 06).

La UI non parla con gli MCP (R13): il backend importa direttamente
`opendata_core.osm.zones` (shared lib, nessun hop MCP). Cache Redis 24h —
le zone di un comune cambiano raramente e l'istanza Overpass pubblica
throttla — sopra la TTLCache in-process del core.
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Depends

from opendata_core.osm import zones
from opendata_core.osm.zones import ZONA_TIPI, OverpassError

from ..auth import ClerkUser
from ..cache.store import cache_get, cache_set
from ..config import (
    REPORT_DEPTH_CONCISE_NOTE,
    check_territorio_scope,
    get_settings,
    province_scope,
    region_config,
    region_name,
    resolve_report_depth,
)
from ..shared.ratelimit import enforce_rate_limit

log = logging.getLogger("opendata-backend.territorio")

router = APIRouter(prefix="/territorio", tags=["territorio"])

_TTL = 24 * 3600


def _key(*parts: str) -> str:
    raw = "|".join(p.lower().strip() for p in parts).encode()
    return "od:territorio:" + hashlib.sha1(raw).hexdigest()


@router.get("/report-mode")
async def report_mode(
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Profondità del report territorio in base alla capacità del modello attivo.

    Serve alla UI per mostrare un disclaimer accanto a «Genera» quando il sistema
    usa un modello locale compatto (tier `concise`), che può produrre imprecisioni;
    sui modelli capaci (claude/azure/ollama_cloud) il tier è `full`.
    """
    depth = resolve_report_depth(get_settings())
    return {
        "depth": depth,
        "concise": depth == "concise",
        "note": REPORT_DEPTH_CONCISE_NOTE.strip() if depth == "concise" else None,
    }


@router.get("/regione")
async def regione_config(
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Regione configurata (`REGION`) per il badge/selettore UI (issue #191, F5).

    `scoped=false` in dev (nessun limite): la UI non mostra il badge. Con `REGION`
    impostato ritorna nome + province; col solo legacy `TERRITORIO_PROVINCE` il
    nome può essere assente (badge sulle province).
    """
    settings = get_settings()
    reg = region_config(settings)
    scope = province_scope(settings)
    return {
        "scoped": bool(reg) or bool(scope),
        "cod_regione": settings.region_istat or None,
        "nome": region_name(settings),
        "province": sorted(scope),
    }


@router.get("/comuni")
async def cerca_comuni(
    q: str = Query(min_length=2, max_length=80, description="Nome comune, anche parziale"),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Autocomplete comune → codice ISTAT (dai confini amministrativi OSM)."""
    scope = province_scope(get_settings())
    key = _key("comuni", q, ",".join(sorted(scope)))
    cached = await cache_get(key)
    if cached is not None:
        return cached
    try:
        results = await zones.lookup_comune(q)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if scope:
        # Ambito territoriale (es. produzione = Puglia): l'autocomplete
        # propone solo comuni delle province ammesse.
        results = [r for r in results if (r.get("ref_istat") or "")[:3] in scope]
    payload = {"results": results, "count": len(results)}
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload


@router.get("/confine")
async def confine_comune(
    osm_id: str = Query(
        pattern=r"^(relation|way)/\d+$",
        description="OSM id del confine, es. 'relation/44915' (da /territorio/comuni)",
    ),
    cod_comune: str | None = Query(
        default=None, pattern=r"^\d{6}$", description="Codice ISTAT per il controllo d'ambito"
    ),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Geometria GeoJSON del confine dell'INTERO comune (per la mappa).

    Analisi a livello comunale: la mappa mostra solo il comune, non le zone.
    """
    if cod_comune:
        try:
            check_territorio_scope(cod_comune, get_settings())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = _key("confine", osm_id)
    cached = await cache_get(key)
    if cached is not None:
        return cached
    osm_type, _, oid = osm_id.partition("/")
    try:
        feature = await zones.get_zone(osm_type, oid)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not feature:
        raise HTTPException(status_code=404, detail=f"Confine non trovato per {osm_id}")
    payload = {"osm_id": osm_id, "feature": feature}
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload


@router.get("/zone")
async def lista_zone(
    cod_comune: str = Query(pattern=r"^\d{6}$", description="Codice ISTAT, es. 072006"),
    tipo: str = Query(description=f"Uno tra: {', '.join(ZONA_TIPI)}"),
    comune_nome: str | None = Query(
        default=None, max_length=80,
        description="Nome del comune — abilita il fallback Nominatim",
    ),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: B008, ARG001
) -> dict:
    """Zone candidate di un tipo dentro il comune, con geometrie GeoJSON.

    Il payload dichiara il `fallback_level` (1 = tag match, 2 = Nominatim,
    3 = niente: la UI degrada all'analisi a livello comune).
    """
    if tipo not in ZONA_TIPI:
        raise HTTPException(
            status_code=422,
            detail=f"tipo {tipo!r} non valido. Valori ammessi: {', '.join(ZONA_TIPI)}",
        )
    try:
        check_territorio_scope(cod_comune, get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    key = _key("zone", cod_comune, tipo, comune_nome or "")
    cached = await cache_get(key)
    if cached is not None:
        return cached
    try:
        payload = await zones.list_zones(cod_comune, tipo, comune_nome=comune_nome)
    except OverpassError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await cache_set(key, payload, ttl_seconds=_TTL)
    return payload
