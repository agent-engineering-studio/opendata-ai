"""Programmatic API keys — store only the SHA-256 hash, expose the token once."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiKey, User


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def generate(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
) -> tuple[ApiKey, str]:
    """Create an API key for `user_id`. Returns (ApiKey row, clear-text token).

    The clear-text token is returned ONCE — the caller is responsible for
    surfacing it to the user; only `key_hash` is persisted.
    """
    token = "od_" + secrets.token_urlsafe(32)
    key = ApiKey(user_id=user_id, name=name, key_hash=_hash(token))
    session.add(key)
    await session.flush()
    return key, token


async def verify(session: AsyncSession, *, token: str) -> ApiKey | None:
    res = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == _hash(token), ApiKey.revoked_at.is_(None))
    )
    return res.scalar_one_or_none()


async def authenticate(
    session: AsyncSession, *, token: str
) -> tuple[ApiKey, User] | None:
    """Resolve a token to (ApiKey, owning User) and stamp `last_used_at`.

    Returns None when the token is unknown or revoked. The caller is expected
    to commit so the `last_used_at` touch is persisted.
    """
    key = await verify(session, token=token)
    if key is None:
        return None
    user = await session.get(User, key.user_id)
    if user is None:
        return None
    key.last_used_at = datetime.now(tz=timezone.utc)
    await session.flush()
    return key, user


async def list_for_user(session: AsyncSession, *, user_id: int) -> list[ApiKey]:
    """All keys for a user (active + revoked), newest first."""
    res = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(res.scalars().all())


async def revoke(session: AsyncSession, *, user_id: int, key_id: int) -> bool:
    """Soft-revoke a key the user owns. Returns False if not found / not theirs.

    Idempotent: re-revoking an already-revoked key returns False (nothing to
    do) so the endpoint can answer 404 without leaking other users' key ids.
    """
    res = await session.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == user_id,
            ApiKey.revoked_at.is_(None),
        )
    )
    key = res.scalar_one_or_none()
    if key is None:
        return False
    key.revoked_at = datetime.now(tz=timezone.utc)
    await session.flush()
    return True
