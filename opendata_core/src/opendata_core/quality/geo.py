"""Geo doctor — diagnosi di un GeoJSON (Data Quality Lab #49, geo).

`profile_geojson(text)` verifica che il file sia GeoJSON valido, **rileva il CRS**
(dichiarato o per euristica sulle coordinate) e segnala il problema più frequente
dei dati geografici comunali: **coordinate proiettate** (in metri) invece di
WGS84 (lon/lat in gradi) → non compaiono sulla mappa. Conta feature e tipi di
geometria, segnala geometrie vuote / coordinate fuori range, calcola la bbox e
un punteggio. Pure Python (nessuna libreria geo): la RIPROIEZIONE a WGS84 la fa
il frontend (`lib/geoReproject.toWgs84`, proj4) in fase di download.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .profile import _PENALITA, _finding

# CRS già WGS84 (lon/lat): nessuna riproiezione necessaria.
_WGS84_NAMES = ("EPSG:4326", "CRS84", "OGC:1.3:CRS84")
_EPSG_RE = re.compile(r"EPSG:*:?(\d{3,6})", re.IGNORECASE)
# tipi di geometria GeoJSON ammessi
_GEOM_TYPES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
}


def _epsg_from_crs(obj: dict[str, Any]) -> str | None:
    """EPSG dal membro `crs` (GeoJSON pre-RFC7946), es. 'EPSG:32632'. None se assente."""
    name = (((obj.get("crs") or {}).get("properties") or {}).get("name"))
    if not isinstance(name, str):
        return None
    up = name.upper()
    if "CRS84" in up:
        return "EPSG:4326"
    m = _EPSG_RE.search(up)
    return f"EPSG:{m.group(1)}" if m else None


def _features(obj: dict[str, Any]) -> list[dict[str, Any]]:
    t = obj.get("type")
    if t == "FeatureCollection" and isinstance(obj.get("features"), list):
        return [f for f in obj["features"] if isinstance(f, dict)]
    if t == "Feature":
        return [obj]
    if t in _GEOM_TYPES:  # bare geometry → wrappa come feature senza properties
        return [{"type": "Feature", "geometry": obj, "properties": {}}]
    return []


def _iter_positions(coords: Any):
    """Genera le posizioni foglia [x, y, ...] da una struttura coordinates."""
    if not isinstance(coords, (list, tuple)):
        return
    if coords and isinstance(coords[0], (int, float)):
        yield coords
        return
    for c in coords:
        yield from _iter_positions(c)


def profile_geojson(text: str) -> dict[str, Any]:
    """Diagnostica un GeoJSON; ritorna formato, CRS, geometrie, findings, punteggio."""
    findings: list[dict[str, Any]] = []
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return {
            "format": "GEOJSON", "tipo": None, "features": 0, "geometrie": {},
            "crs": None, "crs_wgs84": False, "bbox": None,
            "findings": [_finding("alto", "json_non_valido", "Il file non è JSON valido.")],
            "punteggio": 0,
        }

    if not isinstance(obj, dict):
        return {
            "format": "GEOJSON", "tipo": None, "features": 0, "geometrie": {},
            "crs": None, "crs_wgs84": False, "bbox": None,
            "findings": [_finding("alto", "non_geojson", "La radice non è un oggetto GeoJSON.")],
            "punteggio": 0,
        }

    tipo = obj.get("type")
    if tipo == "Topology":
        return {
            "format": "GEOJSON", "tipo": "Topology", "features": 0, "geometrie": {},
            "crs": None, "crs_wgs84": False, "bbox": None,
            "findings": [_finding(
                "alto", "topojson",
                "È un TopoJSON, non un GeoJSON: convertilo in GeoJSON per usarlo sulla mappa.",
            )],
            "punteggio": 0,
        }

    feats = _features(obj)
    if tipo not in ({"FeatureCollection", "Feature"} | _GEOM_TYPES):
        findings.append(_finding("alto", "tipo_sconosciuto", f"Tipo GeoJSON non riconosciuto: {tipo!r}."))
    if not feats:
        findings.append(_finding("alto", "nessuna_feature", "Nessuna geometria/feature nel file."))

    # ── tipi di geometria + validità + bbox ──
    geom_types: Counter[str] = Counter()
    n_empty = n_nonfinite = 0
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    sample_pos: list[float] | None = None

    def _scan_geom(g: Any) -> None:
        nonlocal n_empty, n_nonfinite, minx, miny, maxx, maxy, sample_pos
        if not isinstance(g, dict) or not g.get("type"):
            n_empty += 1
            return
        gt = g["type"]
        geom_types[gt] += 1
        if gt == "GeometryCollection":
            for sub in g.get("geometries") or []:
                _scan_geom(sub)
            return
        coords = g.get("coordinates")
        if not coords:
            n_empty += 1
            return
        for pos in _iter_positions(coords):
            if len(pos) < 2 or not all(isinstance(v, (int, float)) for v in pos[:2]):
                n_nonfinite += 1
                continue
            x, y = float(pos[0]), float(pos[1])
            if x != x or y != y:  # NaN
                n_nonfinite += 1
                continue
            if sample_pos is None:
                sample_pos = [x, y]
            minx, miny = min(minx, x), min(miny, y)
            maxx, maxy = max(maxx, x), max(maxy, y)

    for f in feats:
        _scan_geom(f.get("geometry"))

    bbox = [minx, miny, maxx, maxy] if sample_pos is not None else None

    # ── CRS: dichiarato → euristica ──
    declared = _epsg_from_crs(obj)
    is_lonlat = sample_pos is not None and abs(sample_pos[0]) <= 180 and abs(sample_pos[1]) <= 90

    if declared and declared not in _WGS84_NAMES:
        crs = declared
        crs_wgs84 = False
        findings.append(_finding(
            "alto", "crs_non_wgs84",
            f"CRS dichiarato {declared}, non WGS84: va riproiettato in WGS84 (EPSG:4326) per la mappa.",
        ))
    elif sample_pos is not None and not is_lonlat:
        crs = declared or "proiettato (non lon/lat)"
        crs_wgs84 = False
        findings.append(_finding(
            "alto", "coord_proiettate",
            "Le coordinate sono proiettate (in metri), non lon/lat: riproietta in WGS84 o non "
            "compariranno sulla mappa.",
        ))
    else:
        crs = "EPSG:4326 (WGS84)"
        crs_wgs84 = True
        if declared is None and sample_pos is not None:
            findings.append(_finding(
                "basso", "crs_non_dichiarato",
                "Nessun CRS dichiarato: si assume WGS84 (default GeoJSON RFC 7946), coerente con le coordinate.",
            ))
        # lon/lat fuori dai limiti del globo
        if bbox and (abs(bbox[0]) > 180 or abs(bbox[2]) > 180 or abs(bbox[1]) > 90 or abs(bbox[3]) > 90):
            findings.append(_finding("alto", "coord_fuori_range", "Alcune coordinate sono fuori dai limiti lon/lat."))

    # ── validità geometrie ──
    bad_types = [t for t in geom_types if t not in _GEOM_TYPES]
    if bad_types:
        findings.append(_finding("medio", "geometria_sconosciuta", f"Tipi di geometria non standard: {', '.join(bad_types)}."))
    if n_empty:
        findings.append(_finding("medio", "geometrie_vuote", f"{n_empty} feature senza geometria valida."))
    if n_nonfinite:
        findings.append(_finding("alto", "coord_non_valide", f"{n_nonfinite} coordinate non numeriche/non valide."))

    punteggio = max(0, 100 - sum(_PENALITA.get(f["livello"], 0) for f in findings))

    return {
        "format": "GEOJSON",
        "tipo": tipo,
        "features": len(feats),
        "geometrie": dict(geom_types),
        "crs": crs,
        "crs_wgs84": crs_wgs84,
        "bbox": [round(v, 6) for v in bbox] if bbox else None,
        "findings": findings,
        "punteggio": punteggio,
    }
