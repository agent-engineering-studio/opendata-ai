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
