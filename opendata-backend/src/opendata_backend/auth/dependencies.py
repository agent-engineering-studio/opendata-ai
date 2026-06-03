"""FastAPI dependencies for Clerk-authenticated endpoints.

Every application endpoint (everything except `/health`) declares
`user: ClerkUser = Depends(require_user)` so authentication is enforced
exactly the same way across routers.

When `settings.auth_enabled` is False (local dev) the dependency returns a
synthetic `_DEV_USER` instead of validating — there is no fallback to
anonymous access, just a clearly-named "dev mode" identity.
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

# Used only when `auth_enabled=False`. Subject is recognisable in logs so
# nobody mistakes a dev-mode user id for a real Clerk subject.
_DEV_USER = ClerkUser(
    subject="dev-user",
    email="dev@local",
    claims={"dev_mode": True},
)


async def require_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> ClerkUser:
    if not settings.auth_enabled:
        return _DEV_USER

    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        log.info("auth: missing or non-Bearer credentials on %s", request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await verify_clerk_token(creds.credentials, settings=settings)
    except ClerkAuthError as exc:
        log.info("auth: token rejected on %s: %s", request.url.path, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
