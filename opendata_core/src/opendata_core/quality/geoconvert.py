"""Convertitore tabella → GeoJSON (Punto 03 #51, "convertitori 1-click").

`csv_to_geojson(text)` / `json_to_geojson(text)` trasformano una tabella con
colonne di coordinate (CSV o array JSON di record) in un GeoJSON di punti
mappabile: rileva le colonne lat/lon, valida i range WGS84, normalizza i decimali
all'italiana e mette le altre colonne come `properties`. Deterministico, senza
dipendenze. Completa il geo doctor: lì si *riproietta* un GeoJSON, qui se ne
*crea* uno da un dato piatto.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from .profile import _detect_delimiter, _is_empty

# nomi colonna che indicano latitudine / longitudine (match esatto, case-insensitive)
_LAT_NAMES = {
    "lat", "latitude", "latitudine", "y", "ycoord", "y_coord", "coord_y",
    "wgs84_lat", "lat_wgs84", "gps_lat",
}
_LON_NAMES = {
    "lon", "lng", "long", "longitude", "longitudine", "x", "xcoord", "x_coord",
    "coord_x", "wgs84_lon", "lon_wgs84", "gps_lon", "lng_wgs84",
}

_RE_NORM = re.compile(r"[^0-9a-z]+")


def _norm(name: str) -> str:
    return _RE_NORM.sub("", name.strip().lower())


def _parse_coord(v: str) -> float | None:
    """Numero da una cella coordinata, tollerando la virgola decimale italiana."""
    s = v.strip()
    if not s:
        return None
    # 44,49 → 44.49 ; ma lascia stare 44.49 (punto già decimale)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _pick_coord_fields(
    headers: list[str], lat_field: str | None, lon_field: str | None
) -> tuple[str | None, str | None]:
    """Sceglie le colonne lat/lon: override espliciti o auto-rilevamento per nome."""
    if lat_field and lon_field:
        return lat_field, lon_field
    norm_map = {_norm(h): h for h in headers}
    lat = next((norm_map[n] for n in norm_map if n in _LAT_NAMES), None)
    lon = next((norm_map[n] for n in norm_map if n in _LON_NAMES), None)
    return lat_field or lat, lon_field or lon


def _build(
    records: list[dict[str, str]],
    headers: list[str],
    lat_field: str | None,
    lon_field: str | None,
) -> dict[str, Any]:
    lat_f, lon_f = _pick_coord_fields(headers, lat_field, lon_field)
    if not lat_f or not lon_f:
        return {
            "ok": False,
            "error": "Colonne di coordinate non trovate. Indica quali colonne contengono "
                     "latitudine e longitudine.",
            "candidate_columns": headers,
            "geojson": None,
            "n_features": 0,
            "n_skipped": 0,
        }

    features: list[dict[str, Any]] = []
    skipped = 0
    out_of_range = 0
    for rec in records:
        lat = _parse_coord(rec.get(lat_f, ""))
        lon = _parse_coord(rec.get(lon_f, ""))
        if lat is None or lon is None:
            skipped += 1
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            out_of_range += 1
            skipped += 1
            continue
        props = {
            k: v for k, v in rec.items()
            if k not in (lat_f, lon_f) and not _is_empty(v)
        }
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},  # GeoJSON: [lon, lat]
            "properties": props,
        })

    warnings: list[str] = []
    if skipped:
        warnings.append(f"{skipped} righe saltate per coordinate mancanti o non valide.")
    if out_of_range:
        warnings.append(
            f"{out_of_range} righe con coordinate fuori dai limiti WGS84: forse il file usa "
            "coordinate proiettate (metri) — in tal caso vanno prima riproiettate."
        )
    return {
        "ok": True,
        "error": None,
        "lat_field": lat_f,
        "lon_field": lon_f,
        "geojson": {"type": "FeatureCollection", "features": features},
        "n_features": len(features),
        "n_skipped": skipped,
        "warnings": warnings,
    }


def csv_to_geojson(
    text: str, *, lat_field: str | None = None, lon_field: str | None = None
) -> dict[str, Any]:
    """Converte un CSV con colonne di coordinate in un GeoJSON di punti."""
    if not text.strip():
        return {"ok": False, "error": "Il file è vuoto.", "geojson": None,
                "n_features": 0, "n_skipped": 0, "candidate_columns": []}
    text = text.lstrip("﻿")
    delimiter = _detect_delimiter("\n".join(text.splitlines()[:50]))
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {"ok": False, "error": "Nessuna riga leggibile.", "geojson": None,
                "n_features": 0, "n_skipped": 0, "candidate_columns": []}
    headers = [h.strip() for h in rows[0]]
    records = [
        {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
        for r in rows[1:]
    ]
    return _build(records, headers, lat_field, lon_field)


def json_to_geojson(
    text: str, *, lat_field: str | None = None, lon_field: str | None = None
) -> dict[str, Any]:
    """Converte un array JSON di record (o un GeoJSON già pronto) in GeoJSON di punti.

    Se l'input è già un FeatureCollection lo restituisce invariato.
    """
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"ok": False, "error": "JSON non valido.", "geojson": None,
                "n_features": 0, "n_skipped": 0, "candidate_columns": []}

    if isinstance(obj, dict) and obj.get("type") == "FeatureCollection":
        feats = obj.get("features") or []
        return {"ok": True, "error": None, "lat_field": None, "lon_field": None,
                "geojson": obj, "n_features": len(feats), "n_skipped": 0,
                "warnings": ["L'input è già un GeoJSON: restituito invariato."]}

    # array di record, oppure {"...": [record, ...]}: prendi la prima lista di dict
    if isinstance(obj, dict):
        obj = next((v for v in obj.values() if isinstance(v, list)), None)
    if not isinstance(obj, list) or not obj or not isinstance(obj[0], dict):
        return {"ok": False, "error": "Serve un array JSON di record (oggetti) con coordinate.",
                "geojson": None, "n_features": 0, "n_skipped": 0, "candidate_columns": []}

    headers: list[str] = []
    for rec in obj:
        for k in rec:
            if k not in headers:
                headers.append(k)
    records = [{k: ("" if rec.get(k) is None else str(rec.get(k))) for k in headers} for rec in obj]
    return _build(records, headers, lat_field, lon_field)
