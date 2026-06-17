"""Test ApriQui AI (Fase 3, F1): scoring puro + run su SQLite, spiegazione fallback."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from types import SimpleNamespace

from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.db.repositories import territory as repo
from opendata_backend.usecases.apriqui import run_apriqui, score_categories

AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


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


def test_score_categories_basic() -> None:
    rows = score_categories(
        business={"restaurant": 60, "supermarket": 1, "pharmacy": 1},
        features={"walkability_proxy": 60, "service_accessibility_score": 40,
                  "family_friendly_pois": 10, "tourist_stay_proxy": 5},
        population=27889,
    )
    assert len(rows) == 10
    assert all(0.0 <= r["score"] <= 100.0 for r in rows)
    assert rows == sorted(rows, key=lambda r: r["score"], reverse=True)
    # il supermercato (poco saturo) batte il ristorante (molto saturo) a parità di profilo?
    by = {r["category"]: r for r in rows}
    assert by["Supermercato"]["opportunity"] > by["Ristorante"]["opportunity"]


async def test_run_apriqui_with_explanation(session: AsyncSession) -> None:
    place = await repo.upsert_place(session, istat_code="072021", name="Gioia del Colle")
    await repo.upsert_feature_store(
        session, place_id=place.id,
        features={
            "profile": {"business": {"restaurant": 30, "supermarket": 2, "totale": 120}},
            "features": {"walkability_proxy": 70, "service_accessibility_score": 50,
                         "family_friendly_pois": 20, "tourist_stay_proxy": 8},
        }, computed_at=AT,
    )
    session.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle", popolazione=27889))
    await session.commit()

    out = await run_apriqui(session, istat_codes=["072021"], settings=SimpleNamespace(claude_model="claude-sonnet-4-6"))
    assert len(out["locations"]) == 1
    loc = out["locations"][0]
    assert loc["name"] == "Gioia del Colle"
    assert len(loc["categories"]) == 10
    assert len(loc["top"]) == 3
    assert out["explanation"]  # fallback deterministico


async def test_run_apriqui_comparison(session: AsyncSession) -> None:
    for code, name in [("072021", "Gioia del Colle"), ("072006", "Bari")]:
        p = await repo.upsert_place(session, istat_code=code, name=name)
        await repo.upsert_feature_store(
            session, place_id=p.id,
            features={"profile": {"business": {"restaurant": 5}}, "features": {}}, computed_at=AT,
        )
    await session.commit()
    out = await run_apriqui(session, istat_codes=["072021", "072006"],
                            settings=SimpleNamespace(claude_model="claude-sonnet-4-6"))
    assert len(out["locations"]) == 2
