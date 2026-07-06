"""Da GeoJSON a schema geografico — DDL PostGIS + comando GeoPackage (#51, prima voce).

`infer_geo_schema(text)` completa `schema.py` (relazionale, CSV) sul lato
geografico: dal profilo di un GeoJSON deduce il tipo di geometria dominante e
lo schema delle proprietà (tipo SQL per chiave), e genera il `CREATE TABLE`
PostGIS pronto (colonna `geom` tipizzata + indice GIST). Per il GeoPackage non
generiamo il binario `.gpkg` (richiederebbe GDAL/fiona, dipendenza pesante
volutamente fuori da `opendata_core` — vedi #101): forniamo il comando
`ogr2ogr` equivalente, sullo stesso principio del pacchetto di pubblicazione
(`package.py`) che dà istruzioni testuali invece di chiamare servizi esterni.
Deterministico, senza dipendenze.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .geo import _features
from .profile import _date_format
from .schema import _sanitize

# tipo Python nativo di un valore JSON → tipo SQL
_PY_TYPE_SQL = {bool: "BOOLEAN", int: "BIGINT", float: "DOUBLE PRECISION"}
_MAX_PROPERTIES_SCANNED_FEATURES = 500


def _sql_type_for_values(valori: list[Any]) -> str:
    """Tipo SQL da un campione di valori di una proprietà (non-null)."""
    if not valori:
        return "TEXT"
    tipi = Counter(type(v) for v in valori)
    dominante, n = tipi.most_common(1)[0]
    if dominante is bool:
        return "BOOLEAN"
    if dominante in (int, float) and n == len(valori):
        return _PY_TYPE_SQL.get(dominante, "DOUBLE PRECISION")
    if dominante is str:
        stringhe = [v for v in valori if isinstance(v, str)]
        if stringhe and all(_date_format(v) for v in stringhe):
            return "DATE"
        return "TEXT"
    return "TEXT"


def infer_geo_schema(text: str, *, table_name: str = "dataset") -> dict[str, Any]:
    """Schema geografico (PostGIS DDL + comando GeoPackage) da un GeoJSON.

    Args:
        text: contenuto GeoJSON.
        table_name: nome tabella desiderato (sanificato come identificatore SQL).

    Returns:
        {"tabella", "geometria", "colonne", "ddl_postgis", "comando_geopackage", "note"}.
    """
    note: list[str] = []
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return {
            "tabella": None, "geometria": None, "colonne": [],
            "ddl_postgis": None, "comando_geopackage": None,
            "note": ["Il file non è JSON valido."],
        }
    if not isinstance(obj, dict):
        return {
            "tabella": None, "geometria": None, "colonne": [],
            "ddl_postgis": None, "comando_geopackage": None,
            "note": ["La radice non è un oggetto GeoJSON."],
        }

    feats = _features(obj)
    if not feats:
        return {
            "tabella": None, "geometria": None, "colonne": [],
            "ddl_postgis": None, "comando_geopackage": None,
            "note": ["Nessuna geometria/feature nel file."],
        }

    geom_types: Counter[str] = Counter(
        f["geometry"]["type"] for f in feats
        if isinstance(f.get("geometry"), dict) and f["geometry"].get("type")
    )
    if not geom_types:
        return {
            "tabella": None, "geometria": None, "colonne": [],
            "ddl_postgis": None, "comando_geopackage": None,
            "note": ["Nessuna geometria valida da cui dedurre lo schema."],
        }
    geometria, _ = geom_types.most_common(1)[0]
    if len(geom_types) > 1:
        note.append(
            f"Geometrie miste ({', '.join(sorted(geom_types))}): la colonna «geom» usa il tipo "
            f"generico GEOMETRY invece di {geometria} per accettarle tutte."
        )
    tipo_postgis = geometria if len(geom_types) == 1 else "GEOMETRY"

    # ── proprietà: unione delle chiavi, tipo dal campione di valori non-null ──
    campione = feats[:_MAX_PROPERTIES_SCANNED_FEATURES]
    ordine: list[str] = []
    valori_per_chiave: dict[str, list[Any]] = {}
    for f in campione:
        props = f.get("properties")
        if not isinstance(props, dict):
            continue
        for k, v in props.items():
            if k not in valori_per_chiave:
                valori_per_chiave[k] = []
                ordine.append(k)
            if v is not None:
                valori_per_chiave[k].append(v)
    if len(feats) > _MAX_PROPERTIES_SCANNED_FEATURES:
        note.append(f"Proprietà dedotte da un campione delle prime {_MAX_PROPERTIES_SCANNED_FEATURES} feature.")

    table = _sanitize(table_name, set(), 0) or "dataset"
    used: set[str] = set()
    colonne: list[dict[str, Any]] = []
    for idx, chiave in enumerate(ordine, start=1):
        col_name = _sanitize(chiave, used, idx)
        colonne.append({
            "name": col_name,
            "original": chiave,
            "sql_type": _sql_type_for_values(valori_per_chiave[chiave]),
            "nullable": len(valori_per_chiave[chiave]) < len(campione),
        })

    corpo = ["    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"]
    corpo += [f"    {c['name']} {c['sql_type']}" + ("" if c["nullable"] else " NOT NULL") for c in colonne]
    corpo.append(f"    geom GEOMETRY({tipo_postgis}, 4326) NOT NULL")
    ddl_postgis = (
        f"CREATE TABLE {table} (\n" + ",\n".join(corpo) + "\n);\n\n"
        f"CREATE INDEX idx_{table}_geom ON {table} USING GIST (geom);"
    )
    comando_geopackage = f"ogr2ogr -f GPKG {table}.gpkg input.geojson"

    return {
        "tabella": table,
        "geometria": geometria,
        "colonne": colonne,
        "ddl_postgis": ddl_postgis,
        "comando_geopackage": comando_geopackage,
        "note": note,
    }
