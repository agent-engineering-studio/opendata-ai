"""HTTP client wrappers for OpenStreetMap services.

Covers:
- Nominatim — geocoding + reverse geocoding
- Overpass — bounding-box / radius POI queries
- OSRM — routing (driving / walking / cycling)

All methods return plain dict/list structures so they can be JSON-serialised
directly by the MCP tool layer.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Literal

import httpx

from .settings import osm_settings as settings

Profile = Literal["driving", "walking", "cycling"]

_OSRM_PROFILE_MAP: dict[Profile, str] = {
    "driving": "car",
    "walking": "foot",
    "cycling": "bike",
}


def _headers() -> dict[str, str]:
    ua = settings.OSM_USER_AGENT
    if settings.OSM_CONTACT_EMAIL:
        ua = f"{ua} ({settings.OSM_CONTACT_EMAIL})"
    return {"User-Agent": ua, "Accept": "application/json"}


async def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, headers=_headers())


# ── Nominatim ───────────────────────────────────────────────────────

async def geocode(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Text → coordinates using Nominatim search."""
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "en",
        "limit": max(1, min(limit, 20)),
    }
    async with await _http() as client:
        r = await client.get(f"{settings.NOMINATIM_URL}/search", params=params)
        r.raise_for_status()
        return r.json()


async def reverse_geocode(lat: float, lon: float, zoom: int = 18) -> dict[str, Any]:
    """Coordinates → structured address using Nominatim reverse."""
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "en",
        "zoom": zoom,
    }
    async with await _http() as client:
        r = await client.get(f"{settings.NOMINATIM_URL}/reverse", params=params)
        r.raise_for_status()
        return r.json()


async def geocode_boundary(
    query: str, *, country_codes: str | None = "it"
) -> dict[str, Any] | None:
    """Geocoding + confine amministrativo (GeoJSON) via Nominatim.

    Usa `polygon_geojson=1` per ottenere la geometria del confine. Ritorna
    `{"name", "lat", "lon", "geojson"}` del primo risultato, o `None` se nessun
    match. `geojson` è la geometria GeoJSON (Polygon/MultiPolygon) se disponibile,
    altrimenti `None` (il chiamante può ripiegare sul centroide lat/lon).
    """
    params: dict[str, Any] = {
        "q": query,
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
        "accept-language": "it",
    }
    if country_codes:
        params["countrycodes"] = country_codes
    async with await _http() as client:
        r = await client.get(f"{settings.NOMINATIM_URL}/search", params=params)
        r.raise_for_status()
        data = r.json()
    if not data:
        return None
    top = data[0]
    return {
        "name": top.get("display_name"),
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "geojson": top.get("geojson"),
    }


# ── Overpass ────────────────────────────────────────────────────────

_CATEGORY_FILTER: dict[str, str] = {
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "bar": '["amenity"="bar"]',
    "hotel": '["tourism"="hotel"]',
    "hospital": '["amenity"="hospital"]',
    "pharmacy": '["amenity"="pharmacy"]',
    "school": '["amenity"="school"]',
    "university": '["amenity"="university"]',
    "supermarket": '["shop"="supermarket"]',
    "parking": '["amenity"="parking"]',
    "fuel": '["amenity"="fuel"]',
    "ev_charging": '["amenity"="charging_station"]',
    "atm": '["amenity"="atm"]',
    "bank": '["amenity"="bank"]',
    "park": '["leisure"="park"]',
    "museum": '["tourism"="museum"]',
    "attraction": '["tourism"="attraction"]',
    "bus_station": '["amenity"="bus_station"]',
    "train_station": '["railway"="station"]',
}


def _overpass_filter(category: str) -> str:
    if category in _CATEGORY_FILTER:
        return _CATEGORY_FILTER[category]
    # Fallback: treat unknown category as amenity=<value>
    safe = "".join(ch for ch in category if ch.isalnum() or ch in "_-")
    return f'["amenity"="{safe}"]'


