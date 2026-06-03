"""Favorite dataset bookmarks — per user, scoped by (source, dataset_id)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Favorite


async def list_for_user(session: AsyncSession, *, user_id: int) -> list[Favorite]:
    res = await session.execute(
        select(Favorite).where(Favorite.user_id == user_id).order_by(Favorite.created_at.desc())
    )
    return list(res.scalars().all())


async def add(
    session: AsyncSession,
    *,
    user_id: int,
    source: str,
    dataset_id: str,
    dataset_name: str | None = None,
    metadata: dict | None = None,
) -> Favorite:
    stmt = (
        insert(Favorite)
        .values(
            user_id=user_id,
            source=source,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            metadata_=metadata,
        )
        # set_ keys are DB column names, not the Python attribute aliases.
        .on_conflict_do_update(
            constraint="uq_favorites_user_dataset",
            set_={"dataset_name": dataset_name, "metadata": metadata},
        )
        .returning(Favorite)
    )
    res = await session.execute(stmt)
    return res.scalar_one()


async def remove(
    session: AsyncSession,
    *,
    user_id: int,
    source: str,
    dataset_id: str,
) -> int:
    res = await session.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.source == source,
            Favorite.dataset_id == dataset_id,
        )
    )
    return res.rowcount or 0
