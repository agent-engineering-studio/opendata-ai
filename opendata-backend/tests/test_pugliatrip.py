"""Test PugliaTrip Brain (Fase 3, F2): itinerario puro + run con fonti mockate."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base, ComuneAnagrafica
import opendata_backend.usecases.pugliatrip as pt
from opendata_core.territory import PlaceRef

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)

_POIS = [
    {"name": "Castello Normanno-Svevo", "kind": "castle"},
    {"name": "Museo Civico", "kind": "museum"},
    {"name": "Centro storico", "kind": "attraction"},
    {"name": "Pinacoteca", "kind": "gallery"},
]
_FORECAST = [
    {"date": "2026-06-18", "outdoor_ok": True, "label": "sereno", "tmax": 30, "precip": 0},
    {"date": "2026-06-19", "outdoor_ok": False, "label": "pioggia", "tmax": 22, "precip": 8},
]


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
async def session() -> AsyncSession:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s
    await engine.dispose()


def test_build_itinerary_weather_aware() -> None:
    plan = pt.build_itinerary(list(_POIS), _FORECAST)
    assert len(plan) == 2
    # giorno sereno → POI all'aperto (castle/attraction)
    day1_kinds = {p["kind"] for p in plan[0]["pois"]}
    assert day1_kinds <= {"castle", "attraction"}
    # giorno di pioggia → POI al chiuso (museum/gallery)
    day2_kinds = {p["kind"] for p in plan[1]["pois"]}
    assert day2_kinds <= {"museum", "gallery"}
    # nessun POI ripetuto fra i giorni
    names = [p["name"] for d in plan for p in d["pois"]]
    assert len(names) == len(set(names))


def test_build_itinerary_empty() -> None:
    assert pt.build_itinerary([], _FORECAST)[0]["pois"] == []


async def test_run_pugliatrip_mocked(session: AsyncSession, monkeypatch) -> None:
    async def fake_resolve(name, *, istat_code=None):
        return PlaceRef(name=name, istat_code=istat_code, lat=40.8, lon=16.9)

    async def fake_landmarks(*, bbox, limit=20, timeout=30.0):
        return list(_POIS)

    async def fake_forecast(lat, lon, *, days=3):
        return {"daily": _FORECAST}

    monkeypatch.setattr(pt, "resolve_place", fake_resolve)
    monkeypatch.setattr(pt, "overpass_tourism_landmarks", fake_landmarks)
    monkeypatch.setattr(pt, "forecast", fake_forecast)

    session.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle", popolazione=27889))
    await session.commit()

    out = await pt.run_pugliatrip(session, istat_code="072021", days=2,
                                  settings=SimpleNamespace(claude_model="claude-sonnet-4-6", llm_provider="claude", anthropic_api_key=None))
    assert out["place"]["name"] == "Gioia del Colle"
    assert out["n_pois"] == 4
    assert len(out["itinerary"]) == 2
    assert out["explanation"]  # fallback deterministico
