"""Smoke test ORM del modello territoriale (Fase 0) su SQLite in-memory.

SQLite non onora lo schema `opendata` né PostGIS: la colonna `geom` è TEXT
(vedi `territory_models._GEOM`) e lo schema viene tolto come in test_db_models.
Verifica che le 13 tabelle si creino e che gli insert base funzionino.
"""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db import territory_models as tm
from opendata_backend.db.models import Base

_TERRITORY_TABLES = {
    "entities",
    "dataset_quality",
    "maturity_assessments",
    "place",
    "feature_store",
    "territory_reports",
    "population_profile",
    "business_cluster",
    "tourism_signal",
    "work_signal",
    "mobility_node",
    "weather_signal",
    "investment",
}


def _strip_schema(metadata: MetaData) -> None:
    """SQLite doesn't honour PostgreSQL `schema=` kwargs — strip them off."""
    for table in metadata.tables.values():
        table.schema = None


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


async def test_all_territory_tables_created(session: AsyncSession) -> None:
    def _names(sync_conn: object) -> set[str]:
        return set(inspect(sync_conn).get_table_names())

    tables = await session.run_sync(lambda s: _names(s.connection()))
    assert _TERRITORY_TABLES <= tables


async def test_place_and_entity_insert(session: AsyncSession) -> None:
    place = tm.Place(istat_code="072021", name="Gioia del Colle", type="comune")
    session.add(place)
    await session.commit()
    await session.refresh(place)

    entity = tm.Entity(
        name="Comune di Gioia del Colle", type="comune", ckan_org_id="org-gdc"
    )
    session.add(entity)
    await session.commit()

    rows = (await session.execute(select(tm.Place))).scalars().all()
    assert len(rows) == 1
    assert rows[0].istat_code == "072021"


async def test_feature_store_and_signal_jsonb(session: AsyncSession) -> None:
    place = tm.Place(istat_code="072021", name="Gioia del Colle", type="comune")
    session.add(place)
    await session.commit()
    await session.refresh(place)

    session.add(tm.FeatureStore(place_id=place.id, features_jsonb={"pop": 27000}))
    session.add(
        tm.TourismSignal(place_id=place.id, source="osm", payload_jsonb={"hotels": 3})
    )
    await session.commit()

    fs = (await session.execute(select(tm.FeatureStore))).scalars().one()
    assert fs.features_jsonb == {"pop": 27000}
    sig = (await session.execute(select(tm.TourismSignal))).scalars().one()
    assert sig.payload_jsonb == {"hotels": 3}
