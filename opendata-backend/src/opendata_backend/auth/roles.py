"""RBAC roles and the `require_role` dependency (#235).

Authentication (who you are) is delegated to the OIDC IdP (Keycloak — SPID /
email-OTP registration). Authorization (what you may do) lives HERE: the role
is stored in `opendata.users.role` and managed by an admin from the admin
dashboard. This module resolves the caller's role from the DB (syncing the user
row on first login and applying the bootstrap-admin promotion) and gates
handlers with `Depends(require_role(...))`.

Dev bypass: when `auth_enabled` is False the synthetic dev user is treated as
`admin`, so the whole surface — including the admin dashboard — is reachable
locally without an IdP.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings, get_settings
from ..db.session import get_db_session
from .clerk import ClerkUser
from .dependencies import require_user

log = logging.getLogger("opendata-backend.auth.roles")

ROLE_ADMIN = "admin"
ROLE_REGIONE = "regione"
ROLE_COMUNE = "comune"
ROLE_CITTADINO = "cittadino"

# The four roles map onto the cruscotto personas (regione / comune / cittadino)
# plus the admin who manages them. Order is significant only for display.
VALID_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_REGIONE, ROLE_COMUNE, ROLE_CITTADINO)

# Default role for a newly-synced registrant — the least-privileged one.
DEFAULT_ROLE = ROLE_CITTADINO


async def resolve_role(session: AsyncSession, user: ClerkUser, settings: Settings) -> str:
    """The caller's effective role.

    Dev-bypass → admin. Otherwise the role from `opendata.users` (the row is
    created on first login — lazy sync from the IdP), applying the bootstrap
    admin promotion when the email matches `BOOTSTRAP_ADMIN_EMAIL`. The resolved
    role is also stashed on `user.claims["role"]` for handler convenience.
    """
    if not settings.auth_enabled:
        user.claims["role"] = ROLE_ADMIN
        return ROLE_ADMIN

    from ..db.repositories import users as users_repo

    row = await users_repo.get_by_clerk_id(session, clerk_user_id=user.subject)
    boot = (settings.bootstrap_admin_email or "").strip().lower()
    email = (user.email or (row.email if row else None) or "").strip().lower()
    is_boot = bool(boot) and email == boot

    if row is None:
        # First authenticated request for this subject → sync a user row.
        row = await users_repo.get_or_create(
            session, clerk_user_id=user.subject, email=user.email
        )
        row.role = ROLE_ADMIN if is_boot else DEFAULT_ROLE
        await session.commit()
    elif is_boot and row.role != ROLE_ADMIN:
        row.role = ROLE_ADMIN
        await session.commit()

    user.claims["role"] = row.role
    return row.role


def require_role(*allowed: str):
    """Dependency factory: 403 unless the caller's role is one of `allowed`.

    Composes `require_user` (401 first), so an unauthenticated request never
    reaches the role check. Returns the `ClerkUser` (with `claims["role"]` set)
    so handlers can chain it in place of `require_user`.
    """
    allowed_set = frozenset(allowed)

    async def _dep(
        user: ClerkUser = Depends(require_user),
        session: AsyncSession = Depends(get_db_session),
        settings: Settings = Depends(get_settings),
    ) -> ClerkUser:
        role = await resolve_role(session, user, settings)
        if role not in allowed_set:
            log.info("authz: role=%s denied for subject=%s (needs %s)",
                     role, user.subject, ",".join(sorted(allowed_set)))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role: {', '.join(sorted(allowed_set))}",
            )
        return user

    return _dep


# Convenience alias for the common admin-only gate.
require_admin = require_role(ROLE_ADMIN)
