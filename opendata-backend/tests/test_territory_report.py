"""Test del servizio report territoriale (Fase 2, B3) su SQLite, dipendenze mockate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.db.territory_models import Investment, TerritoryReport, TourismSignal
import opendata_backend.territory.service as svc
from opendata_core.territory import PlaceRef, TerritoryProfile


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


def _settings() -> SimpleNamespace:
    return SimpleNamespace(claude_model="claude-sonnet-4-6")


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _mock_externals(monkeypatch) -> None:
    async def fake_resolve(name, *, istat_code=None):
        return PlaceRef(name=name, istat_code=istat_code, lat=40.8, lon=16.9, geojson=None)

    async def fake_profile(place, *, population=None, radius_m=5000):
        return TerritoryProfile(
            population={"total": population} if population is not None else {},
            business={"totale": 40}, tourism={"hotel": 2, "totale": 5},
        )

    async def fake_fetch(*, cod_comune, max_projects=50, client=None):
        return {
            "projects": [
                {"clp": "1", "titolo": "Scuola", "tema": "Istruzione", "finanziamento_totale": 100000.0},
                {"clp": "2", "titolo": "Strada", "tema": "Trasporti", "finanziamento_totale": 250000.0},
            ],
            "aggregates": {}, "total": 2,
        }

    monkeypatch.setattr(svc, "resolve_place", fake_resolve)
    monkeypatch.setattr(svc, "build_profile", fake_profile)
    monkeypatch.setattr(svc, "fetch_investments", fake_fetch)


@pytest.fixture
async def session() -> AsyncSession:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        s.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle",
                               cod_provincia="072", cod_regione="16", popolazione=27000))
        await s.commit()
        yield s
    await engine.dispose()


async def test_build_report_structure_and_persistence(session: AsyncSession) -> None:
    report = await svc.build_report(
        session, istat_code="072021", temi=["mobilità"], anno_da=2014, anno_a=2027,
        settings=_settings(),
    )

    assert report["place"]["name"] == "Gioia del Colle"
    sez = report["sezioni"]
    assert set(sez) >= {"profilo", "investimenti", "servizi_accessibilita", "segnali",
                        "idee_sviluppo", "gap_dato"}
    assert sez["profilo"]["population"] == {"total": 27000}
    assert sez["investimenti"]["finanziamento_totale"] == 350000.0
    # idee di sviluppo ora popolate da ApriQui (Fase 3): top categorie con score
    assert 1 <= len(sez["idee_sviluppo"]) <= 3
    assert all("category" in i and "score" in i for i in sez["idee_sviluppo"])
    assert report["narrativa"]  # fallback deterministico

    # persistenza
    inv = (await session.execute(select(func.count()).select_from(Investment))).scalar_one()
    rep = (await session.execute(select(func.count()).select_from(TerritoryReport))).scalar_one()
    tour = (await session.execute(select(func.count()).select_from(TourismSignal))).scalar_one()
    assert inv == 2 and rep == 1 and tour == 1


async def test_profile_cached_after_report(session: AsyncSession) -> None:
    assert await svc.get_profile(session, "072021") is None  # prima del report
    await svc.build_report(session, istat_code="072021", temi=None, anno_da=None, anno_a=None,
                           settings=_settings())
    profile = await svc.get_profile(session, "072021")
    assert profile is not None
    assert profile["features"]["profile"]["business"]["totale"] == 40
    assert profile["features"]["investments"]["n_progetti"] == 2


async def test_report_idempotent_signals_investment(session: AsyncSession) -> None:
    await svc.build_report(session, istat_code="072021", temi=None, anno_da=None, anno_a=None,
                           settings=_settings())
    await svc.build_report(session, istat_code="072021", temi=None, anno_da=None, anno_a=None,
                           settings=_settings())
    # investment + signal rigenerati (non duplicati); report storicizzato (2)
    inv = (await session.execute(select(func.count()).select_from(Investment))).scalar_one()
    rep = (await session.execute(select(func.count()).select_from(TerritoryReport))).scalar_one()
    assert inv == 2
    assert rep == 2
