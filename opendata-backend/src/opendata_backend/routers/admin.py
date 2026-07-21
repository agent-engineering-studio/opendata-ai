"""Admin API — user role management (#235, Fase 2).

Admin-only surface behind `require_admin`: list the registered users and change
their RBAC role. Authentication stays with the OIDC IdP; the *role* lives in
`opendata.users.role` and is edited here, then surfaced in the admin dashboard
UI (Fase 4). The public/registration flows never touch this router.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..auth.roles import ROLE_ADMIN, VALID_ROLES, require_admin
from ..db.repositories import users as users_repo
from ..db.session import get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: int
    clerk_user_id: str
    email: str | None
    display_name: str | None
    role: str
    subscription_tier: str
    created_at: datetime


class RoleIn(BaseModel):
    role: str


def _out(u) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        clerk_user_id=u.clerk_user_id,
        email=u.email,
        display_name=u.display_name,
        role=u.role,
        subscription_tier=u.subscription_tier,
        created_at=u.created_at,
    )


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    role: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    _admin: ClerkUser = Depends(require_admin),
) -> list[AdminUserOut]:
    if role is not None and role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown role: {role}",
        )
    rows = await users_repo.list_users(session, role=role, limit=limit, offset=offset)
    return [_out(u) for u in rows]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
async def set_user_role(
    user_id: int,
    body: RoleIn,
    session: AsyncSession = Depends(get_db_session),
    admin: ClerkUser = Depends(require_admin),
) -> AdminUserOut:
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown role: {body.role}; allowed: {', '.join(VALID_ROLES)}",
        )
    # Guard against self-lockout: an admin cannot demote their own row.
    target = await users_repo.get_by_id(session, user_id=user_id)
    if target is not None and target.clerk_user_id == admin.subject and body.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="non puoi rimuovere il tuo stesso ruolo admin",
        )
    updated = await users_repo.set_role_by_id(session, user_id=user_id, role=body.role)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="utente non trovato")
    await session.commit()
    return _out(updated)
