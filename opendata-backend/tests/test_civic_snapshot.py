"""Test KPI civici + snapshot versionati (Fase 4, H2)."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.civic.kpi import compute_kpis
from opendata_backend.civic.snapshot import (
    SnapshotError,
    create_snapshot,
    list_snapshots,
)
from opendata_backend.db.models import Base


def _state(*, concluded: int, total: int, accessibility: float = 50.0) -> dict:
    projects = (
        [{"stato": "concluso"} for _ in range(concluded)]
        + [{"stato": "in corso"} for _ in range(total - concluded)]
    )
    return {
        "name": "Gioia del Colle",
        "features": {"service_accessibility_score": accessibility,
                     "competitor_density_per_1k": 1.4, "walkability_proxy": 40},
        "investimenti": {"finanziamento_totale": 200000.0},
        "projects": projects,
        "population": 20000,
    }


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


def test_compute_kpis_values() -> None:
    k = compute_kpis(_state(concluded=1, total=2))
    assert k["accessibilita_servizi"]["value"] == 50.0
    assert k["investimento_procapite"]["value"] == 10.0       # 200000/20000
    assert k["progetti_conclusi_pct"]["value"] == 50.0
    assert k["accessibilita_servizi"]["direction"] == "up"
    assert k["densita_competitor"]["direction"] == "context"


async def test_create_snapshot_versioning(session: AsyncSession) -> None:
    snap = await create_snapshot(session, istat_code="072021", snapshot_id="2026-H1",
                                 sources_version="2026-06", state=_state(concluded=1, total=4))
    await session.commit()
    assert snap.kpi_version == "1"
    assert snap.kpi_jsonb["progetti_conclusi_pct"]["value"] == 25.0

    # stesso snapshot_id → vietato (non si sovrascrive)
    with pytest.raises(SnapshotError):
        await create_snapshot(session, istat_code="072021", snapshot_id="2026-H1",
                              sources_version="2026-06", state=_state(concluded=2, total=4))
    await session.rollback()

    # nuovo snapshot_id → ok
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H2",
                          sources_version="2026-12", state=_state(concluded=3, total=4))
    await session.commit()
    snaps = await list_snapshots(session, "072021")
    assert [s.snapshot_id for s in snaps] == ["2026-H1", "2026-H2"]
