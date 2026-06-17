"""Test anello valore⇄maturità (Fase 5, L2): gap → reuse_demand → Impact ridotto."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import opendata_backend.maturity.service as svc
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import territory as trepo
from opendata_backend.maturity.reuse_demand import unmet_reuse_demand
from opendata_core.maturity import DatasetInput
from opendata_core.maturity.harvest import HarvestResult

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _good(i: int) -> DatasetInput:
    return DatasetInput.from_ckan({
        "id": f"d{i}", "title": f"Statistiche {i}", "notes": "Descrizione chiara e completa per HVD.",
        "tags": [{"name": "statistica"}], "theme": "POP", "license_id": "cc-by-4.0", "isopen": True,
        "metadata_modified": "2026-04-01T00:00:00", "frequency": "annual",
        "resources": [{"format": "CSV", "url": f"https://ex.it/{i}.csv"}],
    })


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


def _settings() -> SimpleNamespace:
    return SimpleNamespace(anthropic_api_key=None, claude_classify_model="m",
                           maturity_max_datasets=50, maturity_cache_ttl_seconds=3600)


@pytest.fixture(autouse=True)
def _no_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


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


async def test_unmet_reuse_demand_aggregates_gaps(session: AsyncSession) -> None:
    place = await trepo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    await trepo.save_report(session, place_id=place.id, created_at=AT,
                            payload={"sezioni": {"gap_dato": ["Gap A", "Gap B"]}})
    await trepo.upsert_feature_store(session, place_id=place.id,
                                     features={"feature_gaps": ["Gap B", "Gap C"]}, computed_at=AT)
    await session.commit()
    d = await unmet_reuse_demand(session, istat_code="072021")
    assert d["count"] == 3  # A, B, C (B deduplicato)
    assert d["penalty"] == 0.3


async def test_ring_penalizes_impact(session: AsyncSession, monkeypatch) -> None:
    async def fake_harvest(entity, *, base_url=None, max_datasets=50, client=None):
        return HarvestResult(entity=entity, ckan_org_id="org-x", ckan_org_name="x",
                             org_title="Comune X", total=10,
                             datasets=tuple(_good(i) for i in range(10)))

    monkeypatch.setattr(svc, "harvest_entity", fake_harvest)

    # gap di dato per il comune (riducono l'Impact)
    place = await trepo.upsert_place(session, istat_code="072021", name="Comune X")
    await trepo.save_report(session, place_id=place.id, created_at=AT,
                            payload={"sezioni": {"gap_dato": ["Gap A", "Gap B"]}})
    await session.commit()

    base = await svc.run_assessment(session, entity="org-x", base_url=None,
                                    settings=_settings(), force=True)
    ring = await svc.run_assessment(session, entity="org-x", base_url=None,
                                    settings=_settings(), force=True, istat_code="072021")

    assert ring["unmet_reuse_demand"]["count"] == 2
    assert ring["unmet_reuse_demand"]["penalty"] == 0.2
    assert ring["dimensions"]["impact"] < base["dimensions"]["impact"]  # anello chiuso
