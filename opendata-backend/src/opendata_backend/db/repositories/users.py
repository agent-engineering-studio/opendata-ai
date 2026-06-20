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


async def get_by_clerk_id(session: AsyncSession, *, clerk_user_id: str) -> User | None:
    res = await session.execute(
        select(User).where(User.clerk_user_id == clerk_user_id, User.deleted_at.is_(None))
    )
    return res.scalar_one_or_none()


async def set_byok(
    session: AsyncSession,
    *,
    clerk_user_id: str,
    provider: str,
    key_encrypted: str,
    model: str | None = None,
    email: str | None = None,
) -> User:
    """Store (or replace) the user's BYOK credential. Creates the user row if
    absent (a JWT-authenticated user may not have a row yet — webhook lag)."""
    user = await get_or_create(session, clerk_user_id=clerk_user_id, email=email)
    user.byok_provider = provider
    user.byok_key_encrypted = key_encrypted
    user.byok_model = model
    user.updated_at = datetime.now(tz=timezone.utc)
    await session.flush()
    return user


async def clear_byok(session: AsyncSession, *, clerk_user_id: str) -> None:
    user = await get_by_clerk_id(session, clerk_user_id=clerk_user_id)
    if user is None:
        return
    user.byok_provider = None
    user.byok_key_encrypted = None
    user.byok_model = None
    user.updated_at = datetime.now(tz=timezone.utc)
    await session.flush()


async def soft_delete(session: AsyncSession, *, clerk_user_id: str) -> None:
    res = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = res.scalar_one_or_none()
    if user is None:
        return
    user.deleted_at = datetime.now(tz=timezone.utc)
    await session.flush()


async def bind_stripe_customer(
    session: AsyncSession,
    *,
    stripe_customer_id: str,
    clerk_user_id: str | None = None,
    email: str | None = None,
) -> User | None:
    """Bind a Stripe customer id to a user, found by clerk id then email.

    Called from `checkout.session.completed` — the only Stripe event carrying
    both our reference (`client_reference_id`) and the customer. Returns None
    when no user matches; the caller acks anyway so Stripe doesn't retry.
    """
    user = None
    if clerk_user_id:
        res = await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))
        user = res.scalar_one_or_none()
    if user is None and email:
        res = await session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        user = res.scalars().first()
    if user is None:
        return None
    if user.stripe_customer_id != stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
        user.updated_at = datetime.now(tz=timezone.utc)
        await session.flush()
    return user


async def set_tier_by_customer(
    session: AsyncSession,
    *,
    stripe_customer_id: str,
    tier: str,
) -> User | None:
    """Set `subscription_tier` for the user bound to `stripe_customer_id`.

    Returns None if no user is bound yet (a subscription event arrived before
    the checkout binding) — the caller acks; a later subscription.updated
    reconciles once the binding exists.
    """
    res = await session.execute(
        select(User).where(User.stripe_customer_id == stripe_customer_id)
    )
    user = res.scalar_one_or_none()
    if user is None:
        return None
    if user.subscription_tier != tier:
        user.subscription_tier = tier
        user.updated_at = datetime.now(tz=timezone.utc)
        await session.flush()
    return user
