"""Test degli helper puri del seed territoriale (no DB, no rete).

L'idempotenza a livello DB è verificata manualmente su Postgres (place/entity
upsert): qui si coprono la scelta dell'espressione geom e la risoluzione della
geometria con `geocode_boundary` mockato.
"""

from __future__ import annotations

import json

from opendata_backend.ingest import territory_seed as ts


def test_geom_expr_prefers_geojson() -> None:
    assert "ST_GeomFromGeoJSON" in ts._geom_expr('{"type":"Polygon"}', (16.9, 40.8))


def test_geom_expr_falls_back_to_point() -> None:
    expr = ts._geom_expr(None, (16.9, 40.8))
    assert "ST_Point" in expr


def test_geom_expr_null_when_no_geometry() -> None:
    assert ts._geom_expr(None, None) == "NULL"


async def test_resolve_geometry_returns_geojson_and_centroid(monkeypatch) -> None:
    async def fake_geocode(query: str, **_: object) -> dict:
        return {
            "name": "Gioia del Colle",
            "lat": 40.7986,
            "lon": 16.9268,
            "geojson": {"type": "Polygon", "coordinates": [[[16.9, 40.8], [17.0, 40.8]]]},
        }

    monkeypatch.setattr(ts, "geocode_boundary", fake_geocode)
    geojson, centroid = await ts._resolve_geometry("Gioia del Colle")
    assert json.loads(geojson)["type"] == "Polygon"
    assert centroid == (16.9268, 40.7986)


async def test_resolve_geometry_handles_no_match(monkeypatch) -> None:
    async def fake_none(query: str, **_: object) -> None:
        return None

    monkeypatch.setattr(ts, "geocode_boundary", fake_none)
    assert await ts._resolve_geometry("ignoto") == (None, None)


async def test_resolve_geometry_survives_osm_error(monkeypatch) -> None:
    async def boom(query: str, **_: object) -> dict:
        raise RuntimeError("OSM down")

    monkeypatch.setattr(ts, "geocode_boundary", boom)
    assert await ts._resolve_geometry("x") == (None, None)


def test_pilot_constants() -> None:
    assert ts.PILOT_ISTAT == "072021"
    assert ts.PILOT_ENTITY_NAME == "Comune di Gioia del Colle"
