"""Seed pilota del modello territoriale: comune ed ente di Gioia del Colle.

Idempotente:
- `opendata.place` upsert per `istat_code` (ON CONFLICT) — geometria dal confine
  OSM/Nominatim (`polygon_geojson`), con fallback al centroide (Point) se il
  poligono non è disponibile, NULL se OSM è irraggiungibile;
- `opendata.entities` upsert per `name` (update-then-insert).

Geo: usa funzioni PostGIS (ST_GeomFromGeoJSON / ST_Point) → richiede Postgres.
Rieseguibile senza duplicati. Uso:

    opendata-territorio-seed                       # usa DATABASE_URL
    opendata-territorio-seed --no-geometry         # salta il fetch OSM (geom NULL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from opendata_core.osm.client import geocode_boundary

log = logging.getLogger("ingest.territory_seed")

# Pilota Gioia del Colle (Città metropolitana di Bari).
PILOT_ISTAT = "072021"
PILOT_PLACE_NAME = "Gioia del Colle"
PILOT_ENTITY_NAME = "Comune di Gioia del Colle"
PILOT_QUERY = "Gioia del Colle, Bari, Italia"


async def _resolve_geometry(query: str) -> tuple[str | None, tuple[float, float] | None]:
    """Ritorna (geojson_string | None, (lon, lat) | None) dal confine OSM."""
    try:
        hit = await geocode_boundary(query)
    except Exception as exc:  # noqa: BLE001 — OSM down/timeout: il seed continua senza geom
        log.warning("geocode_boundary fallito (%s): proseguo senza geometria", exc)
        return None, None
    if not hit:
        log.warning("Nessun match OSM per %r: geom NULL", query)
        return None, None
    geojson = hit.get("geojson")
    geojson_str = json.dumps(geojson) if geojson else None
    centroid = (hit["lon"], hit["lat"]) if hit.get("lat") and hit.get("lon") else None
    return geojson_str, centroid


def _geom_expr(geojson: str | None, centroid: tuple[float, float] | None) -> str:
    """Espressione SQL PostGIS per la colonna geom (o NULL)."""
    if geojson is not None:
        return "ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)"
    if centroid is not None:
        return "ST_SetSRID(ST_Point(:lon, :lat), 4326)"
    return "NULL"


async def seed(
    engine: AsyncEngine,
    *,
    fetch_geometry: bool = True,
    istat: str = PILOT_ISTAT,
    place_name: str = PILOT_PLACE_NAME,
    entity_name: str = PILOT_ENTITY_NAME,
    query: str = PILOT_QUERY,
    region: str | None = None,
) -> dict[str, Any]:
    """Esegue il seed idempotente; ritorna un riepilogo {place_id, entity_id, geom}.

    `region` (nome regione) è iniettato dal chiamante: derivato da `REGION`
    (`regioni.yaml`) in `main`, non più cablato a "Puglia". Il pilota di default
    resta Gioia del Colle ma è parametrizzabile per altre regioni.
    """
    geojson, centroid = (None, None)
    if fetch_geometry:
        geojson, centroid = await _resolve_geometry(query)

    geom_sql = _geom_expr(geojson, centroid)
    params: dict[str, Any] = {
        "istat": istat,
        "name": place_name,
        "type": "comune",
    }
    if geojson is not None:
        params["geojson"] = geojson
    elif centroid is not None:
        params["lon"], params["lat"] = centroid

    async with engine.begin() as conn:
        place_id = (
            await conn.execute(
                text(
                    f"""
                    INSERT INTO opendata.place (istat_code, name, type, geom)
                    VALUES (:istat, :name, :type, {geom_sql})
                    ON CONFLICT (istat_code) DO UPDATE
                      SET name = EXCLUDED.name, type = EXCLUDED.type, geom = EXCLUDED.geom
                    RETURNING id
                    """
                ),
                params,
            )
        ).scalar_one()

        # Ente: idempotente per nome (no unique su name → update-then-insert).
        ent = {"name": entity_name, "type": "comune", "region": region}
        entity_id = (
            await conn.execute(
                text(
                    "UPDATE opendata.entities SET type = :type, region = :region "
                    "WHERE name = :name RETURNING id"
                ),
                ent,
            )
        ).scalar_one_or_none()
        if entity_id is None:
            entity_id = (
                await conn.execute(
                    text(
                        "INSERT INTO opendata.entities (name, type, region) "
                        "VALUES (:name, :type, :region) RETURNING id"
                    ),
                    ent,
                )
            ).scalar_one()

    summary = {
        "place_id": int(place_id),
        "entity_id": int(entity_id),
        "geom": "polygon" if geojson else ("centroid" if centroid else "null"),
    }
    log.info("Seed pilota OK: %s", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-territorio-seed",
        description="Seed idempotente del pilota Gioia del Colle (place + entity).",
    )
    parser.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL"),
        help="DSN Postgres (default: env DATABASE_URL)",
    )
    parser.add_argument(
        "--no-geometry", action="store_true",
        help="salta il fetch del confine OSM (geom resta NULL)",
    )
    parser.add_argument("--istat", default=PILOT_ISTAT, help="codice ISTAT del comune pilota")
    parser.add_argument("--place-name", default=PILOT_PLACE_NAME, help="nome del comune")
    parser.add_argument("--entity-name", default=PILOT_ENTITY_NAME, help="nome dell'ente")
    parser.add_argument("--query", default=PILOT_QUERY, help="query di geocoding OSM")
    parser.add_argument(
        "--region", default=None,
        help="nome regione dell'ente (default: derivato da REGION, fallback Puglia)",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("serve --database-url o la variabile DATABASE_URL")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stderr,
    )

    from ..config import get_settings, region_name
    from ..db.session import create_database

    # Regione dell'ente: --region esplicito, altrimenti derivata da REGION
    # (regioni.yaml); fallback storico "Puglia" quando nulla è configurato.
    region = args.region or region_name(get_settings()) or "Puglia"

    async def _run() -> None:
        db = create_database(args.database_url)
        try:
            result = await seed(
                db.engine, fetch_geometry=not args.no_geometry,
                istat=args.istat, place_name=args.place_name,
                entity_name=args.entity_name, query=args.query, region=region,
            )
            print(f"OK: place_id={result['place_id']} entity_id={result['entity_id']} "
                  f"geom={result['geom']}")
        finally:
            await db.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
