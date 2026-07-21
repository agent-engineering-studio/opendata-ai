"""OIDC JWT verification (IdP-agnostic).

Standard OpenID Connect token verification — works with ANY compliant issuer
(self-hosted Keycloak/Authentik, or Clerk). The backend never depends on a
specific vendor SDK; it only needs the issuer URL (`settings.oidc_issuer`):

1. Fetch the issuer's JWKS at `${issuer}/.well-known/jwks.json` and cache it
   in-process (issuers rotate keys periodically; a few-minute TTL is fine).
2. Decode the bearer token's header to pick the `kid` to use.
3. Verify the signature with PyJWT against the matching JWK, and check the
   standard claims (`iss`, `exp`, `sub`, and `aud` when `oidc_audience` is set).

Audience is validated only when `settings.oidc_audience` is configured
(Keycloak clients issue an `aud`; Clerk does not by default) — otherwise it is
skipped, preserving back-compat with the previous Clerk-only setup.

The identity type is named `ClerkUser` and the entry point `verify_clerk_token`
for historical reasons; `verify_oidc_token` is exported as the preferred alias.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from ..config import Settings


class ClerkAuthError(Exception):
    """Raised for any JWT-validation failure surfaced to the caller as HTTP 401."""


@dataclass(frozen=True)
class ClerkUser:
    """Minimal identity surface exposed to handlers.

    `subject` is Clerk's user id (e.g. `user_2qXyZ…`) and is the value to use
    as a foreign key in our own tables (step 4).
    """

    subject: str
    email: str | None
    claims: dict[str, Any]

    @property
    def subscription_tier(self) -> str:
        """Subscription tier driving rate limits / access gating.

        For API-key auth it is read from the owning user row; for Clerk JWTs
        it can be surfaced via a `subscription_tier` claim (Clerk JWT template
        / publicMetadata). Defaults to "free" when absent.
        """
        tier = self.claims.get("subscription_tier")
        return tier if isinstance(tier, str) and tier else "free"

    @property
    def auth_method(self) -> str:
        """How this identity authenticated: "clerk", "api_key" or "dev"."""
        method = self.claims.get("auth_method")
        return method if isinstance(method, str) and method else "clerk"

    @property
    def role(self) -> str:
        """RBAC role, populated by `roles.resolve_role` into `claims["role"]`.

        Authorization source of truth is `opendata.users.role`, not the token —
        this only surfaces the value once a `require_role` dependency has run.
        Defaults to "cittadino" (least privilege) when unresolved.
        """
        r = self.claims.get("role")
        return r if isinstance(r, str) and r else "cittadino"


# JWKS clients are keyed by issuer so swapping environments at test time
# doesn't poison the cache.
_jwks_cache: dict[str, tuple[PyJWKClient, float]] = {}


def _jwks_client(issuer: str, ttl_seconds: int) -> PyJWKClient:
    cached = _jwks_cache.get(issuer)
    now = time.time()
    if cached is not None and now - cached[1] < ttl_seconds:
        return cached[0]
    jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"
    client = PyJWKClient(jwks_url, cache_keys=True, lifespan=ttl_seconds)
    _jwks_cache[issuer] = (client, now)
    return client


def _reset_jwks_cache() -> None:
    """Test hook — clear the cached JWKS clients."""
    _jwks_cache.clear()


async def verify_clerk_token(token: str, *, settings: Settings) -> ClerkUser:
    if not settings.oidc_issuer:
        raise ClerkAuthError(
            "OIDC_ISSUER (or the legacy CLERK_JWT_ISSUER) is not configured on the backend"
        )

    try:
        client = _jwks_client(settings.oidc_issuer, settings.oidc_jwks_cache_seconds)
        signing_key = client.get_signing_key_from_jwt(token).key
    except httpx.HTTPError as exc:
        raise ClerkAuthError(f"could not fetch JWKS: {exc}") from exc
    except jwt.PyJWKClientError as exc:
        raise ClerkAuthError(f"unknown signing key: {exc}") from exc
    except jwt.exceptions.DecodeError as exc:
        raise ClerkAuthError(f"malformed token: {exc}") from exc

    # Validate `aud` only when an expected audience is configured; otherwise
    # skip it (Clerk omits `aud` by default).
    require = ["exp", "iss", "sub"]
    if settings.oidc_audience:
        require.append("aud")
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            options={"require": require, "verify_aud": bool(settings.oidc_audience)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ClerkAuthError("token expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise ClerkAuthError("token issuer mismatch") from exc
    except jwt.InvalidAudienceError as exc:
        raise ClerkAuthError("token audience mismatch") from exc
    except jwt.InvalidTokenError as exc:
        raise ClerkAuthError(f"invalid token: {exc}") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ClerkAuthError("token missing 'sub' claim")

    email = claims.get("email")
    if not isinstance(email, str):
        email = None
    return ClerkUser(subject=subject, email=email, claims=claims)


# Preferred, IdP-agnostic name for the verification entry point. `verify_clerk_token`
# is kept as the implementation symbol (imported by the auth dependency and
# monkeypatched in tests) to avoid churn; both refer to the same coroutine.
verify_oidc_token = verify_clerk_token
