"""Zone riconosciute via tag OSM — selezione del territorio senza PostGIS.

Discovery live (2026-06-12, vedi spec 06):
  - i confini comunali italiani su OSM portano `ref:ISTAT` zero-padded
    ("072006") sugli `admin_level=8` → match diretto col cod_comune ISTAT;
  - la resa per tipo è buona ma eterogenea (Bari: 137 aree industriali di cui
    57 nominate, la "Zona Industriale di Bari" è una RELATION multipolygon;
    Barletta: porto reale ma non taggato landuse=harbour);
  - il centro storico NON è mappato come `place` nemmeno a Bari, e Nominatim
    su "centro storico <comune>" può restituire un B&B → il fallback filtra
    per class place/boundary e la degradazione a livello comune è la norma;
  - le istanze pubbliche Overpass throttlano (429) e vanno in 504 sotto
    carico → retry con backoff e timeout espliciti.

Ogni candidato ha un `osm_url` citabile (licenza ODbL) — la zona stessa è
una risorsa verificabile, coerente col modello evidence-based del programma.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from cachetools import TTLCache

from .client import OverpassError, geocode
from .client import overpass_post as _overpass
from .geojson import feature_area_m2, overpass_to_features
from .settings import osm_settings as settings

__all__ = ["OverpassError", "ZonaTipo", "ZONA_TIPI", "lookup_comune", "list_zones", "get_zone"]

log = logging.getLogger("opendata-core.osm.zones")

ZonaTipo = Literal[
    "industriale", "commerciale", "portuale", "centro_storico", "verde", "agricola"
]

ZONA_TIPI: tuple[str, ...] = (
    "industriale", "commerciale", "portuale", "centro_storico", "verde", "agricola",
)

#: Overpass tag filters per zona_tipo (way + relation; node aggiunto per i
#: tipi "place-like"). Un solo posto nel repo per questa mappa (spec 06).
ZONA_FILTERS: dict[str, list[str]] = {
    "industriale": ['["landuse"="industrial"]', '["man_made"="works"]'],
    "commerciale": ['["landuse"="retail"]', '["landuse"="commercial"]'],
    "portuale": ['["landuse"="harbour"]', '["industrial"="port"]'],
    "centro_storico": [
        '["place"~"quarter|suburb|neighbourhood"]'
        '["name"~"[Cc]entro [Ss]torico|[Cc]ittà [Vv]ecchia|[Bb]orgo [Aa]ntico|[Vv]ecchia"]',
    ],
    "verde": ['["leisure"="park"]', '["boundary"="protected_area"]'],
    "agricola": ['["landuse"="farmland"]', '["landuse"="orchard"]', '["landuse"="vineyard"]'],
}

#: Tipi per cui ha senso cercare anche nodi place (punto, non poligono).
_NODE_TIPI = frozenset({"centro_storico"})

#: Label umane per il fallback Nominatim ("<label> <comune>").
ZONA_LABEL: dict[str, str] = {
    "industriale": "zona industriale",
    "commerciale": "zona commerciale",
    "portuale": "porto",
    "centro_storico": "centro storico",
    "verde": "parco",
    "agricola": "zona agricola",
}

#: Nominatim: classi accettabili per un'area urbana (scarta guest_house & co.).
_NOMINATIM_OK_CLASSES = frozenset({"place", "boundary", "landuse", "leisure"})

CACHE_TTL = 24 * 3600  # le zone di un comune cambiano raramente
_cache: TTLCache = TTLCache(maxsize=256, ttl=CACHE_TTL)

# La POST resiliente (retry + rotazione mirror) vive in client.overpass_post
# ed è condivisa con i tool POI (overpass_around/bbox): qui restano solo i
# profili di timeout.
_OVERPASS_TIMEOUT = 60
#: Profilo "interattivo" (autocomplete UI): risposte rapide o fallisci presto.
_SNAPPY_TIMEOUT = 12
_SNAPPY_BACKOFF = 1.5


def _osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


# ───────────────────────────── lookup comune ────────────────────────────────


async def lookup_comune(nome: str, limit: int = 8) -> list[dict[str, Any]]:
    """Nome (anche parziale) → comuni candidati con ref:ISTAT, da OSM.

    Cerca le relation `admin_level=8` per nome, case-insensitive. Il
    `ref_istat` ritornato è zero-padded, direttamente usabile come
    cod_comune nel resto dello stack.
    """
    needle = re.escape(nome.strip())
    if not needle:
        return []
    key = ("lookup", needle.lower())
    if key in _cache:
        return _cache[key]  # type: ignore[return-value]
    # Profilo snappy: è un autocomplete — meglio fallire in fretta (la UI ha
    # il fallback del codice ISTAT manuale) che far aspettare 30s+.
    query = (
        f'[out:json][timeout:{_SNAPPY_TIMEOUT}];'
        f'relation["boundary"="administrative"]["admin_level"="8"]'
        f'["name"~"^{needle}",i]["ref:ISTAT"];'
        f"out tags {max(1, min(limit, 20))};"
    )
    elements = await _overpass(
        query, timeout=_SNAPPY_TIMEOUT, backoff_base=_SNAPPY_BACKOFF
    )
    out = []
    for el in elements:
        tags = el.get("tags") or {}
        out.append(
            {
                "nome": tags.get("name"),
                "ref_istat": tags.get("ref:ISTAT"),
                "cod_provincia": tags.get("ref:ISTAT", "")[:3] or None,
                "osm_id": f"relation/{el.get('id')}",
                "osm_url": _osm_url("relation", el.get("id")),
            }
        )
    # Match esatto prima, poi alfabetico — "Bari" non deve perdersi tra i "Bari Sardo".
    out.sort(key=lambda c: (0 if (c["nome"] or "").lower() == nome.strip().lower() else 1,
                            c["nome"] or ""))
    _cache[key] = out
    return out


# ───────────────────────────── zone candidates ──────────────────────────────


def _candidate_from_feature(feat: dict[str, Any], zona_tipo: str) -> dict[str, Any]:
    props = feat.get("properties") or {}
    geom = feat.get("geometry") or {}
    area = feature_area_m2(feat)

    def _coords_iter():
        t = geom.get("type")
        if t == "Point":
            yield geom["coordinates"]
        elif t == "Polygon":
            yield from geom.get("coordinates", [[]])[0]
        elif t == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                yield from poly[0]

    lons = [c[0] for c in _coords_iter()]
    lats = [c[1] for c in _coords_iter()]
    bbox = [min(lats), min(lons), max(lats), max(lons)] if lons else None
    centroid = (
        {"lat": (bbox[0] + bbox[2]) / 2, "lon": (bbox[1] + bbox[3]) / 2} if bbox else None
    )
    return {
        "osm_type": props.get("osm_type"),
        "osm_id": f"{props.get('osm_type')}/{props.get('osm_id')}",
        "name": props.get("name"),
        "zona_tipo": zona_tipo,
        "area_m2": round(area),
        "centroid": centroid,
        "bbox": bbox,
        "osm_url": _osm_url(str(props.get("osm_type")), int(props.get("osm_id") or 0)),
        "geometry": geom,
    }


async def list_zones(
    ref_istat: str,
    zona_tipo: str,
    *,
    limit: int = 30,
    comune_nome: str | None = None,
) -> dict[str, Any]:
    """Zone candidate di un tipo dentro un comune, con catena di fallback.

    Ritorna {"candidates": [...], "fallback_level": 1|2|3, "source_url": ...}.
      1 = match per tag dentro il confine comunale (caso ideale);
      2 = area nominata trovata via Nominatim (richiede `comune_nome`);
      3 = nessuna geometria → si degrada all'analisi a livello comune.
    """
    if zona_tipo not in ZONA_FILTERS:
        raise ValueError(
            f"zona_tipo {zona_tipo!r} non valido. Valori ammessi: {', '.join(ZONA_TIPI)}"
        )
    ref = str(ref_istat).strip()
    cache_key = ("zones", ref, zona_tipo)
    if cache_key in _cache:
        return _cache[cache_key]  # type: ignore[return-value]

    filters = ZONA_FILTERS[zona_tipo]
    parts = "".join(f"way{f}(area.a);relation{f}(area.a);" for f in filters)
    if zona_tipo in _NODE_TIPI:
        parts += "".join(f"node{f}(area.a);" for f in filters)
    query = (
        f'[out:json][timeout:{_OVERPASS_TIMEOUT}];'
        f'area["boundary"="administrative"]["admin_level"="8"]["ref:ISTAT"="{ref}"]->.a;'
        f"({parts});out geom;"
    )
    elements = await _overpass(query, timeout=_OVERPASS_TIMEOUT)
    features = overpass_to_features(elements)
    candidates = [_candidate_from_feature(f, zona_tipo) for f in features]
    # Nominati prima, poi per area decrescente (discovery: molte particelle anonime).
    candidates.sort(key=lambda c: (0 if c["name"] else 1, -(c["area_m2"] or 0)))
    candidates = candidates[: max(1, limit)]

    fallback_level = 1
    if not candidates and comune_nome:
        candidates = await _nominatim_fallback(zona_tipo, comune_nome)
        fallback_level = 2 if candidates else 3
    elif not candidates:
        fallback_level = 3

    out = {
        "candidates": candidates,
        "fallback_level": fallback_level,
        "zona_tipo": zona_tipo,
        "ref_istat": ref,
        "source_url": f"{settings.OVERPASS_URL}?data={query}"[:500],
    }
    _cache[cache_key] = out
    return out


async def _nominatim_fallback(zona_tipo: str, comune_nome: str) -> list[dict[str, Any]]:
    """Fallback 2: cerca un'area nominata via Nominatim, filtrando per classe.

    Discovery: senza filtro, "centro storico Barletta" ritorna un guest house —
    accettiamo solo class place/boundary/landuse/leisure.
    """
    label = ZONA_LABEL.get(zona_tipo, zona_tipo)
    try:
        hits = await geocode(f"{label} {comune_nome}", limit=5)
    except Exception:  # rete/quota: il fallback non deve rompere la catena
        log.warning("Nominatim fallback failed for %s %s", label, comune_nome, exc_info=True)
        return []
    out = []
    for h in hits:
        if (h.get("class") or h.get("category")) not in _NOMINATIM_OK_CLASSES:
            continue
        osm_type, osm_id = h.get("osm_type"), h.get("osm_id")
        if not osm_type or not osm_id:
            continue
        lat, lon = float(h.get("lat", 0)), float(h.get("lon", 0))
        bb = h.get("boundingbox")
        bbox = [float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3])] if bb else None
        out.append(
            {
                "osm_type": osm_type,
                "osm_id": f"{osm_type}/{osm_id}",
                "name": h.get("display_name", "").split(",")[0] or None,
                "zona_tipo": zona_tipo,
                "area_m2": 0,
                "centroid": {"lat": lat, "lon": lon},
                "bbox": bbox,
                "osm_url": _osm_url(str(osm_type), int(osm_id)),
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    return out


async def get_zone(osm_type: str, osm_id: int | str) -> dict[str, Any] | None:
    """Geometria GeoJSON completa di una singola zona (Feature), o None."""
    t = osm_type.strip().lower()
    if t not in {"way", "relation", "node"}:
        raise ValueError("osm_type deve essere way|relation|node")
    oid = int(str(osm_id).split("/")[-1])
    query = f"[out:json][timeout:{_OVERPASS_TIMEOUT}];{t}({oid});out geom;"
    elements = await _overpass(query, timeout=_OVERPASS_TIMEOUT)
    features = overpass_to_features(elements)
    return features[0] if features else None


def cache_clear() -> None:
    _cache.clear()
