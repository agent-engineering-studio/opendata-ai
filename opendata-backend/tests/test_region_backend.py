"""Cruscotto regionale backend (#229): service + /regione/overview|comuni."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.db.session import get_db_session
from opendata_backend.db.territory_models import DatasetQuality, Entity, MaturityAssessment
from opendata_backend.routers import region


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture
async def sm() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        # Puglia (16): 3 comuni in anagrafica; solo 2 valutati.
        s.add_all([
            ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle",
                             cod_provincia="072", cod_regione="16", popolazione=27000),
            ComuneAnagrafica(cod_comune="072006", nome="Bari",
                             cod_provincia="072", cod_regione="16", popolazione=320000),
            ComuneAnagrafica(cod_comune="073013", nome="Lecce",
                             cod_provincia="073", cod_regione="16", popolazione=95000),
            # comune fuori regione — non deve comparire
            ComuneAnagrafica(cod_comune="015146", nome="Milano",
                             cod_provincia="015", cod_regione="03", popolazione=1400000),
        ])
        e1 = Entity(name="Gioia del Colle", type="comune", region="Puglia")
        e2 = Entity(name="Bari", type="comune", region="Puglia")
        s.add_all([e1, e2])
        await s.flush()
        s.add_all([
            MaturityAssessment(entity_id=e1.id, score_overall=30, score_policy=20,
                               score_quality=40, level="follower",
                               details_jsonb={"n_datasets": 6}),
            MaturityAssessment(entity_id=e2.id, score_overall=82, score_policy=80,
                               score_quality=85, level="leader",
                               details_jsonb={"n_datasets": 40}),
            DatasetQuality(entity_id=e2.id, source="ckan", dataset_id="d1", hvd_category="mobility"),
            DatasetQuality(entity_id=e2.id, source="ckan", dataset_id="d2", hvd_category="geospatial"),
            DatasetQuality(entity_id=e1.id, source="ckan", dataset_id="d3", hvd_category="geospatial"),
        ])
        await s.commit()
    yield maker
    await engine.dispose()


def _client(sm, *, region_code: str = "16") -> TestClient:
    async def _user() -> ClerkUser:
        return ClerkUser(subject="u_reg", email=None, claims={})

    async def _db() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    app = FastAPI()
    app.include_router(region.router)
    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        auth_enabled=False, region_istat=region_code,
    )
    app.dependency_overrides[auth_dep.require_user] = _user
    app.dependency_overrides[get_db_session] = _db
    return TestClient(app)


def test_overview_scoped_and_aggregated(sm) -> None:
    body = _client(sm).get("/regione/overview").json()
    assert body["cod_regione"] == "16"
    # 3 comuni pugliesi (Milano esclusa), 2 valutati.
    assert body["comuni_totali"] == 3
    assert body["comuni_valutati"] == 2
    # Bari maturo, Gioia pochi_dati (overall 30<40), Lecce zero_dati (non valutato).
    assert body["distribuzione_stato"] == {
        "zero_dati": 1, "pochi_dati": 1, "in_crescita": 0, "maturo": 1
    }
    # HVD: geospatial su 2/3 comuni, mobility su 1/3.
    assert body["hvd_copertura"]["geospatial"] == round(2 / 3, 3)
    assert body["hvd_copertura"]["mobility"] == round(1 / 3, 3)
    # dove intervenire: Lecce (zero) + Gioia (bassa) tra i comuni.
    ids = {h["istat"] for h in body["dove_intervenire"] if h["tipo"] == "comune"}
    assert "073013" in ids and "072021" in ids and "072006" not in ids


def test_comuni_ranked_and_filtered(sm) -> None:
    body = _client(sm).get("/regione/comuni").json()
    assert body["totale"] == 3
    # Bari (82) primo, Lecce (non valutato) ultimo.
    assert body["comuni"][0]["nome"] == "Bari"
    assert body["comuni"][-1]["nome"] == "Lecce"
    assert body["comuni"][-1]["stato"] == "zero_dati"
    # filtro per provincia 073 → solo Lecce
    only73 = _client(sm).get("/regione/comuni", params={"provincia": "073"}).json()
    assert [c["nome"] for c in only73["comuni"]] == ["Lecce"]


def test_empty_when_region_has_no_comuni(sm) -> None:
    # regione senza comuni in anagrafica → vista vuota, mai 500
    body = _client(sm, region_code="99").get("/regione/overview").json()
    assert body["comuni_totali"] == 0
    assert body["mediana_overall"] is None
    assert body["dove_intervenire"] == []
