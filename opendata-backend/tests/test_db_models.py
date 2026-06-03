"""Smoke tests for the ORM layer.

Uses an in-memory SQLite (with the asyncio driver) so the suite stays
self-contained — no Postgres needed for unit tests. SQLite doesn't honour
the `opendata` schema, so we mount the metadata onto the default schema
just for the test session.
"""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import ApiKey, Base, Favorite, History, User
from opendata_backend.db.repositories import api_keys as api_keys_repo
from opendata_backend.db.repositories import classifications as classifications_repo
from opendata_backend.db.repositories import favorites as favorites_repo
from opendata_backend.db.repositories import history as history_repo
from opendata_backend.db.repositories import users as users_repo


def _strip_schema(metadata: MetaData) -> None:
    """SQLite doesn't honour PostgreSQL `schema=` kwargs — strip them off."""
    for table in metadata.tables.values():
        table.schema = None


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


async def test_user_upsert(session: AsyncSession) -> None:
    u1 = await users_repo.get_or_create(
        session, clerk_user_id="user_1", email="a@b.c"
    )
    u2 = await users_repo.get_or_create(
        session, clerk_user_id="user_1", email="new@b.c"
    )
    assert u1.id == u2.id
    assert u2.email == "new@b.c"


async def test_favorite_lifecycle(session: AsyncSession) -> None:
    user = await users_repo.get_or_create(session, clerk_user_id="user_1")
    fav = await favorites_repo.add(
        session,
        user_id=user.id,
        source="ckan",
        dataset_id="d1",
        dataset_name="Ds 1",
    )
    assert fav.id is not None

    rows = await favorites_repo.list_for_user(session, user_id=user.id)
    assert len(rows) == 1
    assert rows[0].dataset_name == "Ds 1"

    n = await favorites_repo.remove(
        session, user_id=user.id, source="ckan", dataset_id="d1"
    )
    assert n == 1


async def test_history_append_and_list(session: AsyncSession) -> None:
    user = await users_repo.get_or_create(session, clerk_user_id="user_2")
    await history_repo.append(session, user_id=user.id, query="popolazione milano")
    await history_repo.append(session, user_id=user.id, query="energia eolica")

    rows = await history_repo.list_for_user(session, user_id=user.id)
    assert [r.query for r in rows] == ["energia eolica", "popolazione milano"]


async def test_api_key_generate_returns_clear_token_once(session: AsyncSession) -> None:
    user = await users_repo.get_or_create(session, clerk_user_id="user_3")
    row, token = await api_keys_repo.generate(session, user_id=user.id, name="ci")
    assert token.startswith("od_")
    # The token should NOT be persisted in clear-text.
    assert row.key_hash != token
    # And we can verify it back.
    matched = await api_keys_repo.verify(session, token=token)
    assert matched is not None
    assert matched.id == row.id


async def test_classifications_cache_key_is_deterministic() -> None:
    a = classifications_repo.taxonomy_hash(["energy", "transport"])
    b = classifications_repo.taxonomy_hash(["transport", "energy"])
    assert a == b
