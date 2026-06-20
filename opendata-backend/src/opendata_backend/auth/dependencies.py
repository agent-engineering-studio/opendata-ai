"""FastAPI dependencies for authenticated endpoints.

Every application endpoint (everything except `/health`) declares
`user: ClerkUser = Depends(require_user)` so authentication is enforced
exactly the same way across routers.

Two credential types are accepted, unified into a single `ClerkUser`:

- **Clerk session JWT** — `Authorization: Bearer <jwt>` from the web UI.
- **Programmatic API key** — `Authorization: Bearer od_…` or `X-API-Key: od_…`
  for headless clients, MCP/A2A integrations and scripts. The key is resolved
  to its owning user, so everything downstream (rate-limit subject, favourites,
  history) keys off the same Clerk user id whichever credential was used.

When `settings.auth_enabled` is False (local dev) the dependency returns a
synthetic `_DEV_USER` instead of validating — there is no fallback to
anonymous access, just a clearly-named "dev mode" identity.

`authenticate_credentials` holds the shared resolution logic so the A2A auth
middleware (which mounts routes outside FastAPI's dependency graph) enforces
exactly the same rules.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import Settings, get_settings
from .clerk import ClerkAuthError, ClerkUser, verify_clerk_token

log = logging.getLogger("opendata-backend.auth")

# Treat HTTPBearer as optional so we can return a tailored 401 with the same
# {"detail": "..."} shape used elsewhere in the API.
_bearer = HTTPBearer(auto_error=False)

# Programmatic API keys carry this prefix (see repositories/api_keys.generate).
API_KEY_PREFIX = "od_"

# Used only when `auth_enabled=False`. Subject is recognisable in logs so
# nobody mistakes a dev-mode user id for a real Clerk subject.
_DEV_USER = ClerkUser(
    subject="dev-user",
    email="dev@local",
    claims={"dev_mode": True, "auth_method": "dev"},
)


async def _resolve_api_key(token: str, settings: Settings) -> ClerkUser:
    """Resolve an API key token to its owning user, stamping `last_used_at`.

    Raises `ClerkAuthError` (→ 401) when the database is unavailable, the key
    is unknown/revoked, or the owner has been soft-deleted.
    """
    # Imported lazily to keep the auth package free of DB import cycles.
    from ..db.repositories import api_keys as api_keys_repo
    from ..db.session import get_session_factory

    try:
        factory = get_session_factory()
    except RuntimeError as exc:  # DATABASE_URL not configured
        raise ClerkAuthError("API key authentication is unavailable") from exc

    async with factory() as session:
        resolved = await api_keys_repo.authenticate(session, token=token)
        if resolved is None:
            raise ClerkAuthError("invalid or revoked API key")
        key, user = resolved
        if user.deleted_at is not None:
            raise ClerkAuthError("API key owner is no longer active")
        await session.commit()
        return ClerkUser(
            subject=user.clerk_user_id,
            email=user.email,
            claims={
                "auth_method": "api_key",
                "api_key_id": key.id,
                "subscription_tier": user.subscription_tier,
            },
        )


async def authenticate_credentials(
    *,
    authorization: str | None,
    api_key_header: str | None,
    settings: Settings,
) -> ClerkUser:
    """Validate raw credentials, returning the authenticated `ClerkUser`.

    Accepts an `X-API-Key` header or an `Authorization: Bearer …` value. A
    bearer value prefixed `od_` (or any `X-API-Key`) is treated as a
    programmatic API key; anything else is verified as a Clerk session JWT.
    Raises `ClerkAuthError` on any failure. Used by both `require_user` and the
    A2A auth middleware so the two paths can never drift.
    """
    if not settings.auth_enabled:
        return _DEV_USER

    api_token: str | None = None
    jwt_token: str | None = None

    if api_key_header and api_key_header.strip():
        api_token = api_key_header.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
        if raw.startswith(API_KEY_PREFIX):
            api_token = raw
        elif raw:
            jwt_token = raw

    if api_token:
        return await _resolve_api_key(api_token, settings)
    if jwt_token:
        return await verify_clerk_token(jwt_token, settings=settings)
    raise ClerkAuthError("Bearer token or API key required")


async def require_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> ClerkUser:
    authorization = (
        f"{creds.scheme} {creds.credentials}"
        if creds is not None and creds.credentials
        else None
    )
    try:
        return await authenticate_credentials(
            authorization=authorization,
            api_key_header=request.headers.get("x-api-key"),
            settings=settings,
        )
    except ClerkAuthError as exc:
        log.info("auth: rejected on %s: %s", request.url.path, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
