"""Test del livello value del backend: card, reuse, portfolio, narrativa, retro-compat."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base, Classification, Favorite
from opendata_backend.db.territory_models import DatasetQuality, Entity
from opendata_backend.orchestrator.parsing import Resource
from opendata_backend.value.cards import attach_value_cards, value_card_for_resource
from opendata_backend.value.impact import reuse_score
from opendata_backend.value.narrative import generate_narrative
from opendata_backend.value.portfolio import build_portfolio

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


# ── value card (retro-compatibilità) ────────────────────────────────


def test_resource_value_card_optional_and_retrocompat() -> None:
    r = Resource(name="Mobilità TPL", url="https://ex.it/tpl.csv", format="CSV")
    assert r.value_card is None                      # default → vecchi client invariati
    dump = r.model_dump()
    assert "value_card" in dump and dump["value_card"] is None


def test_value_card_for_resource_has_criteria() -> None:
    r = Resource(name="Mobilità TPL per comune", url="https://ex.it/tpl.geojson", format="GeoJSON",
                 description="Fermate e linee del trasporto pubblico locale per anno.")
    card = value_card_for_resource(r)
    assert {"socioeconomic", "audience_sme", "revenue", "combinability", "overall"} <= set(card)
    assert card["hvd_category"] == "mobility"


def test_attach_value_cards_populates_all() -> None:
    rs = [
        Resource(name="A", url="https://ex.it/a.csv", format="CSV"),
        Resource(name="B", url="https://ex.it/b.json", format="JSON"),
    ]
    n = attach_value_cards(rs)
    assert n == 2
    assert all(r.value_card is not None for r in rs)


# ── reuse / impact ──────────────────────────────────────────────────


async def test_reuse_score_from_platform_signals(session: AsyncSession) -> None:
    session.add_all([
        Favorite(user_id=1, source="ckan", dataset_id="d1", dataset_name="D1"),
        Favorite(user_id=2, source="ckan", dataset_id="d1", dataset_name="D1"),
        Classification(source="ckan", dataset_id="d1", taxonomy_hash="h", result={"x": 1}, model="m"),
    ])
    await session.commit()
    score = await reuse_score(session, source="ckan", dataset_id="d1")
    assert score == 60.0  # 2*25 + 1*10
    assert await reuse_score(session, source="ckan", dataset_id="unused") == 0.0


# ── portfolio ───────────────────────────────────────────────────────


async def test_portfolio_aggregates(session: AsyncSession) -> None:
    ent = Entity(name="Comune X", type="ente", region="Puglia")
    session.add(ent)
    await session.flush()
    session.add_all([
        DatasetQuality(entity_id=ent.id, source="ckan", dataset_id="d1", assessed_at=AT,
                       stars_5=3, license_open_bool=True, hvd_category="mobility", freshness_days=100),
        DatasetQuality(entity_id=ent.id, source="ckan", dataset_id="d2", assessed_at=AT,
                       stars_5=1, license_open_bool=False, hvd_category=None, freshness_days=900),
    ])
    await session.commit()

    pf = await build_portfolio(session, entity_id=ent.id)
    assert pf["count"] == 2
    assert pf["pct_hvd"] == 50.0
    assert pf["pct_open_license"] == 50.0
    assert pf["avg_freshness_days"] == 500.0
    assert pf["avg_reuse"] == 0.0  # nessun favorite/classification


async def test_portfolio_empty(session: AsyncSession) -> None:
    pf = await build_portfolio(session, entity_id=999)
    assert pf["count"] == 0
    assert pf["pct_hvd"] is None


# ── narrativa (fallback offline) ────────────────────────────────────


async def test_narrative_fallback_without_key() -> None:
    text = await generate_narrative(model="claude-sonnet-4-6", context={"title": "Dataset mobilità"})
    assert "Problema" in text and "Beneficiario" in text
