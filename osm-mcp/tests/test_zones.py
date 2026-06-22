"""Tests for the zone-selection layer (opendata_core.osm.zones + geojson assembly).

Geometry fixtures are REAL Overpass `out geom` responses captured during the
spec-06 discovery (Zona Industriale di Bari relation; Barletta closed ways).
Network calls are monkeypatched — no live Overpass/Nominatim in the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opendata_core.osm import zones
from opendata_core.osm.geojson import feature_area_m2, overpass_to_features

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _clear_cache():
    zones.cache_clear()
    yield
    zones.cache_clear()


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())["elements"]


# ───────────────────── overpass_to_features (fixture reali) ─────────────────


def test_real_relation_becomes_polygon() -> None:
    feats = overpass_to_features(_load("fixture_relation_industrial.json"))
    assert len(feats) == 1
    f = feats[0]
    assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert f["properties"]["name"] == "Zona Industriale di Bari"
    assert f["properties"]["osm_type"] == "relation"
    assert feature_area_m2(f) > 100_000  # la ZI di Bari è enorme


def test_real_closed_ways_become_polygons() -> None:
    feats = overpass_to_features(_load("fixture_ways_industrial.json"))
    assert len(feats) == 3
    assert all(f["geometry"]["type"] == "Polygon" for f in feats)
    names = {f["properties"].get("name") for f in feats}
    assert "Centro Industriale INCA'" in names


def test_relation_with_inner_ring_and_split_outer() -> None:
    """Outer spezzato in 2 way da ricucire + un inner (buco)."""
    elements = [
        {
            "type": "relation",
            "id": 99,
            "tags": {"landuse": "industrial", "name": "Test MP"},
            "members": [
                {"type": "way", "role": "outer", "geometry": [
                    {"lat": 0.0, "lon": 0.0}, {"lat": 0.0, "lon": 1.0}, {"lat": 1.0, "lon": 1.0},
                ]},
                {"type": "way", "role": "outer", "geometry": [
                    {"lat": 1.0, "lon": 1.0}, {"lat": 1.0, "lon": 0.0}, {"lat": 0.0, "lon": 0.0},
                ]},
                {"type": "way", "role": "inner", "geometry": [
                    {"lat": 0.4, "lon": 0.4}, {"lat": 0.4, "lon": 0.6},
                    {"lat": 0.6, "lon": 0.6}, {"lat": 0.6, "lon": 0.4}, {"lat": 0.4, "lon": 0.4},
                ]},
            ],
        }
    ]
    feats = overpass_to_features(elements)
    assert len(feats) == 1
    geom = feats[0]["geometry"]
    assert geom["type"] == "Polygon"
    assert len(geom["coordinates"]) == 2  # outer + inner


def test_open_way_is_skipped_and_node_becomes_point() -> None:
    elements = [
        {"type": "way", "id": 1, "tags": {}, "geometry": [
            {"lat": 0, "lon": 0}, {"lat": 0, "lon": 1},
        ]},
        {"type": "node", "id": 2, "lat": 41.1, "lon": 16.8, "tags": {"place": "quarter"}},
    ]
    feats = overpass_to_features(elements)
    assert len(feats) == 1
    assert feats[0]["geometry"] == {"type": "Point", "coordinates": [16.8, 41.1]}


# ───────────────────────────── list_zones ───────────────────────────────────


def _candidate_elements() -> list[dict]:
    def square(idx: int, size: float, name: str | None) -> dict:
        pts = [
            {"lat": 0.0, "lon": idx * 2.0},
            {"lat": 0.0, "lon": idx * 2.0 + size},
            {"lat": size, "lon": idx * 2.0 + size},
            {"lat": size, "lon": idx * 2.0},
            {"lat": 0.0, "lon": idx * 2.0},
        ]
        tags = {"landuse": "industrial"}
        if name:
            tags["name"] = name
        return {"type": "way", "id": 100 + idx, "tags": tags, "geometry": pts}

    return [
        square(0, 0.010, None),                # anonima, grande
        square(1, 0.001, "Zona PIP Piccola"),  # nominata, piccola
        square(2, 0.005, "Zona ASI Grande"),   # nominata, grande
    ]


async def test_list_zones_sorts_named_first_then_area(monkeypatch) -> None:
    async def fake_overpass(query: str, **kw):
        assert 'ref:ISTAT"="072006"' in query
        return _candidate_elements()

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    out = await zones.list_zones("072006", "industriale")
    names = [c["name"] for c in out["candidates"]]
    assert names == ["Zona ASI Grande", "Zona PIP Piccola", None]
    assert out["fallback_level"] == 1
    first = out["candidates"][0]
    assert first["osm_url"].startswith("https://www.openstreetmap.org/way/")
    assert first["centroid"] and first["bbox"] and first["area_m2"] > 0
    assert first["geometry"]["type"] == "Polygon"


async def test_list_zones_invalid_tipo_is_actionable() -> None:
    with pytest.raises(ValueError, match="industriale"):
        await zones.list_zones("072006", "balneare")


async def test_list_zones_quartieri_accepts_place_nodes(monkeypatch) -> None:
    """Tipo generico 'quartieri' (lente Commercio): nomina aree place=*."""
    assert "quartieri" in zones.ZONA_TIPI

    async def fake_overpass(query: str, **kw):
        return [
            {"type": "node", "id": 5, "lat": 40.80, "lon": 16.92,
             "tags": {"place": "neighbourhood", "name": "Quartiere Sud"}},
        ]

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    out = await zones.list_zones("072021", "quartieri")
    assert [c["name"] for c in out["candidates"]] == ["Quartiere Sud"]
    assert out["candidates"][0]["zona_tipo"] == "quartieri"


async def test_list_zones_fallback_to_nominatim_filters_classes(monkeypatch) -> None:
    async def fake_overpass(query: str, **kw):
        return []

    async def fake_geocode(q: str, limit: int = 5):
        assert "centro storico" in q and "Barletta" in q
        return [
            # Discovery: il B&B va scartato (class non territoriale).
            {"class": "tourism", "type": "guest_house", "osm_type": "node", "osm_id": 1,
             "lat": "41.3", "lon": "16.2", "display_name": "Al Centro Storico, Barletta"},
            {"class": "place", "type": "quarter", "osm_type": "node", "osm_id": 2,
             "lat": "41.31", "lon": "16.28", "display_name": "Centro Storico, Barletta",
             "boundingbox": ["41.30", "41.32", "16.27", "16.29"]},
        ]

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    monkeypatch.setattr(zones, "geocode", fake_geocode)
    out = await zones.list_zones("110002", "centro_storico", comune_nome="Barletta")
    assert out["fallback_level"] == 2
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["name"] == "Centro Storico"


async def test_list_zones_degrades_to_level_3(monkeypatch) -> None:
    async def fake_overpass(query: str, **kw):
        return []

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    out = await zones.list_zones("110002", "portuale")  # senza comune_nome
    assert out["fallback_level"] == 3
    assert out["candidates"] == []


async def test_lookup_comune_exact_match_first(monkeypatch) -> None:
    async def fake_overpass(query: str, **kw):
        # L'autocomplete usa il profilo snappy (timeout corto).
        assert kw.get("timeout") == zones._SNAPPY_TIMEOUT
        assert '"name"~"^Bari",i' in query
        return [
            {"type": "relation", "id": 2, "tags": {"name": "Bari Sardo", "ref:ISTAT": "091009"}},
            {"type": "relation", "id": 1, "tags": {"name": "Bari", "ref:ISTAT": "072006"}},
        ]

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    out = await zones.lookup_comune("Bari")
    assert out[0]["nome"] == "Bari" and out[0]["ref_istat"] == "072006"
    assert out[0]["cod_provincia"] == "072"
    assert out[1]["nome"] == "Bari Sardo"


# ───────────────────────────── MCP tools ────────────────────────────────────


async def test_mcp_list_zones_strips_geometry(monkeypatch) -> None:
    from osm_mcp import tools as mcp_tools

    async def fake_overpass(query: str, **kw):
        return _candidate_elements()

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    raw = await mcp_tools.list_zones("072006", "industriale")
    payload = json.loads(raw)
    assert payload["count"] == 3
    assert payload["fallback_level"] == 1
    assert all("geometry" not in c for c in payload["candidates"])
    assert "ODbL" in payload["sources"][0]["licenza"]


async def test_mcp_get_zone_returns_feature(monkeypatch) -> None:
    from osm_mcp import tools as mcp_tools

    async def fake_overpass(query: str, **kw):
        assert "way(101)" in query
        return _candidate_elements()[1:2]

    monkeypatch.setattr(zones, "_overpass", fake_overpass)
    raw = await mcp_tools.get_zone("way", "way/101")
    payload = json.loads(raw)
    assert payload["feature"]["geometry"]["type"] == "Polygon"
    assert payload["name"] == "Zona PIP Piccola"
    assert payload["source_url"].endswith("/way/101")


# ───────────────────── overpass_post: rotazione mirror ──────────────────────


async def test_overpass_post_rotates_to_mirror_on_429(httpx_mock) -> None:
    """Visto live su explore_area: 429 sul primario → il mirror risponde."""
    from opendata_core.osm import client as osm_client

    endpoints = osm_client.overpass_endpoints()
    assert len(endpoints) >= 2, "serve almeno un mirror di fallback"
    httpx_mock.add_response(url=endpoints[0], status_code=429)
    httpx_mock.add_response(url=endpoints[1], json={"elements": [{"type": "node", "id": 1}]})

    elements = await osm_client.overpass_post("[out:json];node(1);out;", backoff_base=0.01)
    assert elements == [{"type": "node", "id": 1}]


async def test_overpass_post_rotates_past_dead_mirror_then_succeeds(httpx_mock) -> None:
    """Mirror bloccato in egress (errore di trasporto) → si ruota SUBITO al
    successivo senza ritentare l'host morto né dormire."""
    import httpx

    from opendata_core.osm import client as osm_client

    endpoints = osm_client.overpass_endpoints()
    assert len(endpoints) >= 2
    httpx_mock.add_exception(httpx.ConnectError("egress blocked"), url=endpoints[0])
    httpx_mock.add_response(url=endpoints[1], json={"elements": [{"type": "node", "id": 7}]})

    elements = await osm_client.overpass_post("[out:json];node(7);out;")
    assert elements == [{"type": "node", "id": 7}]


async def test_overpass_post_raises_when_all_mirrors_dead(httpx_mock) -> None:
    """Tutti i mirror irraggiungibili → OverpassError (best-effort: il chiamante
    degrada), senza appendersi: ogni host è provato e scartato."""
    import httpx

    from opendata_core.osm import client as osm_client

    for ep in osm_client.overpass_endpoints():
        httpx_mock.add_exception(httpx.ConnectError("egress blocked"), url=ep)

    with pytest.raises(osm_client.OverpassError):
        await osm_client.overpass_post("[out:json];node(1);out;")
