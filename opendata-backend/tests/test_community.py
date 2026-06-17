"""Test community micro-servizio (Fase 4, J1): thread/post/moderazione/ruoli."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.db.models import Base
from opendata_backend.db.repositories import community as repo


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


async def test_thread_and_posts_lifecycle(session: AsyncSession) -> None:
    th = await repo.create_thread(session, istat_code="072021", topic_type="opera",
                                  title="Nuova scuola", created_by="user_1")
    await session.commit()
    threads = await repo.list_threads(session, "072021")
    assert [t.id for t in threads] == [th.id]

    p1 = await repo.create_post(session, thread_id=th.id, body="Ottimo!", author="user_2")
    await repo.create_post(session, thread_id=th.id, body="Spam", author="user_3")
    await session.commit()
    assert len(await repo.list_posts(session, th.id)) == 2

    # moderazione: nascondi un post
    await repo.moderate_post(session, p1.id, status="hidden")
    await session.commit()
    visible = await repo.list_posts(session, th.id)
    assert len(visible) == 1
    assert len(await repo.list_posts(session, th.id, include_hidden=True)) == 2


async def test_roles(session: AsyncSession) -> None:
    assert await repo.get_role(session, clerk_user_id="u1", istat_code="072021") == "cittadino"
    await repo.set_role(session, clerk_user_id="u1", istat_code="072021", role="moderatore")
    await session.commit()
    assert await repo.get_role(session, clerk_user_id="u1", istat_code="072021") == "moderatore"
    assert repo.is_moderator("moderatore") is True
    assert repo.is_moderator("cittadino") is False
    with pytest.raises(ValueError):
        await repo.set_role(session, clerk_user_id="u1", istat_code="072021", role="re")
