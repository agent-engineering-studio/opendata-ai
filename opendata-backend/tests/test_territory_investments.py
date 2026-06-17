"""Test dell'aggregatore investimenti OpenCoesione (Fase 2, B1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.territory_models import Investment, Place
from opendata_backend.territory.investments import (
    fetch_investments,
    persist_investments,
    summarize_investments,
)

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)

_PROJECTS = [
    {"clp": "1", "titolo": "Scuola", "tema": "Istruzione", "finanziamento_totale": 100000.0},
    {"clp": "2", "titolo": "Strada", "tema": "Trasporti", "finanziamento_totale": 250000.0},
    {"clp": "3", "titolo": "Asilo", "tema": "Istruzione", "finanziamento_totale": 50000.0},
]


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


def test_summarize_investments() -> None:
    s = summarize_investments(_PROJECTS)
    assert s["n_progetti"] == 3
    assert s["finanziamento_totale"] == 400000.0
    assert s["per_tema"][0] == {"tema": "Trasporti", "finanziamento": 250000.0}


async def test_persist_investments_idempotent(session: AsyncSession) -> None:
    place = Place(istat_code="072021", name="Gioia del Colle", type="comune")
    session.add(place)
    await session.flush()

    n1 = await persist_investments(session, place_id=place.id, projects=_PROJECTS, observed_at=AT)
    await session.commit()
    assert n1 == 3

    # re-run: sostituisce, non duplica
    await persist_investments(session, place_id=place.id, projects=_PROJECTS[:1], observed_at=AT)
    await session.commit()
    count = (await session.execute(select(func.count()).select_from(Investment))).scalar_one()
    assert count == 1


async def test_fetch_investments_with_mocked_client(monkeypatch) -> None:
    from opendata_core.opencoesione import OpenCoesioneClient

    async def fake_aggregates(self, **kw):
        return {"totali": {"finanziamento": 400000.0}}

    async def fake_search(self, **kw):
        return {"total": 3, "results": _PROJECTS}

    async def noop_aenter(self):
        return self

    async def noop_aexit(self, *exc):
        return None

    monkeypatch.setattr(OpenCoesioneClient, "territorial_aggregates", fake_aggregates)
    monkeypatch.setattr(OpenCoesioneClient, "search_projects", fake_search)
    monkeypatch.setattr(OpenCoesioneClient, "__aenter__", noop_aenter)
    monkeypatch.setattr(OpenCoesioneClient, "__aexit__", noop_aexit)

    out = await fetch_investments(cod_comune="072021")
    assert out["total"] == 3
    assert len(out["projects"]) == 3
    assert out["aggregates"]["totali"]["finanziamento"] == 400000.0
