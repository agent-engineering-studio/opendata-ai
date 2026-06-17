"""Test modelli Fase 4 (H1) su SQLite: civic_snapshots + community."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import (
    CivicSnapshot,
    CommunityPost,
    CommunityThread,
)

_TABLES = {"civic_snapshots", "community_members", "community_threads", "community_posts"}


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


async def test_civic_tables_created(session: AsyncSession) -> None:
    names = await session.run_sync(lambda s: set(inspect(s.connection()).get_table_names()))
    assert _TABLES <= names


async def test_snapshot_versioning_unique(session: AsyncSession) -> None:
    session.add(CivicSnapshot(istat_code="072021", snapshot_id="2026-H1", payload_jsonb={"a": 1}))
    await session.commit()
    # stesso (istat, snapshot_id) → vietato (non si sovrascrive, si versiona)
    session.add(CivicSnapshot(istat_code="072021", snapshot_id="2026-H1", payload_jsonb={"a": 2}))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
    # snapshot_id diverso → consentito
    session.add(CivicSnapshot(istat_code="072021", snapshot_id="2026-H2", payload_jsonb={"a": 3}))
    await session.commit()


async def test_thread_and_post(session: AsyncSession) -> None:
    th = CommunityThread(istat_code="072021", topic_type="snapshot", topic_ref="2026-H2",
                         title="Cosa è cambiato", created_by="user_1")
    session.add(th)
    await session.flush()
    session.add(CommunityPost(thread_id=th.id, author="user_1", body="Ottimo avanzamento."))
    await session.commit()
    assert th.id is not None
