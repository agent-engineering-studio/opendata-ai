"""Test del modello raw_ingest (Fase 3, C2) su SQLite: creazione + vincolo sha unico."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import RawIngest


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


async def test_raw_ingest_table_created(session: AsyncSession) -> None:
    names = await session.run_sync(lambda s: set(inspect(s.connection()).get_table_names()))
    assert "raw_ingest" in names


async def test_raw_ingest_sha_unique(session: AsyncSession) -> None:
    session.add(RawIngest(source="ckan", dataset_id="d1", license="CC-BY", sha="abc",
                          payload_jsonb={"k": 1}))
    await session.commit()
    session.add(RawIngest(source="ckan", dataset_id="d1", license="CC-BY", sha="abc",
                          payload_jsonb={"k": 2}))
    with pytest.raises(IntegrityError):
        await session.commit()