# Le istanze Overpass pubbliche throttlano (429) e vanno in 504 sotto carico:
# OGNI chiamata Overpass del repo passa da `overpass_post`, che ritenta con
# backoff e RUOTA sui mirror di fallback (env OVERPASS_FALLBACK_URLS).
OVERPASS_FALLBACK_URLS = [
    u.strip()
    for u in os.getenv(
        "OVERPASS_FALLBACK_URLS", "https://overpass.kumi.systems/api/interpreter"
    ).split(",")
    if u.strip()
]
_OVERPASS_MAX_RETRIES = 3
_OVERPASS_RETRYABLE = (429, 502, 504)

log = logging.getLogger("opendata-core.osm")


class OverpassError(RuntimeError):
    """Overpass non raggiungibile o in errore dopo retry e rotazione mirror."""


def overpass_endpoints() -> list[str]:
    primary = settings.OVERPASS_URL
    return [primary] + [u for u in OVERPASS_FALLBACK_URLS if u != primary]


async def overpass_post(
    query: str,
    *,
    timeout: float = 30.0,
    backoff_base: float = 4.0,
    max_retries: int = _OVERPASS_MAX_RETRIES,
) -> list[dict[str, Any]]:
    """POST a Overpass con retry/backoff e rotazione degli endpoint."""
    last = ""
    endpoints = overpass_endpoints()
    async with await _http() as client:
        for attempt in range(max_retries):
            endpoint = endpoints[attempt % len(endpoints)]
            try:
                resp = await client.post(endpoint, data={"data": query}, timeout=timeout)
            except httpx.HTTPError as exc:
                last = f"transport: {type(exc).__name__}"
                log.warning("Overpass %s su %s — provo il mirror successivo", last, endpoint)
                continue
            if resp.status_code in _OVERPASS_RETRYABLE:
                last = f"HTTP {resp.status_code}"
                delay = backoff_base * (attempt + 1)
                log.warning("Overpass %s su %s — retry in %.1fs", last, endpoint, delay)
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json().get("elements", [])
    raise OverpassError(f"Overpass non disponibile dopo {max_retries} tentativi ({last})")


async def overpass_around(
    lat: float, lon: float, radius_m: int, category: str, limit: int = 30
) -> list[dict[str, Any]]:
    """POIs within `radius_m` metres of (lat, lon) matching `category`."""
    flt = _overpass_filter(category)
    # Query nodes + ways + relations, centroid for non-nodes.
    query = f"""
    [out:json][timeout:25];
    (
      node{flt}(around:{radius_m},{lat},{lon});
      way{flt}(around:{radius_m},{lat},{lon});
      relation{flt}(around:{radius_m},{lat},{lon});
    );
    out center tags {limit};
    """
    return await overpass_post(query, timeout=30.0, backoff_base=2.0)


async def overpass_bbox(
    south: float, west: float, north: float, east: float, category: str, limit: int = 50
) -> list[dict[str, Any]]:
    """POIs inside a bounding box (south,west,north,east) matching `category`."""
    flt = _overpass_filter(category)
    query = f"""
    [out:json][timeout:25];
    (
      node{flt}({south},{west},{north},{east});
      way{flt}({south},{west},{north},{east});
      relation{flt}({south},{west},{north},{east});
    );
    out center tags {limit};
    """
    return await overpass_post(query, timeout=30.0, backoff_base=2.0)


# ── Profilo commerciale (densità POI per categoria, lente Commercio/DUC) ──────
# Filtri Overpass per categoria commerciale. `negozi` (shop=*) è l'ombrello; le
# altre sono sottoinsiemi tematici utili al "mix". `totale` (sotto) è l'unione
# DEDUPLICATA — non la somma (che conterebbe due volte gli shop tematici).
_COMMERCIAL_FILTERS: dict[str, str] = {
    "negozi": '["shop"]',
    "alimentari": '["shop"~"^(supermarket|convenience|bakery|butcher|greengrocer|deli|grocery)$"]',
    "ristorazione": '["amenity"~"^(restaurant|cafe|bar|fast_food|pub|ice_cream)$"]',
    "mercati": '["amenity"="marketplace"]',
    "servizi": '["amenity"~"^(bank|pharmacy|post_office)$"]',
}


