"""Test dei modelli + repository di monitoraggio su SQLite (#88)."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.repositories import monitor as repo
from opendata_backend.db.territory_models import Entity

_TABLES = {"monitor_targets", "monitor_runs"}


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


async def test_monitor_tables_created(session: AsyncSession) -> None:
    names = await session.run_sync(lambda s: set(inspect(s.connection()).get_table_names()))
    assert _TABLES <= names


async def test_create_and_list_active_targets(session: AsyncSession) -> None:
    t1 = await repo.create_target(session, url="https://x.it/a.csv", accrual_periodicity="MONTHLY")
    t2 = await repo.create_target(session, url="https://x.it/b.csv")
    t2.active = False
    await session.commit()

    active = await repo.list_active_targets(session)
    assert [t.id for t in active] == [t1.id]


async def test_target_linked_to_entity(session: AsyncSession) -> None:
    ent = Entity(name="Regione Puglia")
    session.add(ent)
    await session.flush()
    t = await repo.create_target(session, url="https://x.it/a.csv", entity_id=ent.id)
    await session.commit()

    targets = await repo.list_targets_by_entity(session, ent.id)
    assert [x.id for x in targets] == [t.id]


async def test_latest_run_none_before_first_run(session: AsyncSession) -> None:
    t = await repo.create_target(session, url="https://x.it/a.csv")
    await session.commit()
    assert await repo.latest_run(session, t.id) is None


async def test_save_run_and_latest_run(session: AsyncSession) -> None:
    t = await repo.create_target(session, url="https://x.it/a.csv")
    await session.commit()

    await repo.save_run(
        session, target_id=t.id, esito="ok", findings=[], diff={"nuovi": [], "risolti": [], "invariati": []},
        quality_score=90.0,
    )
    await session.commit()
    r1 = await repo.latest_run(session, t.id)
    assert r1 is not None and r1.esito == "ok" and float(r1.quality_score) == 90.0

    await repo.save_run(
        session, target_id=t.id, esito="critico",
        findings=[{"livello": "alto", "codice": "link_rotto", "messaggio": "x"}],
        diff={"nuovi": ["link_rotto"], "risolti": [], "invariati": []}, quality_score=None,
    )
    await session.commit()
    r2 = await repo.latest_run(session, t.id)
    assert r2 is not None and r2.esito == "critico" and r2.id != r1.id


async def test_run_trend_ordered_desc(session: AsyncSession) -> None:
    t = await repo.create_target(session, url="https://x.it/a.csv")
    await session.commit()
    for esito in ("ok", "attenzione", "critico"):
        await repo.save_run(session, target_id=t.id, esito=esito, findings=[], diff={})
        await session.commit()
    trend = await repo.run_trend(session, t.id)
    assert [r.esito for r in trend] == ["critico", "attenzione", "ok"]
