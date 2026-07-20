"""Convertitore Shapefile.zip → GeoJSON (WGS84) server-side (#157, follow-up #101).

Il Quality Lab UI converte gli shapefile client-side (jszip+shpjs+proj4); questo
motore porta la STESSA capability lato server per i consumatori REST/A2A.
Deterministico: legge `.shp`+`.dbf` dall'archivio zip, riproietta le geometrie
in **WGS84 (EPSG:4326)** leggendo il CRS sorgente dal `.prj`, ed emette una
`FeatureCollection` GeoJSON.

Dipendenze opzionali importate pigramente (extra `converters`): **pyshp**
(lettura shapefile, puro Python) e **pyproj** (riproiezione). **Niente
fiona/GDAL** (peggiorano la build arm64 — vedi CLAUDE.md). Senza le librerie la
funzione NON solleva: `ok=False` con messaggio chiaro (endpoint → 501).

Guardia **zip-bomb**: rifiuta archivi la cui dimensione decompressa totale supera
`MAX_UNCOMPRESSED` o con troppe entry, prima di estrarre (`ok=False`,
`zipbomb=True` → l'endpoint mappa su 413).
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

#: Cap difensivi sull'archivio (prima dell'estrazione).
MAX_UNCOMPRESSED = 200 * 1024 * 1024  # 200 MB decompressi totali
MAX_ENTRIES = 200
MAX_FEATURES = 200_000


def _empty(error: str | None = None, *, zipbomb: bool = False) -> dict[str, Any]:
    return {
        "ok": False, "content": None, "geojson": None, "feature_count": 0,
        "source_crs": None, "warnings": [], "zipbomb": zipbomb, "error": error,
    }


def _reproject_coords(coords: Any, transform: Any) -> Any:
    """Riproietta ricorsivamente una struttura di coordinate GeoJSON.

    Una coordinata è una lista [x, y(, z…)] con x,y numerici; tutto il resto è
    una lista annidata (anelli, poligoni, multi-geometrie) da percorrere.
    """
    if (
        isinstance(coords, (list, tuple)) and len(coords) >= 2
        and all(isinstance(c, (int, float)) for c in coords[:2])
    ):
        x, y = transform(coords[0], coords[1])
        return [x, y, *coords[2:]]
    return [_reproject_coords(c, transform) for c in coords]


def shapefile_to_geojson(data: bytes) -> dict[str, Any]:
    """Converte uno Shapefile zippato (bytes) in GeoJSON WGS84.

    Ritorna `geojson` (dict FeatureCollection) + `content` (stringa JSON),
    `feature_count`, `source_crs` e `warnings`. `ok=False` con `error` quando le
    dipendenze mancano, l'archivio è invalido/zip-bomb, o manca il `.shp`.
    """
    if not data:
        return _empty("Il file è vuoto.")

    try:
        import json

        import pyproj
        import shapefile  # pyshp
    except ImportError:
        return _empty(
            "Conversione Shapefile non disponibile su questo server: mancano le "
            "dipendenze opzionali pyshp/pyproj (extra 'converters')."
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return _empty("Archivio zip non valido.")

    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            return _empty(f"Troppe entry nell'archivio (> {MAX_ENTRIES}).", zipbomb=True)
        total = sum(i.file_size for i in infos)
        if total > MAX_UNCOMPRESSED:
            return _empty(
                f"Archivio troppo grande da decomprimere (> {MAX_UNCOMPRESSED // (1024 * 1024)} MB).",
                zipbomb=True,
            )

        def _find(ext: str) -> str | None:
            # primo file con l'estensione, ignorando cartelle e file nascosti __MACOSX
            for i in infos:
                name = i.filename
                if name.lower().endswith(ext) and "__MACOSX" not in name:
                    return name
            return None

        shp_name = _find(".shp")
        if not shp_name:
            return _empty("Nessun file .shp trovato nell'archivio.")
        dbf_name = _find(".dbf")
        shx_name = _find(".shx")
        prj_name = _find(".prj")

        warnings: list[str] = []
        try:
            shp_fp = io.BytesIO(zf.read(shp_name))
            dbf_fp = io.BytesIO(zf.read(dbf_name)) if dbf_name else None
            shx_fp = io.BytesIO(zf.read(shx_name)) if shx_name else None
            reader_kwargs: dict[str, Any] = {"shp": shp_fp}
            if dbf_fp is not None:
                reader_kwargs["dbf"] = dbf_fp
            if shx_fp is not None:
                reader_kwargs["shx"] = shx_fp
            reader = shapefile.Reader(**reader_kwargs)
        except Exception as exc:  # noqa: BLE001 — shapefile illeggibile → messaggio chiaro
            return _empty(f"Shapefile non leggibile: {exc}")

        if len(reader) > MAX_FEATURES:
            return _empty(f"Troppe geometrie (> {MAX_FEATURES}).", zipbomb=True)

        # CRS sorgente dal .prj (WKT); default WGS84 con warning se assente.
        source_crs = "EPSG:4326 (assunto: .prj mancante)"
        transformer = None
        if prj_name:
            try:
                prj_wkt = zf.read(prj_name).decode("utf-8", errors="replace")
                src = pyproj.CRS.from_wkt(prj_wkt)
                source_crs = src.name
                if src.to_epsg() != 4326 and not src.equals(pyproj.CRS.from_epsg(4326)):
                    transformer = pyproj.Transformer.from_crs(
                        src, pyproj.CRS.from_epsg(4326), always_xy=True
                    ).transform
            except Exception as exc:  # noqa: BLE001 — .prj illeggibile → nessuna riproiezione, warning
                warnings.append(f".prj non interpretabile ({exc}): coordinate lasciate invariate.")
        else:
            warnings.append(".prj mancante: si assume già WGS84, nessuna riproiezione.")

        features = []
        try:
            for sr in reader.shapeRecords():
                geo = sr.__geo_interface__  # {'type':'Feature','geometry':...,'properties':...}
                geom = geo.get("geometry")
                if geom and transformer is not None and geom.get("coordinates") is not None:
                    geom = {**geom, "coordinates": _reproject_coords(geom["coordinates"], transformer)}
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": geo.get("properties") or {},
                })
        except Exception as exc:  # noqa: BLE001 — record corrotto → fail-safe
            return _empty(f"Errore leggendo le geometrie: {exc}")

    fc = {"type": "FeatureCollection", "features": features}
    return {
        "ok": True,
        "error": None,
        "geojson": fc,
        "content": json.dumps(fc, ensure_ascii=False),
        "feature_count": len(features),
        "source_crs": source_crs,
        "warnings": warnings,
        "zipbomb": False,
    }
