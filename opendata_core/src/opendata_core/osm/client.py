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
# Default: mirror FR per primo (overpass-api.de e kumi sono bloccati in egress
# da alcune reti — vedi nota operativa). Sovrascrivibile via env.
OVERPASS_FALLBACK_URLS = [
    u.strip()
    for u in os.getenv(
        "OVERPASS_FALLBACK_URLS",
        "https://overpass.openstreetmap.fr/api/interpreter,"
        "https://overpass.kumi.systems/api/interpreter",
    ).split(",")
    if u.strip()
]
_OVERPASS_MAX_RETRIES = 3
_OVERPASS_RETRYABLE = (429, 502, 504)
# Un mirror irraggiungibile (egress bloccato → spesso il pacchetto è DROPpato,
# niente RST: la connect resterebbe appesa fino al timeout di read) va scartato
# in fretta. Teniamo il CONNECT corto e il READ generoso (Overpass calcola query
# pesanti per decine di secondi su un host VIVO).
_OVERPASS_CONNECT_TIMEOUT = 6.0

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
    """POST a Overpass con rotazione degli endpoint a ogni fallimento.

    Due cambi rispetto al naïve "ritenta lo stesso host con backoff":
    - CONNECT corto (`_OVERPASS_CONNECT_TIMEOUT`): un mirror morto (egress
      bloccato → il pacchetto è DROPpato, niente RST) si scarta in pochi secondi
      invece di appendere la connect fino al timeout di read. Il READ resta
      generoso per un host VIVO che calcola una query pesante.
    - Su un errore di trasporto (host irraggiungibile) NON si dorme: ritentare lo
      stesso host è solo tempo perso, si ruota subito al mirror successivo. Lo
      sleep di backoff serve solo quando c'è un UNICO mirror che throttla (429):
      con più mirror la rotazione è già la mitigazione giusta.

    In rete sana non cambia nulla: il primo mirror raggiungibile risponde e si
    esce al primo tentativo.
    """
    last = ""
    endpoints = overpass_endpoints()
    httpx_timeout = httpx.Timeout(timeout, connect=min(_OVERPASS_CONNECT_TIMEOUT, timeout))
    attempts = max(max_retries, len(endpoints))
    async with await _http() as client:
        for attempt in range(attempts):
            endpoint = endpoints[attempt % len(endpoints)]
            try:
                resp = await client.post(
                    endpoint, data={"data": query}, timeout=httpx_timeout
                )
            except httpx.HTTPError as exc:
                last = f"transport: {type(exc).__name__}"
                log.warning(
                    "Overpass %s su %s — mirror irraggiungibile, passo al prossimo",
                    last, endpoint,
                )
                continue  # host morto: nessuno sleep, prova subito il mirror dopo
            if resp.status_code in _OVERPASS_RETRYABLE:
                last = f"HTTP {resp.status_code}"
                # Sleep solo se NON c'è un altro mirror su cui ruotare (un solo
                # endpoint): altrimenti il prossimo giro tocca già un host diverso.
                if len(endpoints) == 1 and attempt + 1 < attempts:
                    delay = backoff_base * (attempt + 1)
                    log.warning("Overpass %s su %s — retry in %.1fs", last, endpoint, delay)
                    await asyncio.sleep(delay)
                else:
                    log.warning("Overpass %s su %s — ruoto al mirror successivo", last, endpoint)
                continue
            resp.raise_for_status()
            return resp.json().get("elements", [])
    raise OverpassError(
        f"Overpass non disponibile su {len(endpoints)} mirror dopo {attempts} tentativi ({last})"
    )


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


# ── Trasporti / mobilità (lente Trasporti) ──────────────────────────
#
# Densità del trasporto pubblico mappato su OSM. Misura quanto il comune è servito
# dal TPL e se ha un nodo ferroviario — gap di accessibilità / dipendenza dall'auto.
_TRANSPORT_FILTERS: dict[str, str] = {
    "fermate_bus": '["highway"="bus_stop"]',
    "autostazioni": '["amenity"="bus_station"]',
    "stazioni_treno": '["railway"~"^(station|halt)$"]',
    "tram_metro": '["railway"~"^(tram_stop|subway_entrance)$"]',
}


