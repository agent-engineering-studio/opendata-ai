"""Test orchestrazione sito civico (Fase 4, I2): 2 snapshot → diff + maturità."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.civic.site_service import build_site
from opendata_backend.civic.snapshot import create_snapshot
from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import Entity, MaturityAssessment

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _state(concluded: int, total: int) -> dict:
    return {
        "name": "Gioia del Colle",
        "population": 27889,
        "features": {"service_accessibility_score": 50.0, "competitor_density_per_1k": 1.4,
                     "walkability_proxy": 40},
        "investimenti": {"n_progetti": total, "finanziamento_totale": 350000.0,
                         "per_tema": [{"tema": "Trasporti", "finanziamento": 250000.0}]},
        "projects": [{"clp": str(i), "titolo": f"Opera {i}",
                      "stato": "concluso" if i <= concluded else "in corso"} for i in range(1, total + 1)],
        "report": {"sezioni": {"idee_sviluppo": [{"category": "Bar", "score": 88.8, "rationale": "ok"}],
                               "gap_dato": ["Dati occupazione non integrati."]}},
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


async def test_build_site_with_two_snapshots(session: AsyncSession) -> None:
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H1",
                          sources_version="2026-06", state=_state(1, 4))
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H2",
                          sources_version="2026-12", state=_state(3, 4))
    # maturità collegabile per nome ente
    ent = Entity(name="Comune di Gioia del Colle", type="comune")
    session.add(ent)
    await session.flush()
    session.add(MaturityAssessment(entity_id=ent.id, assessed_at=AT, score_overall=67.0,
                                   score_policy=66.7, score_portal=75.0, score_quality=72.7,
                                   score_impact=48.7, level="Fast-tracker"))
    await session.commit()

    files = await build_site(session, istat_code="072021")  # default → ultimo (H2)
    assert files is not None
    # avanzamento col diff H1→H2: 2 opere passate a concluso
    assert "opere concluse" in files["avanzamento.html"]
    assert "2026-H2" in files["index.html"]
    # anello valore⇄maturità
    assert "Fast-tracker" in files["scorecard.html"]


async def test_build_site_none_without_snapshot(session: AsyncSession) -> None:
    assert await build_site(session, istat_code="999999") is None
