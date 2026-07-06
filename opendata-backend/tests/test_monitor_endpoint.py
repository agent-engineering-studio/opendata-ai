"""Test dell'endpoint GET /monitor/{entity_id} (#88)."""

from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from opendata_backend.auth import ClerkUser
from opendata_backend.auth import dependencies as auth_dep
from opendata_backend.config import Settings, get_settings
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import monitor as repo
from opendata_backend.db.session import get_db_session
from opendata_backend.db.territory_models import Entity
from opendata_backend.routers import monitor


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


@pytest.fixture
async def sessionmaker() -> async_sessionmaker[AsyncSession]:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _client(sm: async_sessionmaker[AsyncSession]) -> TestClient:
    user = ClerkUser(subject="u_monitor", email=None, claims={})

    async def _user() -> ClerkUser:
        return user

    async def _db() -> AsyncIterator[AsyncSession]:
        async with sm() as session:
            yield session

    app = FastAPI()
    app.include_router(monitor.router)
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=False)  # type: ignore[call-arg]
    app.dependency_overrides[auth_dep.require_user] = _user
    app.dependency_overrides[get_db_session] = _db
    return TestClient(app)


async def test_no_targets_returns_empty_list(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    client = _client(sessionmaker)
    res = client.get("/monitor/999")
    assert res.status_code == 200
    assert res.json() == {"entity_id": 999, "targets": []}


async def test_target_with_run_returns_latest_esito(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        ent = Entity(name="Regione Puglia")
        session.add(ent)
        await session.flush()
        t = await repo.create_target(session, url="https://x.it/a.csv", entity_id=ent.id)
        await repo.save_run(
            session, target_id=t.id, esito="attenzione",
            findings=[{"livello": "medio", "codice": "stantio", "messaggio": "x"}],
            diff={"nuovi": [], "risolti": [], "invariati": []}, quality_score=80.0,
        )
        await session.commit()
        entity_id = ent.id

    client = _client(sessionmaker)
    res = client.get(f"/monitor/{entity_id}")
    assert res.status_code == 200
    body = res.json()
    assert len(body["targets"]) == 1
    assert body["targets"][0]["ultimo_run"]["esito"] == "attenzione"
    assert body["targets"][0]["ultimo_run"]["quality_score"] == 80.0


async def test_target_without_run_has_null_ultimo_run(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        ent = Entity(name="Comune di Bari")
        session.add(ent)
        await session.flush()
        await repo.create_target(session, url="https://x.it/b.csv", entity_id=ent.id)
        await session.commit()
        entity_id = ent.id

    client = _client(sessionmaker)
    body = client.get(f"/monitor/{entity_id}").json()
    assert body["targets"][0]["ultimo_run"] is None
