"""Authentication middleware for the A2A JSON-RPC surface.

A2A routes are mounted via the SDK's `add_a2a_routes_to_fastapi` helper, which
registers them *outside* FastAPI's dependency graph — so `Depends(require_user)`
cannot guard them. This middleware intercepts requests to the JSON-RPC endpoint
(`/a2a/`) and enforces the same credential rules as `require_user`
(Clerk JWT or `od_` API key) before the request reaches the executor.

Discovery stays public on purpose: the AgentCard at `/.well-known/agent*.json`
advertises capabilities and must be fetchable by any client deciding whether to
talk to us. Only the *invocation* endpoint requires a subscriber credential.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..auth import ClerkAuthError, authenticate_credentials
from ..config import Settings

log = logging.getLogger("opendata-backend.a2a")

# JSON-RPC invocation path. Discovery (`/.well-known/...`) is deliberately
# excluded so AgentCard fetches stay anonymous.
_PROTECTED_PREFIX = "/a2a"


def register_a2a_auth(app: FastAPI, settings: Settings) -> None:
    """Attach the A2A auth middleware unless A2A or auth is disabled.

    When `auth_enabled=False` (dev) the check still runs but
    `authenticate_credentials` short-circuits to the synthetic dev user, so the
    middleware is effectively a pass-through locally.
    """
    if not settings.a2a_enabled:
        return

    @app.middleware("http")
    async def _a2a_auth(request: Request, call_next):  # type: ignore[type-arg]
        path = request.url.path
        # Guard only the JSON-RPC endpoint; allow CORS preflight through so the
        # CORS middleware can answer it.
        if request.method == "OPTIONS" or not (
            path == _PROTECTED_PREFIX or path.startswith(_PROTECTED_PREFIX + "/")
        ):
            return await call_next(request)

        try:
            await authenticate_credentials(
                authorization=request.headers.get("authorization"),
                api_key_header=request.headers.get("x-api-key"),
                settings=settings,
            )
        except ClerkAuthError as exc:
            log.info("a2a auth: rejected %s: %s", path, exc)
            return JSONResponse(
                status_code=401,
                content={"detail": str(exc)},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
