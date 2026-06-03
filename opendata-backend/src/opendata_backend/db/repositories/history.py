"""Search history — chronological log of /datasets/search queries per user."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import History


async def append(
    session: AsyncSession,
    *,
    user_id: int,
    query: str,
    response_summary: str | None = None,
) -> History:
    entry = History(user_id=user_id, query=query, response_summary=response_summary)
    session.add(entry)
    await session.flush()
    return entry


async def list_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int = 50,
) -> list[History]:
    res = await session.execute(
        select(History)
        .where(History.user_id == user_id)
        .order_by(History.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())