async def overpass_transport_counts(
    *,
    around: tuple[float, float, int] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Conta i nodi del trasporto pubblico per categoria in UNA query (`out count`).

    `around=(lat,lon,radius_m)` oppure `bbox=(s,w,n,e)`. Ritorna
    `{categoria: n, ..., "totale": n}` (unione deduplicata). Mirror di
    `overpass_tourism_counts` con `_TRANSPORT_FILTERS`.
    """
    if around is not None:
        lat, lon, radius_m = around
        region = f"(around:{int(radius_m)},{lat},{lon})"
    elif bbox is not None:
        s, w, n, e = bbox
        region = f"({s},{w},{n},{e})"
    else:
        raise ValueError("overpass_transport_counts richiede `around` o `bbox`")

    keys = list(_TRANSPORT_FILTERS)
    set_lines = [
        f"( node{flt}{region}; way{flt}{region}; )->.{key};"
        for key, flt in _TRANSPORT_FILTERS.items()
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


# ── Sanità (lente Sanità) ───────────────────────────────────────────
#
# Presìdi sanitari mappati su OSM, complementari alle farmacie del Min. Salute:
# ospedali e strutture territoriali (ambulatori/cliniche, studi medici). Misura
# l'accessibilità geografica ai servizi sanitari dentro il confine del comune.
_HEALTH_FILTERS: dict[str, str] = {
    "ospedali": '["amenity"="hospital"]',
    "ambulatori": '["amenity"="clinic"]',
    "studi_medici": '["amenity"="doctors"]',
}


async def overpass_health_counts(
    *,
    around: tuple[float, float, int] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Conta i presìdi sanitari per categoria in UNA query (`out count`).

    `around=(lat,lon,radius_m)` oppure `bbox=(s,w,n,e)`. Ritorna
    `{categoria: n, ..., "totale": n}`. Mirror di `overpass_transport_counts`
    con `_HEALTH_FILTERS`.
    """
    if around is not None:
        lat, lon, radius_m = around
        region = f"(around:{int(radius_m)},{lat},{lon})"
    elif bbox is not None:
        s, w, n, e = bbox
        region = f"({s},{w},{n},{e})"
    else:
        raise ValueError("overpass_health_counts richiede `around` o `bbox`")

    keys = list(_HEALTH_FILTERS)
    set_lines = [
        f"( node{flt}{region}; way{flt}{region}; )->.{key};"
        for key, flt in _HEALTH_FILTERS.items()
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


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza in linea d'aria (km) tra due punti (lat/lon in gradi)."""
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, a**0.5))


async def nearest_hospital(
    lat: float, lon: float, *, radii_m: tuple[int, ...] = (15000, 40000, 90000)
) -> dict[str, Any] | None:
    """Ospedale (amenity=hospital) più vicino a (lat,lon), cercando in raggi
    CRESCENTI (Overpass live). Utile per i comuni SENZA ospedale: misura
    l'accessibilità ospedaliera. Ritorna `{nome, lat, lon, dist_linea_km}` del più
    vicino in linea d'aria, o None se nessuno entro il raggio massimo. La distanza/
    tempo STRADALI si ottengono poi con `osrm_route()`."""
    for radius in radii_m:
        elements = await overpass_around(lat, lon, radius, "hospital", limit=80)
        best: dict[str, Any] | None = None
        best_d: float | None = None
        for el in elements:
            center = el.get("center") or {}
            elat = el.get("lat", center.get("lat"))
            elon = el.get("lon", center.get("lon"))
            if elat is None or elon is None:
                continue
            d = _haversine_km(lat, lon, float(elat), float(elon))
            if best_d is None or d < best_d:
                best_d = d
                best = {
                    "nome": (el.get("tags") or {}).get("name") or "ospedale",
                    "lat": float(elat),
                    "lon": float(elon),
                    "dist_linea_km": round(d, 1),
                }
        if best:
            return best
    return None


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


