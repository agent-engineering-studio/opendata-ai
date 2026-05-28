"""User aggregate — upsert from Clerk webhook events, lookup by clerk_user_id."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


async def get_or_create(
    session: AsyncSession,
    *,
    clerk_user_id: str,
    email: str | None = None,
    display_name: str | None = None,
) -> User:
    res = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = res.scalar_one_or_none()
    if user is not None:
        # Refresh tracked fields if Clerk-supplied values changed.
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if changed:
            user.updated_at = datetime.now(tz=timezone.utc)
            await session.flush()
        return user
    user = User(clerk_user_id=clerk_user_id, email=email, display_name=display_name)
    session.add(user)
    await session.flush()
    return user


async def soft_delete(session: AsyncSession, *, clerk_user_id: str) -> None:
    res = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = res.scalar_one_or_none()
    if user is None:
        return
    user.deleted_at = datetime.now(tz=timezone.utc)
    await session.flush()
