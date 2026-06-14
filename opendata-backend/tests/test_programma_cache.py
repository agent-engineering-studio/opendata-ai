"""Test della cache analisi /programma (F1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base, ComuneKnowledge
from opendata_backend.db.repositories import programma_cache as cache_repo


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture
async def sessionmaker_() -> async_sessionmaker:
    _strip_schema(Base.metadata)
    eng: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


def test_cache_key_normalises_tema_and_cicli_order() -> None:
    a = cache_repo.compute_cache_key(
        cod_comune="072006", tema="Energia", cicli=["2021-2027", "2014-2020"],
        modalita="completa", knowledge_version=0, prompt_version="v1",
    )
    b = cache_repo.compute_cache_key(
        cod_comune="072006", tema="energia", cicli=["2014-2020", "2021-2027"],
        modalita="completa", knowledge_version=0, prompt_version="v1",
    )
    assert a == b  # case del tema + ordine cicli irrilevanti


def test_cache_key_changes_with_knowledge_and_prompt_version() -> None:
    base = dict(cod_comune="072006", tema=None, cicli=None, modalita="completa")
    k0 = cache_repo.compute_cache_key(**base, knowledge_version=0, prompt_version="v1")
    assert k0 != cache_repo.compute_cache_key(**base, knowledge_version=1, prompt_version="v1")
    assert k0 != cache_repo.compute_cache_key(**base, knowledge_version=0, prompt_version="v2")


async def test_upsert_then_get_fresh_roundtrip(sessionmaker_) -> None:
    now = datetime.now(timezone.utc)
    key = "k1"
    async with sessionmaker_() as s:
        await cache_repo.upsert(
            s, cache_key=key, cod_comune="072006", tema=None, modalita="completa",
            knowledge_version=0, prompt_version="v1", scheda_json='{"x":1}',
            generato_il=now, expires_at=now + timedelta(days=30),
        )
        await s.commit()
    async with sessionmaker_() as s:
        row = await cache_repo.get_fresh(s, key, now=now)
        assert row is not None and row.scheda_json == '{"x":1}'


async def test_get_fresh_returns_none_when_expired(sessionmaker_) -> None:
    now = datetime.now(timezone.utc)
    async with sessionmaker_() as s:
        await cache_repo.upsert(
            s, cache_key="k2", cod_comune="072006", tema=None, modalita="completa",
            knowledge_version=0, prompt_version="v1", scheda_json="{}",
            generato_il=now, expires_at=now - timedelta(seconds=1),  # già scaduta
        )
        await s.commit()
    async with sessionmaker_() as s:
        assert await cache_repo.get_fresh(s, "k2", now=now) is None


async def test_knowledge_version_default_and_bump(sessionmaker_) -> None:
    async with sessionmaker_() as s:
        assert await cache_repo.get_knowledge_version(s, "072006") == 0  # default
        s.add(ComuneKnowledge(cod_comune="072006", version=3))
        await s.commit()
    async with sessionmaker_() as s:
        assert await cache_repo.get_knowledge_version(s, "072006") == 3
