"""Stripe webhook: signature gating, customer↔user binding, tier sync."""

from __future__ import annotations

import json

import pytest
import stripe
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import MetaData, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from opendata_backend.config import Settings, get_settings, tier_for_price
from opendata_backend.db.models import Base, User
from opendata_backend.db.repositories import users as users_repo
from opendata_backend.routers import webhooks


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture
async def sqlite_factory():
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def _app(settings: Settings, sqlite_factory, monkeypatch) -> FastAPI:
    from opendata_backend.db import session as db_session

    monkeypatch.setattr(db_session, "_factory", sqlite_factory)
    app = FastAPI()
    app.include_router(webhooks.router)
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


# ── config: price → tier map ───────────────────────────────────────────────


def test_tier_for_price() -> None:
    settings = Settings(  # type: ignore[call-arg]
        stripe_price_tiers="price_aaa=sostenitore, price_bbb=pro, price_ccc=team",
    )
    assert tier_for_price("price_aaa", settings) == "sostenitore"
    assert tier_for_price("price_bbb", settings) == "pro"
    assert tier_for_price("price_ccc", settings) == "team"
    # Unknown price / empty map / None → None (caller falls back to "free").
    assert tier_for_price("price_zzz", settings) is None
    assert tier_for_price(None, settings) is None
    assert tier_for_price("price_aaa", Settings()) is None  # type: ignore[call-arg]


# ── repository: bind + set tier by customer ─────────────────────────────────


async def test_bind_prefers_clerk_id_then_email(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        await users_repo.get_or_create(s, clerk_user_id="u1", email="a@b.it")
        await users_repo.get_or_create(s, clerk_user_id="u2", email="c@d.it")
        await s.commit()

    async with sqlite_factory() as s:
        by_id = await users_repo.bind_stripe_customer(
            s, stripe_customer_id="cus_1", clerk_user_id="u1"
        )
        by_email = await users_repo.bind_stripe_customer(
            s, stripe_customer_id="cus_2", email="c@d.it"
        )
        assert by_id is not None and by_id.stripe_customer_id == "cus_1"
        assert by_email is not None and by_email.stripe_customer_id == "cus_2"
        # No match → None (caller acks anyway).
        assert await users_repo.bind_stripe_customer(
            s, stripe_customer_id="cus_x", email="nobody@nope.it"
        ) is None


async def test_set_tier_by_customer_unbound_returns_none(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        assert await users_repo.set_tier_by_customer(
            s, stripe_customer_id="cus_unknown", tier="pro"
        ) is None


# ── endpoint: signature gating ──────────────────────────────────────────────


async def test_stripe_webhook_missing_secret_500(sqlite_factory, monkeypatch) -> None:
    settings = Settings()  # type: ignore[call-arg]  (no stripe_webhook_secret)
    async with _client(_app(settings, sqlite_factory, monkeypatch)) as client:
        r = await client.post("/webhooks/stripe", json={})
    assert r.status_code == 500


async def test_stripe_webhook_bad_signature_400(sqlite_factory, monkeypatch) -> None:
    settings = Settings(stripe_webhook_secret="whsec_test")  # type: ignore[call-arg]

    def _boom(**_kw):
        raise stripe.error.SignatureVerificationError("bad sig", "t=1,v1=deadbeef")

    monkeypatch.setattr(stripe.Webhook, "construct_event", _boom)
    async with _client(_app(settings, sqlite_factory, monkeypatch)) as client:
        r = await client.post("/webhooks/stripe", json={"type": "x"})
    assert r.status_code == 400


# ── endpoint: happy paths ───────────────────────────────────────────────────


def _bypass_signature(monkeypatch) -> None:
    # construct_event "verifies" by just parsing the body (signature bypassed).
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda payload, sig_header, secret: json.loads(payload),
    )


async def test_checkout_then_subscription_sets_tier(sqlite_factory, monkeypatch) -> None:
    settings = Settings(  # type: ignore[call-arg]
        stripe_webhook_secret="whsec_test",
        stripe_price_tiers="price_pro=pro",
    )
    _bypass_signature(monkeypatch)

    async with sqlite_factory() as s:
        await users_repo.get_or_create(s, clerk_user_id="u1", email="a@b.it")
        await s.commit()

    async with _client(_app(settings, sqlite_factory, monkeypatch)) as client:
        # 1. checkout.session.completed binds cus_1 ↔ u1 (via client_reference_id).
        r = await client.post(
            "/webhooks/stripe",
            json={
                "id": "evt_1",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_1",
                        "client_reference_id": "u1",
                        "customer_details": {"email": "a@b.it"},
                    }
                },
            },
        )
        assert r.status_code == 200

        # 2. customer.subscription.updated (active, price_pro) → tier "pro".
        r = await client.post(
            "/webhooks/stripe",
            json={
                "id": "evt_2",
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "customer": "cus_1",
                        "status": "active",
                        "items": {"data": [{"price": {"id": "price_pro"}}]},
                    }
                },
            },
        )
        assert r.status_code == 200

    async with sqlite_factory() as s:
        res = await s.execute(select(User).where(User.clerk_user_id == "u1"))
        user = res.scalar_one()
    assert user.stripe_customer_id == "cus_1"
    assert user.subscription_tier == "pro"


async def test_subscription_deleted_reverts_to_free(sqlite_factory, monkeypatch) -> None:
    settings = Settings(stripe_webhook_secret="whsec_test")  # type: ignore[call-arg]
    _bypass_signature(monkeypatch)

    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="u9", email="x@y.it")
        user.stripe_customer_id = "cus_9"
        user.subscription_tier = "pro"
        await s.commit()

    async with _client(_app(settings, sqlite_factory, monkeypatch)) as client:
        r = await client.post(
            "/webhooks/stripe",
            json={
                "id": "evt_9",
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": "cus_9", "status": "canceled"}},
            },
        )
        assert r.status_code == 200

    async with sqlite_factory() as s:
        res = await s.execute(select(User).where(User.clerk_user_id == "u9"))
        user = res.scalar_one()
    assert user.subscription_tier == "free"
