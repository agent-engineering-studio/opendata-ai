"""Test check-in → thread community (Fase 4, J2)."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.civic.checkin import open_checkin_thread
from opendata_backend.civic.snapshot import create_snapshot
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import community as community_repo


def _state(concluded: int, total: int) -> dict:
    return {
        "name": "Gioia del Colle", "population": 27889,
        "features": {"service_accessibility_score": 50.0, "walkability_proxy": 40},
        "investimenti": {"finanziamento_totale": 350000.0},
        "projects": [{"clp": str(i), "titolo": f"Opera {i}",
                      "stato": "concluso" if i <= concluded else "in corso"} for i in range(1, total + 1)],
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


async def test_checkin_first_snapshot_no_thread(session: AsyncSession) -> None:
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H1",
                          sources_version="2026-06", state=_state(1, 4))
    await session.commit()
    assert await open_checkin_thread(session, istat_code="072021", snapshot_id="2026-H1") is None


async def test_checkin_opens_review_thread(session: AsyncSession) -> None:
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H1",
                          sources_version="2026-06", state=_state(1, 4))
    await create_snapshot(session, istat_code="072021", snapshot_id="2026-H2",
                          sources_version="2026-12", state=_state(3, 4))
    await session.commit()

    out = await open_checkin_thread(session, istat_code="072021", snapshot_id="2026-H2")
    await session.commit()
    assert out is not None
    assert out["opere_concluse"] == 2  # opere 2,3 passate a concluso
    assert "2026-H2" in out["summary"]

    threads = await community_repo.list_threads(session, "072021")
    assert any(t.topic_type == "snapshot" and t.topic_ref == "2026-H2" for t in threads)
    posts = await community_repo.list_posts(session, out["thread_id"])
    assert len(posts) == 1
    assert posts[0].author == "system"
