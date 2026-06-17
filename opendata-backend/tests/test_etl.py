"""Test ETL Fase 3 (C3): record_raw idempotente + GTFS → mobility_node."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_core.gtfs import GtfsStop
from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import MobilityNode, Place, RawIngest
from opendata_backend.etl.mobility import haversine_km, ingest_gtfs_stops
from opendata_backend.etl.raw import payload_sha, record_raw

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


def test_payload_sha_stable_and_order_independent() -> None:
    assert payload_sha({"a": 1, "b": 2}) == payload_sha({"b": 2, "a": 1})
    assert payload_sha({"a": 1}) != payload_sha({"a": 2})


async def test_record_raw_idempotent(session: AsyncSession) -> None:
    _, c1 = await record_raw(session, source="ckan", payload={"x": 1}, license="CC-BY")
    await session.commit()
    _, c2 = await record_raw(session, source="ckan", payload={"x": 1}, license="CC-BY")
    await session.commit()
    assert c1 is True and c2 is False
    n = (await session.execute(select(func.count()).select_from(RawIngest))).scalar_one()
    assert n == 1


def test_haversine_km() -> None:
    d = haversine_km(40.80, 16.92, 40.79, 16.93)
    assert 0.5 < d < 2.0  # ~1.3 km


async def test_ingest_gtfs_filters_and_idempotent(session: AsyncSession) -> None:
    place = Place(istat_code="072021", name="Gioia del Colle", type="comune")
    session.add(place)
    await session.flush()

    stops = [
        GtfsStop("S1", "Stazione", 40.800, 16.920),     # vicina
        GtfsStop("S2", "Piazza", 40.795, 16.925),        # vicina
        GtfsStop("FAR", "Bari Centrale", 41.117, 16.871),  # ~36 km → esclusa
    ]
    n = await ingest_gtfs_stops(session, place_id=place.id, stops=stops, observed_at=AT,
                                center=(40.7986, 16.9268), radius_km=10)
    await session.commit()
    assert n == 2

    nodes = (await session.execute(select(func.count()).select_from(MobilityNode))).scalar_one()
    assert nodes == 2
    raws = (await session.execute(select(func.count()).select_from(RawIngest))).scalar_one()
    assert raws == 1

    # re-run: mobility_node rigenerati (non duplicati)
    await ingest_gtfs_stops(session, place_id=place.id, stops=stops, observed_at=AT,
                            center=(40.7986, 16.9268), radius_km=10)
    await session.commit()
    nodes2 = (await session.execute(select(func.count()).select_from(MobilityNode))).scalar_one()
    assert nodes2 == 2
