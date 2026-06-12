"""Tests for /territorio endpoints and the zone→task injection (spec 06)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from opendata_backend.orchestrator.programma import ProgrammaRequest, build_programma_task
from opendata_backend.routers import territorio as territorio_router

from opendata_core.osm import zones


@pytest.fixture(autouse=True)
def _clear_core_cache():
    zones.cache_clear()
    yield
    zones.cache_clear()


async def test_cerca_comuni_returns_results(monkeypatch) -> None:
    async def fake_lookup(nome: str, limit: int = 8):
        return [{"nome": "Barletta", "ref_istat": "110002", "cod_provincia": "110",
                 "osm_id": "relation/41200", "osm_url": "https://www.openstreetmap.org/relation/41200"}]

    monkeypatch.setattr(zones, "lookup_comune", fake_lookup)
    out = await territorio_router.cerca_comuni(q="Barlet", user=None)  # type: ignore[arg-type]
    assert out["count"] == 1
    assert out["results"][0]["ref_istat"] == "110002"


async def test_lista_zone_rejects_invalid_tipo() -> None:
    with pytest.raises(HTTPException) as exc:
        await territorio_router.lista_zone(
            cod_comune="072006", tipo="balneare", comune_nome=None, user=None  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 422
    assert "industriale" in exc.value.detail


async def test_lista_zone_happy_path(monkeypatch) -> None:
    async def fake_list(cod_comune: str, tipo: str, comune_nome=None):
        return {"candidates": [{"osm_id": "way/1", "name": "ZI Test", "zona_tipo": tipo,
                                "geometry": {"type": "Polygon", "coordinates": []}}],
                "fallback_level": 1, "zona_tipo": tipo, "ref_istat": cod_comune,
                "source_url": "https://overpass-api.de/..."}

    monkeypatch.setattr(zones, "list_zones", fake_list)
    out = await territorio_router.lista_zone(
        cod_comune="072006", tipo="industriale", comune_nome=None, user=None  # type: ignore[arg-type]
    )
    assert out["fallback_level"] == 1
    assert out["candidates"][0]["name"] == "ZI Test"


async def test_lista_zone_maps_overpass_outage_to_503(monkeypatch) -> None:
    async def fake_list(cod_comune: str, tipo: str, comune_nome=None):
        raise zones.OverpassError("Overpass non disponibile dopo 3 tentativi (HTTP 429)")

    monkeypatch.setattr(zones, "list_zones", fake_list)
    with pytest.raises(HTTPException) as exc:
        await territorio_router.lista_zone(
            cod_comune="072006", tipo="industriale", comune_nome=None, user=None  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 503


# ───────────────────── zona risolta → task del fan-out ──────────────────────


def test_task_injects_zone_name_centroid_bbox() -> None:
    req = ProgrammaRequest(cod_comune="072006", zona_osm_id="relation/20799475")
    zona_info = {
        "name": "Zona Industriale di Bari",
        "centroid": {"lat": 41.10579, "lon": 16.79321},
        "bbox": [41.09, 16.77, 41.12, 16.82],
    }
    task = build_programma_task(req, zona_info)
    assert "Zona Industriale di Bari" in task
    assert "lat=41.10579" in task and "lon=16.79321" in task
    assert "bbox sud=41.09000" in task and "est=16.82000" in task


def test_task_without_zone_info_falls_back_to_text() -> None:
    req = ProgrammaRequest(cod_comune="072006", zona="area industriale")
    task = build_programma_task(req, None)
    assert "area industriale" in task and "bbox" not in task