async def overpass_commercial_counts(
    *,
    around: tuple[float, float, int] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Conta i POI commerciali per categoria in UNA sola query (Overpass
    `out count`: payload minimo, nessuna enumerazione → niente problema del
    `limit`). `around=(lat,lon,radius_m)` oppure `bbox=(s,w,n,e)`.

    Ritorna `{categoria: n, ..., "totale": n}` dove `totale` è l'unione
    deduplicata di tutte le categorie. Categorie a 0 incluse.
    """
    if around is not None:
        lat, lon, radius_m = around
        region = f"(around:{int(radius_m)},{lat},{lon})"
    elif bbox is not None:
        s, w, n, e = bbox
        region = f"({s},{w},{n},{e})"
    else:
        raise ValueError("overpass_commercial_counts richiede `around` o `bbox`")

    keys = list(_COMMERCIAL_FILTERS)
    set_lines = [
        f"( node{flt}{region}; way{flt}{region}; )->.{key};"
        for key, flt in _COMMERCIAL_FILTERS.items()
    ]
    out_lines = [f".{key} out count;" for key in keys]
    union = "( " + " ".join(f".{k};" for k in keys) + " )->.tot;"
    query = "[out:json][timeout:25];\n" + "\n".join(set_lines) + "\n" + union + "\n" \
        + "\n".join(out_lines) + "\n.tot out count;"

    elements = await overpass_post(query, timeout=timeout, backoff_base=2.0)
    counts_elems = [el for el in elements if el.get("type") == "count"]

    def _total(el: dict[str, Any]) -> int:
        try:
            return int((el.get("tags") or {}).get("total", 0))
        except (TypeError, ValueError):
            return 0

    out: dict[str, int] = {}
    for i, key in enumerate(keys):
        out[key] = _total(counts_elems[i]) if i < len(counts_elems) else 0
    out["totale"] = _total(counts_elems[len(keys)]) if len(counts_elems) > len(keys) else 0
    return out


# ── Tourism / culture (lente Turismo/Cultura) ───────────────────────
#
# Asset culturali e ricettività mappati su OSM. `cultura` (teatri/cinema) e
# `ricettivita` sono separati dal commercio per non sovrapporsi alla lente
# Commercio (che conta shop/ristorazione).
_TOURISM_FILTERS: dict[str, str] = {
    "musei": '["tourism"="museum"]',
    "monumenti_siti": '["historic"~"^(monument|memorial|castle|archaeological_site|ruins|fort|monastery|city_gate)$"]',
    "attrazioni": '["tourism"~"^(attraction|artwork|viewpoint|gallery|theme_park)$"]',
    "ricettivita": '["tourism"~"^(hotel|guest_house|hostel|bed_and_breakfast|apartment|chalet|camp_site|motel)$"]',
    "cultura": '["amenity"~"^(theatre|arts_centre|cinema)$"]',
}
# I poli da NOMINARE (musei/monumenti/attrazioni): la ricettività e i teatri
# raramente hanno un nome "citabile" come asset → fuori dall'enumerazione.
_LANDMARK_FILTER = (
    '["name"]'
    '["tourism"~"^(museum|attraction|artwork|gallery|viewpoint|theme_park)$"]'
)
_LANDMARK_FILTER_HIST = (
    '["name"]'
    '["historic"~"^(monument|memorial|castle|archaeological_site|ruins|fort|monastery|city_gate)$"]'
)


async def overpass_tourism_counts(
    *,
    around: tuple[float, float, int] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Conta i POI turistico-culturali per categoria in UNA query (`out count`).

    `around=(lat,lon,radius_m)` oppure `bbox=(s,w,n,e)`. Ritorna
    `{categoria: n, ..., "totale": n}` (unione deduplicata). Mirror di
    `overpass_commercial_counts` con `_TOURISM_FILTERS`.
    """
    if around is not None:
        lat, lon, radius_m = around
        region = f"(around:{int(radius_m)},{lat},{lon})"
    elif bbox is not None:
        s, w, n, e = bbox
        region = f"({s},{w},{n},{e})"
    else:
        raise ValueError("overpass_tourism_counts richiede `around` o `bbox`")

    keys = list(_TOURISM_FILTERS)
    set_lines = [
        f"( node{flt}{region}; way{flt}{region}; )->.{key};"
        for key, flt in _TOURISM_FILTERS.items()
    ]
    out_lines = [f".{key} out count;" for key in keys]
    union = "( " + " ".join(f".{k};" for k in keys) + " )->.tot;"
    query = "[out:json][timeout:25];\n" + "\n".join(set_lines) + "\n" + union + "\n" \
        + "\n".join(out_lines) + "\n.tot out count;"

    elements = await overpass_post(query, timeout=timeout, backoff_base=2.0)
    counts_elems = [el for el in elements if el.get("type") == "count"]

    def _total(el: dict[str, Any]) -> int:
        try:
            return int((el.get("tags") or {}).get("total", 0))
        except (TypeError, ValueError):
            return 0

    out: dict[str, int] = {}
    for i, key in enumerate(keys):
        out[key] = _total(counts_elems[i]) if i < len(counts_elems) else 0
    out["totale"] = _total(counts_elems[len(keys)]) if len(counts_elems) > len(keys) else 0
    return out


async def overpass_tourism_landmarks(
    *,
    bbox: tuple[float, float, float, float],
    limit: int = 25,
    timeout: float = 30.0,
) -> list[dict[str, str]]:
    """Enumera i poli culturali NOMINATI (musei/monumenti/attrazioni) in un bbox.

    Enumerazione BOUNDED (`out tags <limit>`): payload piccolo. Serve a far
    NOMINARE un asset specifico a un'idea di valorizzazione. Ritorna
    `[{name, kind}]` deduplicato per nome, max `limit` voci.
    """
    s, w, n, e = bbox
    region = f"({s},{w},{n},{e})"
    cap = max(1, min(limit, 60))
    query = (
        "[out:json][timeout:25];\n"
        f"( node{_LANDMARK_FILTER}{region}; way{_LANDMARK_FILTER}{region};"
        f" node{_LANDMARK_FILTER_HIST}{region}; way{_LANDMARK_FILTER_HIST}{region}; );\n"
        f"out tags {cap};"
    )
    elements = await overpass_post(query, timeout=timeout, backoff_base=2.0)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        kind = tags.get("tourism") or tags.get("historic") or "poi"
        out.append({"name": name, "kind": kind})
        if len(out) >= cap:
            break
    return out


# ── OSRM ────────────────────────────────────────────────────────────

async def osrm_route(
    start: tuple[float, float],
    end: tuple[float, float],
    profile: Profile = "driving",
    steps: bool = True,
) -> dict[str, Any]:
    """Route from `start` to `end`. Coordinates are (lat, lon)."""
    osrm_profile = _OSRM_PROFILE_MAP.get(profile, "car")
    s_lat, s_lon = start
    e_lat, e_lon = end
    url = (
        f"{settings.OSRM_URL}/route/v1/{osrm_profile}/"
        f"{s_lon},{s_lat};{e_lon},{e_lat}"
    )
    params = {
        "overview": "simplified",
        "geometries": "geojson",
        "steps": "true" if steps else "false",
        "alternatives": "false",
    }
    async with await _http() as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def osrm_table(
    points: list[tuple[float, float]],
    profile: Profile = "driving",
) -> dict[str, Any]:
    """Duration matrix among N points (used by meeting-point heuristic)."""
    osrm_profile = _OSRM_PROFILE_MAP.get(profile, "car")
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    url = f"{settings.OSRM_URL}/table/v1/{osrm_profile}/{coords}"
    async with await _http() as client:
        r = await client.get(url, params={"annotations": "duration,distance"})
        r.raise_for_status()
        return r.json()
