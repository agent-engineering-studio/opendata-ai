"""Test feature store (Fase 3, D1): compute puro + materializzazione su SQLite."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.db.repositories import territory as repo
from opendata_backend.db.territory_models import MobilityNode
from opendata_backend.features.engineering import compute_features
from opendata_backend.features.materialize import materialize_features

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


def test_compute_features_values() -> None:
    out = compute_features(
        business={"totale": 40, "pharmacy": 1, "supermarket": 2, "restaurant": 5, "park": 1, "bank": 0},
        tourism={"totale": 5, "museum": 1},
        mobility=[{"distance_km": 0.4}, {"distance_km": 1.2}],
        population=27889,
    )
    f = out["features"]
    assert f["competitor_density_per_1k"] == round(40 / 27889 * 1000, 2)
    assert f["service_accessibility_score"] == round(100 * 2 / 7, 1)  # pharmacy+supermarket
    assert f["family_friendly_pois"] == 7  # park1+restaurant5+museum1
    assert f["walkability_proxy"] == 40.0
    assert f["distance_to_nearest_stop_km"] == 0.4
    assert f["age_25_44_share"] is None
    assert any("fragilità" in g.lower() or "fascia" in g.lower() for g in out["gaps"])


def test_compute_features_handles_missing() -> None:
    out = compute_features(business=None, tourism=None, mobility=None, population=None)
    assert out["features"]["competitor_density_per_1k"] is None
    assert out["features"]["distance_to_nearest_stop_km"] is None


async def test_materialize_features(session: AsyncSession) -> None:
    place = await repo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    await repo.upsert_feature_store(
        session, place_id=place.id,
        features={"profile": {"business": {"totale": 40, "pharmacy": 1}, "tourism": {"totale": 5}}},
        computed_at=AT,
    )
    session.add(MobilityNode(place_id=place.id, source="gtfs", observed_at=AT,
                             payload_jsonb={"stop_id": "S1", "distance_km": 0.3}))
    session.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle", popolazione=27889))
    await session.commit()

    result = await materialize_features(session, istat_code="072021")
    assert result is not None
    assert result["features"]["distance_to_nearest_stop_km"] == 0.3

    fs = await repo.get_feature_store(session, place.id)
    assert fs.features_jsonb["features"]["competitor_density_per_1k"] is not None
    assert "feature_gaps" in fs.features_jsonb
    # profilo preesistente preservato (merge)
    assert fs.features_jsonb["profile"]["business"]["totale"] == 40


async def test_materialize_none_when_no_place(session: AsyncSession) -> None:
    assert await materialize_features(session, istat_code="999999") is None
