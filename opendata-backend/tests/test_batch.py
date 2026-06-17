"""Test batch ricorrente (Fase 5, M1): idempotenza degli snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import opendata_backend.ingest.batch as batch
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import territory as trepo
from opendata_backend.db.territory_models import CivicSnapshot

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


@pytest.fixture(autouse=True)
def _fake_assessment(monkeypatch) -> None:
    async def fake_run_assessment(session, **kwargs):  # noqa: ANN001
        return {"level": "Beginner", "overall": 0.0}

    monkeypatch.setattr(batch, "run_assessment", fake_run_assessment)


async def test_batch_idempotent_snapshots(session: AsyncSession) -> None:
    # stato minimo per build_state dello snapshot
    place = await trepo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    await trepo.upsert_feature_store(session, place_id=place.id,
                                     features={"features": {"walkability_proxy": 40},
                                               "profile": {"business": {"totale": 40}}},
                                     computed_at=AT)
    await session.commit()

    targets = [{"entity": "comune-di-gioia-del-colle", "istat": "072021"}]

    first = await batch.run_batch(session, targets=targets,
                                  settings=SimpleNamespace(anthropic_api_key=None,
                                                           claude_classify_model="m",
                                                           maturity_max_datasets=50,
                                                           maturity_cache_ttl_seconds=3600),
                                  snapshot_id="2026-H1")
    assert first["targets"][0]["snapshot"] == "created"

    second = await batch.run_batch(session, targets=targets,
                                   settings=SimpleNamespace(anthropic_api_key=None,
                                                            claude_classify_model="m",
                                                            maturity_max_datasets=50,
                                                            maturity_cache_ttl_seconds=3600),
                                   snapshot_id="2026-H1")
    assert second["targets"][0]["snapshot"] == "exists"  # idempotente: non duplica

    n = (await session.execute(select(func.count()).select_from(CivicSnapshot))).scalar_one()
    assert n == 1


async def test_load_targets_has_pilot() -> None:
    targets = batch.load_targets()
    assert any(t.get("istat") == "072021" for t in targets)
