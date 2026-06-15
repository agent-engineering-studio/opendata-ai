"""GeoJSON parsing, validation, normalization and styling utilities.

Pure Python, no I/O, no network. All functions are deterministic and side-effect
free. The module sits between the OSM tool layer (which produces raw
JSON dicts) and the rendering layer (which expects FeatureCollections + styles).

CRS policy: GeoJSON RFC 7946 mandates WGS84 (EPSG:4326). Inputs declaring a
different CRS via the (deprecated) "crs" member are rejected with a clear
ValueError. Automatic reprojection is out of scope.
"""
from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

# Italy default bbox used when an empty FeatureCollection is given to
# compute_bounds. Avoids div-by-zero when callers blindly fitBounds().
_ITALY_BBOX: tuple[float, float, float, float] = (35.5, 6.6, 47.1, 18.5)

# 12-color palette (high-contrast, color-blind friendly).
_PALETTE: list[str] = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#42d4f4",
    "#f032e6", "#469990", "#9A6324", "#800000", "#808000", "#000075",
]


def parse_geojson(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Parse and normalize a GeoJSON input into a FeatureCollection dict.

    Accepts JSON strings, FeatureCollection dicts, single Feature dicts, and
    raw Geometry dicts. Wraps non-collection inputs as needed.

    Strips features whose geometry is None or invalid (logs a warning with the
    count). Rejects non-WGS84 CRS declarations with ValueError.
    """
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid GeoJSON string: {exc}") from exc
    else:
        data = raw

    if not isinstance(data, dict):
        raise ValueError(f"GeoJSON must be a JSON object, got {type(data).__name__}")

    _reject_non_wgs84(data)

    gtype = data.get("type")
    if gtype == "FeatureCollection":
        fc = data
    elif gtype == "Feature":
        fc = {"type": "FeatureCollection", "features": [data]}
    elif gtype in {"Point", "LineString", "Polygon", "MultiPoint",
                   "MultiLineString", "MultiPolygon", "GeometryCollection"}:
        fc = {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": data, "properties": {}}],
        }
    else:
        raise ValueError(f"unsupported GeoJSON type: {gtype!r}")

    raw_features = list(fc.get("features") or [])
    valid = [f for f in raw_features if _is_valid_feature(f)]
    dropped = len(raw_features) - len(valid)
    if dropped:
        log.warning("geojson_builder: dropped %d invalid features", dropped)
    return {"type": "FeatureCollection", "features": valid}


def _reject_non_wgs84(data: dict[str, Any]) -> None:
    crs = data.get("crs")
    if not crs:
        return
    name = (crs.get("properties") or {}).get("name") or ""
    if "CRS84" in name or "4326" in name or "WGS" in name.upper():
        return
    raise ValueError(
        f"non-WGS84 CRS not supported (got {name!r}); "
        "please reproject to EPSG:4326 (RFC 7946)"
    )


def _is_valid_feature(feature: dict[str, Any]) -> bool:
    if feature.get("type") != "Feature":
        return False
    geom = feature.get("geometry")
    if not isinstance(geom, dict):
        return False
    coords = geom.get("coordinates")
    if coords is None and geom.get("type") != "GeometryCollection":
        return False
    return True


def compute_bounds(geojson: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) bbox of a FeatureCollection.

    For empty collections returns Italy's default bbox so map fits gracefully.
    """
    south = +90.0
    north = -90.0
    west = +180.0
    east = -180.0
    has_any = False
    for feat in geojson.get("features", []):
        for lon, lat in _iter_coords(feat.get("geometry") or {}):
            has_any = True
            if lat < south:
                south = lat
            if lat > north:
                north = lat
            if lon < west:
                west = lon
            if lon > east:
                east = lon
    if not has_any:
        return _ITALY_BBOX
    return (south, west, north, east)


def _iter_coords(geom: dict[str, Any]):
    """Yield (lon, lat) pairs from any GeoJSON geometry."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point" and coords is not None:
        yield (coords[0], coords[1])
    elif gtype in {"LineString", "MultiPoint"}:
        for c in coords or []:
            yield (c[0], c[1])
    elif gtype in {"Polygon", "MultiLineString"}:
        for ring in coords or []:
            for c in ring:
                yield (c[0], c[1])
    elif gtype == "MultiPolygon":
        for poly in coords or []:
            for ring in poly:
                for c in ring:
                    yield (c[0], c[1])
    elif gtype == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from _iter_coords(g)


def assign_layer_styles(count: int) -> list[dict[str, Any]]:
    """Return N distinct Leaflet style dicts. Cycles palette if N > 12."""
    return [
        {"color": _PALETTE[i % len(_PALETTE)],
         "weight": 2,
         "fillOpacity": 0.5,
         "radius": 6}
        for i in range(count)
    ]


# ── Overpass `out geom` → GeoJSON features ──────────────────────────────
#
# Used by the zone-selection layer (zones.py). Pure Python on purpose: the
# repo has no GIS dependency and ranking/centroids only need approximate
# math. Way members arrive with an inline `geometry` list of {lat, lon};
# relations carry their members inline (roles outer/inner).


def _ring_from_way_geometry(geometry: list[dict[str, Any]]) -> list[list[float]] | None:
    """Overpass way geometry → GeoJSON ring [[lon, lat], …]; None if degenerate."""
    if not geometry or len(geometry) < 2:
        return None
    return [[pt["lon"], pt["lat"]] for pt in geometry]


def _close_ring(ring: list[list[float]]) -> list[list[float]]:
    return ring if ring[0] == ring[-1] else ring + [ring[0]]


def _join_ways_into_rings(ways: list[list[list[float]]]) -> list[list[list[float]]]:
    """Join open way segments that share endpoints into closed rings.

    Multipolygon relations split each outer/inner ring across several ways;
    this stitches them back greedily. Segments that can't be closed are
    dropped (logged) — better a missing ring than a corrupt polygon.
    """
    segments = [list(w) for w in ways if len(w) >= 2]
    rings: list[list[list[float]]] = []
    while segments:
        ring = segments.pop(0)
        progress = True
        while ring[0] != ring[-1] and progress:
            progress = False
            for i, seg in enumerate(segments):
                if seg[0] == ring[-1]:
                    ring.extend(seg[1:])
                elif seg[-1] == ring[-1]:
                    ring.extend(list(reversed(seg))[1:])
                elif seg[-1] == ring[0]:
                    ring[:0] = seg[:-1]
                elif seg[0] == ring[0]:
                    ring[:0] = list(reversed(seg))[:-1]
                else:
                    continue
                segments.pop(i)
                progress = True
                break
        if ring[0] == ring[-1] and len(ring) >= 4:
            rings.append(ring)
        else:
            log.warning("overpass_to_features: dropped unclosable ring (%d pts)", len(ring))
    return rings


def _point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting — good enough to attach inner rings to their outer."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def ring_area_m2(ring: list[list[float]]) -> float:
    """Approximate planar area (m²) of a WGS84 ring — equirectangular shoelace.

    Plenty accurate at comune scale for RANKING zones by size; not survey-grade.
    """
    import math

    if len(ring) < 4:
        return 0.0
    lat0 = math.radians(sum(p[1] for p in ring) / len(ring))
    k = 111_320.0  # metres per degree
    pts = [(p[0] * k * math.cos(lat0), p[1] * k) for p in ring]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def overpass_to_features(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn Overpass `out geom` elements (node/way/relation) into GeoJSON Features.

    - closed ways → Polygon; open ways are skipped (zones are areas);
    - relations → Polygon/MultiPolygon assembled from outer/inner members,
      inner rings attached to the first outer that contains them;
    - nodes → Point (place markers, e.g. a centro storico node).
    Each feature gets properties: tags + osm_type/osm_id.
    """
    features: list[dict[str, Any]] = []
    for el in elements:
        etype, eid = el.get("type"), el.get("id")
        tags = el.get("tags") or {}
        props = {**tags, "osm_type": etype, "osm_id": eid}
        geom: dict[str, Any] | None = None

        if etype == "node" and "lat" in el and "lon" in el:
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}

        elif etype == "way":
            ring = _ring_from_way_geometry(el.get("geometry") or [])
            if ring and ring[0] == ring[-1] and len(ring) >= 4:
                geom = {"type": "Polygon", "coordinates": [ring]}
            else:
                log.debug("overpass_to_features: skipped open way %s", eid)

        elif etype == "relation":
            outers_raw, inners_raw = [], []
            for m in el.get("members") or []:
                if m.get("type") != "way" or not m.get("geometry"):
                    continue
                ring = _ring_from_way_geometry(m["geometry"])
                if ring is None:
                    continue
                (outers_raw if m.get("role") != "inner" else inners_raw).append(ring)
            outers = _join_ways_into_rings(outers_raw)
            inners = _join_ways_into_rings(inners_raw)
            if outers:
                polys: list[list[list[list[float]]]] = [[_close_ring(o)] for o in outers]
                for inner in inners:
                    lon, lat = inner[0]
                    target = next(
                        (p for p in polys if _point_in_ring(lon, lat, p[0])), polys[0]
                    )
                    target.append(_close_ring(inner))
                geom = (
                    {"type": "Polygon", "coordinates": polys[0]}
                    if len(polys) == 1
                    else {"type": "MultiPolygon", "coordinates": polys}
                )

        if geom is not None:
            features.append({"type": "Feature", "geometry": geom, "properties": props})
    return features


def feature_area_m2(feature: dict[str, Any]) -> float:
    """Approximate area of a Polygon/MultiPolygon feature (outer rings only)."""
    geom = feature.get("geometry") or {}
    if geom.get("type") == "Polygon":
        rings = [geom["coordinates"][0]] if geom.get("coordinates") else []
    elif geom.get("type") == "MultiPolygon":
        rings = [poly[0] for poly in geom.get("coordinates", []) if poly]
    else:
        return 0.0
    return sum(ring_area_m2(r) for r in rings)
