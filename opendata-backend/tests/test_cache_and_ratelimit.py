"""Cache + rate-limit unit tests backed by fakeredis."""

from __future__ import annotations

import pytest

from opendata_backend.cache import by_category as by_cat
from opendata_backend.cache import fetch as fetch_cache
from opendata_backend.cache.state import set_redis


@pytest.fixture
def fake_redis():
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis(client)
    try:
        yield client
    finally:
        set_redis(None)


async def test_fetch_cache_round_trip(fake_redis) -> None:
    await fetch_cache.set("https://example.com/data.csv", {"content": "a,b\n1,2", "size_bytes": 8})
    got = await fetch_cache.get("https://example.com/data.csv")
    assert got is not None
    assert got["content"] == "a,b\n1,2"


async def test_fetch_cache_miss_returns_none(fake_redis) -> None:
    assert await fetch_cache.get("https://example.com/unseen.csv") is None


async def test_by_category_cache_key_includes_region(fake_redis) -> None:
    await by_cat.set("energy", "https://dati.lombardia.it", "Milano", {"text": "milano"})
    await by_cat.set("energy", "https://dati.lombardia.it", "Bergamo", {"text": "bergamo"})
    a = await by_cat.get("energy", "https://dati.lombardia.it", "Milano")
    b = await by_cat.get("energy", "https://dati.lombardia.it", "Bergamo")
    assert a == {"text": "milano"}
    assert b == {"text": "bergamo"}


async def test_cache_noop_when_redis_unset() -> None:
    # No fixture used → redis is None
    set_redis(None)
    await fetch_cache.set("https://x.test/d.csv", {"content": "a"})
    assert await fetch_cache.get("https://x.test/d.csv") is None


async def test_rate_limit_blocks_above_threshold(fake_redis, monkeypatch) -> None:
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from opendata_backend.auth import ClerkUser
    from opendata_backend.auth import dependencies as auth_dep
    from opendata_backend.config import Settings, get_settings
    from opendata_backend.shared.ratelimit import enforce_rate_limit

    user = ClerkUser(subject="user_rl_test", email=None, claims={})

    async def _user(*args, **kwargs) -> ClerkUser:
        return user

    monkeypatch.setattr(auth_dep, "require_user", _user)

    settings = Settings(auth_enabled=False, rate_limit_per_minute=3)  # type: ignore[call-arg]

    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[auth_dep.require_user] = _user

    @app.get("/ping")
    async def ping(_: ClerkUser = Depends(enforce_rate_limit)) -> dict:
        return {"ok": True}

    client = TestClient(app)
    for i in range(3):
        assert client.get("/ping").status_code == 200, f"call {i}"
    res = client.get("/ping")
    assert res.status_code == 429
    assert "Retry-After" in res.headers
