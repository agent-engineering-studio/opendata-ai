"""Per-IP / global rate-limit middleware helper tests (#235).

Exercises `shared.ip_ratelimit.check_request` directly with an explicit
`Settings` — both the in-process fallback (no Redis) and the Redis-backed path
(fakeredis) — plus the disabled case.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from opendata_backend.cache.state import set_redis
from opendata_backend.config import Settings
from opendata_backend.shared import ip_ratelimit


def _app(settings: Settings) -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def _mw(request, call_next):  # type: ignore[type-arg]
        retry = await ip_ratelimit.check_request(request, settings)
        if retry is not None:
            return JSONResponse(
                status_code=429, content={"detail": "rl"}, headers={"Retry-After": str(retry)}
            )
        return await call_next(request)

    @app.get("/x")
    async def x() -> dict:
        return {"ok": True}

    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean():
    ip_ratelimit._reset_local()
    set_redis(None)
    yield
    set_redis(None)


def test_ip_limit_blocks_in_process() -> None:
    client = _app(Settings(rate_limit_ip_per_minute=3))  # type: ignore[call-arg]
    for i in range(3):
        assert client.get("/x").status_code == 200, f"call {i}"
    res = client.get("/x")
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_disabled_when_zero() -> None:
    client = _app(Settings(rate_limit_ip_per_minute=0, rate_limit_global_per_minute=0))  # type: ignore[call-arg]
    for _ in range(50):
        assert client.get("/x").status_code == 200


def test_global_limit_independent_of_ip() -> None:
    # per-IP disabled, only the global cap applies
    client = _app(Settings(rate_limit_ip_per_minute=0, rate_limit_global_per_minute=2))  # type: ignore[call-arg]
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429


def test_ip_limit_redis_backed() -> None:
    import fakeredis.aioredis

    set_redis(fakeredis.aioredis.FakeRedis(decode_responses=True))
    client = _app(Settings(rate_limit_ip_per_minute=2))  # type: ignore[call-arg]
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429


async def test_forwarded_for_is_used() -> None:
    from starlette.requests import Request

    settings = Settings(rate_limit_ip_per_minute=1)  # type: ignore[call-arg]

    def _req(xff: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/x",
                "headers": [(b"x-forwarded-for", xff.encode())],
                "client": ("10.0.0.1", 1234),
            }
        )

    # Two distinct forwarded IPs get independent budgets even behind one proxy.
    assert await ip_ratelimit.check_request(_req("203.0.113.7"), settings) is None
    assert await ip_ratelimit.check_request(_req("203.0.113.7"), settings) is not None
    assert await ip_ratelimit.check_request(_req("203.0.113.9"), settings) is None
