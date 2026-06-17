"""Test showcase-engine (Fase 3, E1): caricamento YAML + esecuzione su SQLite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.repositories import territory as repo
from opendata_backend.db.territory_models import Investment
from opendata_backend.showcase import get_showcase, list_showcases, run_showcase

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


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


def test_list_and_get_showcases() -> None:
    ids = {s["id"] for s in list_showcases()}
    assert {"competitor-density", "accessibilita-servizi", "investimenti-pubblici"} <= ids
    assert get_showcase("competitor-density")["source"] == "feature_store"
    assert get_showcase("inesistente") is None


async def test_run_feature_store_showcase(session: AsyncSession) -> None:
    place = await repo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    await repo.upsert_feature_store(
        session, place_id=place.id,
        features={"features": {"competitor_density_per_1k": 1.43}}, computed_at=AT,
    )
    await session.commit()

    out = await run_showcase(session, "competitor-density", istat_code="072021")
    assert out["data"]["value"] == 1.43
    assert out["visualization"]["type"] == "number"
    assert out["license"]


async def test_run_investment_showcase(session: AsyncSession) -> None:
    place = await repo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    session.add_all([
        Investment(place_id=place.id, source="opencoesione", observed_at=AT,
                   payload_jsonb={"finanziamento_totale": 100000.0}),
        Investment(place_id=place.id, source="opencoesione", observed_at=AT,
                   payload_jsonb={"finanziamento_totale": 250000.0}),
    ])
    await session.commit()

    out = await run_showcase(session, "investimenti-pubblici", istat_code="072021")
    assert out["data"]["n_progetti"] == 2
    assert out["data"]["finanziamento_totale"] == 350000.0


async def test_run_unknown_returns_none(session: AsyncSession) -> None:
    assert await run_showcase(session, "boh", istat_code="072021") is None
