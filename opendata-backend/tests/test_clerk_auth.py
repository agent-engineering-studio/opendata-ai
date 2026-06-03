"""Tests for the Clerk auth dependency.

Covers the dev-mode bypass, missing/invalid Bearer paths and the happy path
end-to-end through `require_user` with a stubbed `verify_clerk_token`.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient

from opendata_backend.auth import ClerkAuthError, ClerkUser
from opendata_backend.auth import clerk as clerk_module
from opendata_backend.auth.dependencies import require_user
from opendata_backend.config import Settings, get_settings


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: ClerkUser = Depends(require_user)) -> dict:
        return {"subject": user.subject, "email": user.email}

    return app


def _override_settings(app: FastAPI, settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: settings


def test_dev_bypass_when_auth_disabled() -> None:
    settings = Settings(auth_enabled=False)  # type: ignore[call-arg]
    app = _app()
    _override_settings(app, settings)

    res = TestClient(app).get("/whoami")
    assert res.status_code == 200
    assert res.json()["subject"] == "dev-user"


def test_missing_bearer_returns_401() -> None:
    settings = Settings(  # type: ignore[call-arg]
        auth_enabled=True,
        clerk_jwt_issuer="https://example.clerk.accounts.dev",
    )
    app = _app()
    _override_settings(app, settings)

    res = TestClient(app).get("/whoami")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.headers.get("WWW-Authenticate") == "Bearer"


def test_invalid_bearer_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(  # type: ignore[call-arg]
        auth_enabled=True,
        clerk_jwt_issuer="https://example.clerk.accounts.dev",
    )
    app = _app()
    _override_settings(app, settings)

    async def _fail(token: str, *, settings) -> ClerkUser:
        raise ClerkAuthError("token expired")

    # Patch the symbol used INSIDE the dependency module.
    monkeypatch.setattr(
        "opendata_backend.auth.dependencies.verify_clerk_token",
        _fail,
    )

    res = TestClient(app).get("/whoami", headers={"Authorization": "Bearer fake"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    assert res.json()["detail"] == "token expired"


def test_valid_bearer_returns_user(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(  # type: ignore[call-arg]
        auth_enabled=True,
        clerk_jwt_issuer="https://example.clerk.accounts.dev",
    )
    app = _app()
    _override_settings(app, settings)

    async def _ok(token: str, *, settings) -> ClerkUser:
        assert token == "ok-token"
        return ClerkUser(subject="user_42", email="x@y.z", claims={})

    monkeypatch.setattr(
        "opendata_backend.auth.dependencies.verify_clerk_token",
        _ok,
    )

    res = TestClient(app).get("/whoami", headers={"Authorization": "Bearer ok-token"})
    assert res.status_code == 200
    assert res.json() == {"subject": "user_42", "email": "x@y.z"}


async def test_verify_rejects_without_issuer_setting() -> None:
    clerk_module._reset_jwks_cache()
    settings = Settings(auth_enabled=True, clerk_jwt_issuer=None)  # type: ignore[call-arg]
    with pytest.raises(ClerkAuthError, match="CLERK_JWT_ISSUER"):
        await clerk_module.verify_clerk_token("anything", settings=settings)