# ── Aree candidate per la rigenerazione (opportunity mining, Fase 2) ───────
#
# Vuoti urbani / aree dismesse o sottoutilizzate riusabili per dotazioni
# (mercato/eventi, sport, parcheggi, spazi pubblici). Tipologie OSM dei "vuoti":
_CANDIDATE_AREA_FILTERS = [
    '["landuse"="brownfield"]',                # area dismessa / da bonificare
    '["landuse"="greenfield"]',                # area libera edificabile
    '["disused:landuse"]',                     # ex-uso dismesso (qualsiasi)
    '["abandoned:landuse"]',
    '["landuse"="railway"]["disused"="yes"]',  # ex sedime ferroviario
    '["place"="square"]',                      # piazze / slarghi
    '["amenity"="parking"]',                   # parcheggi (riqualificabili a polifunzionali)
    '["building"="ruins"]',
]


def _polygon_area_m2(coords: list[tuple[float, float]]) -> float:
    """Area approssimata (m²) di un anello (lat,lon) via proiezione equirettangolare
    locale + shoelace. Sufficiente per ordinare/filtrare i candidati (non catastale)."""
    import math

    if len(coords) < 3:
        return 0.0
    lat0 = sum(c[0] for c in coords) / len(coords)
    rr = 6371000.0
    coslat = math.cos(math.radians(lat0))
    pts = [(math.radians(lon) * rr * coslat, math.radians(lat) * rr) for lat, lon in coords]
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


async def overpass_candidate_areas(
    *,
    bbox: tuple[float, float, float, float],
    limit: int = 20,
    timeout: float = 40.0,
) -> list[dict[str, Any]]:
    """Enumera AREE candidate (vuoti urbani / dismessi / sottoutilizzati) in un bbox.

    `out geom` per calcolare l'area approssimata di ogni way/relation. Ritorna
    `[{osm_type, osm_id, name, kind, lat, lon, area_mq, url}]` ordinato per area
    decrescente, max `limit`. Fail-safe a monte: `overpass_post` ruota i mirror e
    apre il circuit breaker; il chiamante cattura le eccezioni di trasporto."""
    s, w, n, e = bbox
    region = f"({s},{w},{n},{e})"
    union = "".join(f" way{f}{region}; relation{f}{region};" for f in _CANDIDATE_AREA_FILTERS)
    cap = max(1, min(limit * 3, 120))
    query = f"[out:json][timeout:{int(timeout)}];\n({union}\n);\nout geom {cap};"
    elements = await overpass_post(query, timeout=timeout, backoff_base=2.0)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in elements:
        geom = el.get("geometry") or []
        coords = [(g["lat"], g["lon"]) for g in geom if "lat" in g and "lon" in g]
        if len(coords) < 3:
            continue
        area = _polygon_area_m2(coords)
        if area < 300:  # scarta micro-poligoni (rumore)
            continue
        otype, oid = el.get("type", "way"), el.get("id")
        key = f"{otype}/{oid}"
        if key in seen:
            continue
        seen.add(key)
        tags = el.get("tags") or {}
        kind = (
            tags.get("landuse") or tags.get("amenity") or tags.get("place")
            or tags.get("building") or "area"
        )
        out.append({
            "osm_type": otype,
            "osm_id": oid,
            "name": (tags.get("name") or "").strip() or None,
            "kind": kind,
            "lat": round(sum(c[0] for c in coords) / len(coords), 6),
            "lon": round(sum(c[1] for c in coords) / len(coords), 6),
            "area_mq": int(round(area)),
            "url": f"https://www.openstreetmap.org/{otype}/{oid}",
        })
    out.sort(key=lambda d: d["area_mq"], reverse=True)
    return out[:limit]
