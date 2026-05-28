"""Programmatic API keys — store only the SHA-256 hash, expose the token once."""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiKey


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
    from sqlalchemy import select

    res = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == _hash(token), ApiKey.revoked_at.is_(None))
    )
    return res.scalar_one_or_none()
