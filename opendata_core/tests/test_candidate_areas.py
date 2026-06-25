"""`overpass_candidate_areas` — parsing/area/sort dei vuoti urbani candidati.

Overpass è mockato (l'endpoint reale è spesso bloccato in egress): qui si verifica
solo la trasformazione elementi→candidati (geometria, area shoelace, dedup, ordine).
"""

from __future__ import annotations

import pytest

from opendata_core.osm import client


@pytest.mark.asyncio
async def test_candidate_areas_parsing(monkeypatch) -> None:
    fake = [
        {  # brownfield ~111×84 m ≈ 9.300 m² → tenuto
            "type": "way", "id": 10,
            "tags": {"landuse": "brownfield", "name": "Ex Fornace"},
            "geometry": [
                {"lat": 40.800, "lon": 16.920}, {"lat": 40.801, "lon": 16.920},
                {"lat": 40.801, "lon": 16.921}, {"lat": 40.800, "lon": 16.921},
            ],
        },
        {  # micro-triangolo ~11 m → scartato (<300 m²)
            "type": "way", "id": 11, "tags": {"amenity": "parking"},
            "geometry": [
                {"lat": 40.80, "lon": 16.92}, {"lat": 40.8001, "lon": 16.92},
                {"lat": 40.8001, "lon": 16.9201},
            ],
        },
        {"type": "way", "id": 12, "tags": {"landuse": "brownfield"},
         "geometry": [{"lat": 40.8, "lon": 16.92}]},  # <3 punti → scartato
    ]

    async def _fake_post(*a, **k):
        return fake

    monkeypatch.setattr(client, "overpass_post", _fake_post)
    res = await client.overpass_candidate_areas(bbox=(40.79, 16.91, 40.81, 16.93), limit=5)
    ids = {r["osm_id"] for r in res}
    assert 10 in ids and 12 not in ids and 11 not in ids  # filtri area/geometria
    top = next(r for r in res if r["osm_id"] == 10)
    assert top["kind"] == "brownfield" and top["name"] == "Ex Fornace"
    assert top["area_mq"] > 300 and top["url"].endswith("/way/10")


# ── Clip al confine comunale (point-in-polygon) ─────────────────────


def test_point_in_geojson_polygon_and_hole() -> None:
    # quadrato esterno [16.90..16.94]×[40.79..40.81] con foro centrale
    poly = {
        "type": "Polygon",
        "coordinates": [
            [[16.90, 40.79], [16.94, 40.79], [16.94, 40.81], [16.90, 40.81], [16.90, 40.79]],
            [[16.915, 40.799], [16.925, 40.799], [16.925, 40.801], [16.915, 40.801], [16.915, 40.799]],
        ],
    }
    assert client.point_in_geojson(40.80, 16.905, poly) is True   # dentro l'esterno
    assert client.point_in_geojson(40.80, 16.920, poly) is False  # nel foro → fuori
    assert client.point_in_geojson(40.80, 16.950, poly) is False  # oltre l'esterno
    assert client.point_in_geojson(40.80, 16.92, None) is False    # niente poligono → fuori


def test_bbox_from_geojson_multipolygon() -> None:
    mp = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[16.90, 40.79], [16.92, 40.79], [16.92, 40.80], [16.90, 40.79]]],
            [[[16.95, 40.81], [16.97, 40.81], [16.97, 40.82], [16.95, 40.81]]],
        ],
    }
    assert client.bbox_from_geojson(mp) == (40.79, 16.90, 40.82, 16.97)  # (s, w, n, e)
    assert client.bbox_from_geojson(None) is None
    assert client.bbox_from_geojson({"type": "Point", "coordinates": [16.9, 40.8]}) is None


@pytest.mark.asyncio
async def test_candidate_areas_boundary_clip(monkeypatch) -> None:
    """Il candidato fuori dal confine comunale è scartato anche se cade nel bbox."""
    fake = [
        {  # dentro il confine
            "type": "way", "id": 20, "tags": {"landuse": "brownfield"},
            "geometry": [
                {"lat": 40.800, "lon": 16.920}, {"lat": 40.801, "lon": 16.920},
                {"lat": 40.801, "lon": 16.921}, {"lat": 40.800, "lon": 16.921},
            ],
        },
        {  # nel bbox ma fuori dal confine (comune vicino)
            "type": "way", "id": 21, "tags": {"landuse": "brownfield"},
            "geometry": [
                {"lat": 40.700, "lon": 16.820}, {"lat": 40.701, "lon": 16.820},
                {"lat": 40.701, "lon": 16.821}, {"lat": 40.700, "lon": 16.821},
            ],
        },
    ]

    async def _fake_post(*a, **k):
        return fake

    boundary = {
        "type": "Polygon",
        "coordinates": [
            [[16.91, 40.79], [16.93, 40.79], [16.93, 40.81], [16.91, 40.81], [16.91, 40.79]],
        ],
    }
    monkeypatch.setattr(client, "overpass_post", _fake_post)
    res = await client.overpass_candidate_areas(
        bbox=(40.69, 16.78, 40.82, 16.94), boundary=boundary, limit=5
    )
    ids = {r["osm_id"] for r in res}
    assert ids == {20}  # 21 scartato (centroide fuori confine)
