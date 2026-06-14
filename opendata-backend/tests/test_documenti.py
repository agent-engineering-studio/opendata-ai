"""Test registro documenti PA (F2) + invalidazione cache via knowledge_version."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.repositories import documenti as documenti_repo
from opendata_backend.db.repositories import programma_cache as cache_repo


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture
async def sm() -> async_sessionmaker:
    _strip_schema(Base.metadata)
    eng: AsyncEngine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(eng, expire_on_commit=False)
    await eng.dispose()


async def test_create_list_delete_roundtrip(sm) -> None:
    async with sm() as s:
        await documenti_repo.create(
            s, cod_comune="072021", filename="delibera.pdf", kg_namespace="comune-072021",
            sha256="abc", mime_type="application/pdf", caricato_da="user_1", stato="ingerito",
        )
        await s.commit()
    async with sm() as s:
        rows = await documenti_repo.list_by_comune(s, "072021")
        assert len(rows) == 1 and rows[0].filename == "delibera.pdf"
        assert await documenti_repo.list_by_comune(s, "999999") == []
    async with sm() as s:
        doc = (await documenti_repo.list_by_comune(s, "072021"))[0]
        await documenti_repo.delete(s, doc)
        await s.commit()
    async with sm() as s:
        assert await documenti_repo.list_by_comune(s, "072021") == []


async def test_bump_knowledge_version_invalidates_cache_key(sm) -> None:
    base = dict(cod_comune="072021", tema=None, cicli=None, modalita="completa",
                prompt_version="v1")
    async with sm() as s:
        v0 = await cache_repo.get_knowledge_version(s, "072021")
        assert v0 == 0
        key_v0 = cache_repo.compute_cache_key(**base, knowledge_version=v0)
        v1 = await cache_repo.bump_knowledge_version(s, "072021")
        await s.commit()
        assert v1 == 1
    async with sm() as s:
        v = await cache_repo.get_knowledge_version(s, "072021")
        assert v == 1
        key_v1 = cache_repo.compute_cache_key(**base, knowledge_version=v)
    # La chiave cambia → la vecchia scheda in cache non viene più trovata.
    assert key_v0 != key_v1
