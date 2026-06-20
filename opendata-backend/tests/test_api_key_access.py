"""Access control: API-key authentication, key lifecycle, tier rate limits,
and A2A endpoint protection."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from opendata_backend.auth import ClerkAuthError, authenticate_credentials
from opendata_backend.config import Settings, rate_limit_for
from opendata_backend.db.models import Base
from opendata_backend.db.repositories import api_keys as api_keys_repo
from opendata_backend.db.repositories import users as users_repo


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


# ── repository layer ─────────────────────────────────────────────────────


async def test_authenticate_resolves_user_and_stamps_last_used(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="user_a")
        _, token = await api_keys_repo.generate(s, user_id=user.id, name="ci")
        await s.commit()

    async with sqlite_factory() as s:
        resolved = await api_keys_repo.authenticate(s, token=token)
        assert resolved is not None
        key, owner = resolved
        assert owner.clerk_user_id == "user_a"
        assert key.last_used_at is not None
        await s.commit()


async def test_revoked_key_no_longer_authenticates(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="user_b")
        row, token = await api_keys_repo.generate(s, user_id=user.id, name="tmp")
        await s.commit()
        ok = await api_keys_repo.revoke(s, user_id=user.id, key_id=row.id)
        assert ok is True
        await s.commit()

    async with sqlite_factory() as s:
        assert await api_keys_repo.authenticate(s, token=token) is None


async def test_revoke_rejects_other_users_key(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        owner = await users_repo.get_or_create(s, clerk_user_id="owner")
        attacker = await users_repo.get_or_create(s, clerk_user_id="attacker")
        row, _ = await api_keys_repo.generate(s, user_id=owner.id, name="k")
        await s.commit()
        # Attacker cannot revoke a key they don't own.
        assert await api_keys_repo.revoke(s, user_id=attacker.id, key_id=row.id) is False


async def test_list_for_user_newest_first(sqlite_factory) -> None:
    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="user_c")
        await api_keys_repo.generate(s, user_id=user.id, name="one")
        await api_keys_repo.generate(s, user_id=user.id, name="two")
        await s.commit()
        rows = await api_keys_repo.list_for_user(s, user_id=user.id)
        assert {r.name for r in rows} == {"one", "two"}


# ── authenticate_credentials (shared by require_user + A2A middleware) ─────


async def test_credentials_accept_api_key_via_bearer(sqlite_factory, monkeypatch) -> None:
    from opendata_backend.db import session as db_session

    monkeypatch.setattr(db_session, "_factory", sqlite_factory)

    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="user_d")
        user.subscription_tier = "pro"
        _, token = await api_keys_repo.generate(s, user_id=user.id, name="cli")
        await s.commit()

    settings = Settings(auth_enabled=True)  # type: ignore[call-arg]
    who = await authenticate_credentials(
        authorization=f"Bearer {token}", api_key_header=None, settings=settings
    )
    assert who.subject == "user_d"
    assert who.auth_method == "api_key"
    assert who.subscription_tier == "pro"


async def test_credentials_accept_api_key_via_header(sqlite_factory, monkeypatch) -> None:
    from opendata_backend.db import session as db_session

    monkeypatch.setattr(db_session, "_factory", sqlite_factory)

    async with sqlite_factory() as s:
        user = await users_repo.get_or_create(s, clerk_user_id="user_e")
        _, token = await api_keys_repo.generate(s, user_id=user.id, name="hdr")
        await s.commit()

    settings = Settings(auth_enabled=True)  # type: ignore[call-arg]
    who = await authenticate_credentials(
        authorization=None, api_key_header=token, settings=settings
    )
    assert who.subject == "user_e"


async def test_credentials_reject_unknown_api_key(sqlite_factory, monkeypatch) -> None:
    from opendata_backend.db import session as db_session

    monkeypatch.setattr(db_session, "_factory", sqlite_factory)
    settings = Settings(auth_enabled=True)  # type: ignore[call-arg]
    with pytest.raises(ClerkAuthError):
        await authenticate_credentials(
            authorization="Bearer od_does_not_exist",
            api_key_header=None,
            settings=settings,
        )


async def test_credentials_dev_bypass() -> None:
    settings = Settings(auth_enabled=False)  # type: ignore[call-arg]
    who = await authenticate_credentials(
        authorization=None, api_key_header=None, settings=settings
    )
    assert who.subject == "dev-user"
    assert who.auth_method == "dev"


# ── tier-aware rate limit resolution ───────────────────────────────────────


def test_rate_limit_for_tiers() -> None:
    settings = Settings(  # type: ignore[call-arg]
        rate_limit_per_minute=60,
        rate_limit_tiers="pro=600, enterprise=6000",
    )
    assert rate_limit_for("free", settings) == 60
    assert rate_limit_for(None, settings) == 60
    assert rate_limit_for("pro", settings) == 600
    assert rate_limit_for("enterprise", settings) == 6000
    # Unknown tier falls back to the baseline.
    assert rate_limit_for("mystery", settings) == 60


def test_rate_limit_for_malformed_entry_falls_back() -> None:
    settings = Settings(  # type: ignore[call-arg]
        rate_limit_per_minute=42,
        rate_limit_tiers="pro=notanumber",
    )
    assert rate_limit_for("pro", settings) == 42


# ── A2A auth middleware ────────────────────────────────────────────────────


def _a2a_app(settings: Settings):
    from fastapi import FastAPI

    from opendata_backend.a2a import register_a2a_auth

    app = FastAPI()

    @app.post("/a2a/")
    async def rpc() -> dict:
        return {"ok": True}

    @app.get("/.well-known/agent-card.json")
    async def card() -> dict:
        return {"name": "opendata"}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    register_a2a_auth(app, settings)
    return app


def test_a2a_rpc_requires_credentials() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(_a2a_app(Settings(auth_enabled=True, a2a_enabled=True)))  # type: ignore[call-arg]
    # JSON-RPC without credentials → 401.
    assert client.post("/a2a/", json={}).status_code == 401
    # Discovery stays public.
    assert client.get("/.well-known/agent-card.json").status_code == 200
    # Unrelated paths are untouched.
    assert client.get("/health").status_code == 200


def test_a2a_dev_bypass_allows_rpc() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(_a2a_app(Settings(auth_enabled=False, a2a_enabled=True)))  # type: ignore[call-arg]
    assert client.post("/a2a/", json={}).status_code == 200
