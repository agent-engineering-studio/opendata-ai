"""Test del backend Copilota Open Data (#222): service + endpoint /dataplan/*."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.db.session import get_db_session
from opendata_backend.db.territory_models import DataplanPlan
from opendata_backend.routers import dataplan


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
        s.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle",
                               cod_provincia="072", cod_regione="16", popolazione=27000))
        await s.commit()
    yield maker
    await engine.dispose()


def _client(sm, *, region: str = "") -> TestClient:
    async def _user() -> ClerkUser:
        return ClerkUser(subject="u_dp", email=None, claims={})

    async def _db() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    app = FastAPI()
    app.include_router(dataplan.router)
    # provider=claude + no key → LLM non configurato → fallback offline deterministico
    app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[call-arg]
        auth_enabled=False, region_istat=region, llm_provider="claude", anthropic_api_key=None,
    )
    app.dependency_overrides[auth_dep.require_user] = _user
    app.dependency_overrides[get_db_session] = _db
    return TestClient(app)


def test_inventario(sm) -> None:
    r = _client(sm).get("/dataplan/072021/inventario")
    assert r.status_code == 200
    body = r.json()
    assert body["totale"] >= 12
    assert any(c["gia_aperto_nazionale"] for c in body["candidati"])


def test_piano_ranks_quick_wins(sm) -> None:
    r = _client(sm).get("/dataplan/072021/piano")
    assert r.status_code == 200
    body = r.json()
    assert body["ente"] == "Gioia del Colle"
    assert body["ranking"][0]["quadrante"] == "quick_win"
    assert body["piano"]["quick_win"]
    assert "Piano di pubblicazione" in body["piano_markdown"]
    # KPI plannabili del pilota (#187): baseline + target
    kpi = body["kpi"]
    assert kpi["dataset_nel_piano"] >= 12
    assert kpi["gia_aperti_nazionali"] + kpi["da_produrre"] == kpi["quick_win"]
    assert kpi["target_dataset_conformi"] == 10


def test_diagnosi_baseline_and_national(sm) -> None:
    r = _client(sm).get("/dataplan/072021/diagnosi")
    assert r.status_code == 200
    body = r.json()
    assert body["comune"] == "Gioia del Colle"
    assert body["pubblicato"] is None and body["hint"]      # nessun assessment → hint onesto
    assert any(x["fonte"] for x in body["gia_aperto_nazionale"])
    # accompagnamento attivo (#184): nessun dato → stato "zero_dati" + percorso onboarding
    acc = body["accompagnamento"]
    assert acc["stato"] == "zero_dati"
    assert [s["chiave"] for s in acc["percorso"]][0] == "diagnosi"
    assert acc["prossima_azione"]


def test_politica_offline_and_persisted(sm) -> None:
    r = _client(sm).post("/dataplan/072021/politica", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["generato_con"] == "offline"          # nessun LLM configurato
    assert any("Finalità" in s["titolo"] for s in body["sezioni"])
    assert body["licenza"] == "CC-BY-4.0"

    # persistenza append-only
    import asyncio

    async def _count() -> int:
        async with sm() as s:
            return (await s.execute(
                select(func.count()).select_from(DataplanPlan)
                .where(DataplanPlan.tipo == "politica")
            )).scalar_one()

    assert asyncio.get_event_loop().run_until_complete(_count()) == 1


def test_brief_and_unknown(sm) -> None:
    client = _client(sm)
    r = client.post("/dataplan/072021/brief", json={"candidate_id": "esercizi-commerciali-suap"})
    assert r.status_code == 200
    body = r.json()
    assert body["candidate_id"] == "esercizi-commerciali-suap"
    assert body["privacy"]["richiede_validazione_umana"] is True  # dati personali → gate DPO
    assert body["passi"]
    # id inesistente → 404
    assert client.post("/dataplan/072021/brief", json={"candidate_id": "boh"}).status_code == 404


def test_region_scope_enforced(sm) -> None:
    # deployment scoped su Puglia (16): un comune fuori regione → 422
    client = _client(sm, region="16")
    assert client.get("/dataplan/072021/piano").status_code == 200      # Puglia → ok
    assert client.get("/dataplan/015146/piano").status_code == 422      # Milano → fuori
