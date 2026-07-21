"""Tests for the Clerk auth dependency.

Covers the dev-mode bypass, missing/invalid Bearer paths and the happy path
end-to-end through `require_user` with a stubbed `verify_clerk_token`.
"""

from __future__ import annotations

import time

import jwt
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
    with pytest.raises(ClerkAuthError, match="OIDC_ISSUER"):
        await clerk_module.verify_clerk_token("anything", settings=settings)


def test_oidc_issuer_alias_is_idp_agnostic() -> None:
    # The canonical name and the legacy Clerk name populate the same field, so
    # a self-hosted Keycloak issuer configures the backend identically.
    kc = "https://sso.regione.example/realms/opendata"
    assert Settings(oidc_issuer=kc).oidc_issuer == kc  # type: ignore[call-arg]
    assert Settings(clerk_jwt_issuer=kc).oidc_issuer == kc  # type: ignore[call-arg]
    # Audience is opt-in (Clerk omits it; Keycloak issues one).
    assert Settings().oidc_audience is None  # type: ignore[call-arg]


async def test_verify_enforces_audience_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # Real RS256 verification against a locally-generated key, with the JWKS
    # client stubbed to return that key. Exercises the optional `aud` check.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    class _FakeSigningKey:
        def __init__(self, pub):
            self.key = pub

    class _FakeJWKClient:
        def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
            return _FakeSigningKey(key.public_key())

    monkeypatch.setattr(clerk_module, "_jwks_client", lambda issuer, ttl: _FakeJWKClient())

    issuer = "https://sso.regione.example/realms/opendata"
    settings = Settings(  # type: ignore[call-arg]
        auth_enabled=True, oidc_issuer=issuer, oidc_audience="opendata-backend"
    )
    now = int(time.time())
    base = {"iss": issuer, "sub": "kc_user_1", "exp": now + 3600}

    good = jwt.encode({**base, "aud": "opendata-backend"}, priv_pem, algorithm="RS256")
    user = await clerk_module.verify_clerk_token(good, settings=settings)
    assert user.subject == "kc_user_1"

    wrong = jwt.encode({**base, "aud": "someone-else"}, priv_pem, algorithm="RS256")
    with pytest.raises(ClerkAuthError, match="audience"):
        await clerk_module.verify_clerk_token(wrong, settings=settings)
