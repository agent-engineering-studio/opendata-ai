"""Programmatic API keys — generate, list and revoke.

The clear-text token is returned ONCE, on creation. Afterwards only metadata
(name, created/last-used/revoked timestamps) is ever exposed; the token itself
is stored only as a SHA-256 hash and cannot be recovered.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..db.repositories import api_keys as api_keys_repo
from ..db.repositories import users as users_repo
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit

router = APIRouter(tags=["api-keys"])


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class GenerateResponse(BaseModel):
    id: int
    name: str
    token: str  # only returned this once
    created_at: str


class ApiKeyInfo(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None
    revoked_at: str | None


@router.post("/api-keys/generate", response_model=GenerateResponse, status_code=201)
async def generate(
    body: GenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> GenerateResponse:
    local_user = await users_repo.get_or_create(
        session, clerk_user_id=user.subject, email=user.email
    )
    row, token = await api_keys_repo.generate(session, user_id=local_user.id, name=body.name)
    await session.commit()
    return GenerateResponse(
        id=row.id,
        name=row.name,
        token=token,
        created_at=row.created_at.isoformat(),
    )


@router.get("/api-keys", response_model=list[ApiKeyInfo])
async def list_keys(
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> list[ApiKeyInfo]:
    local_user = await users_repo.get_or_create(
        session, clerk_user_id=user.subject, email=user.email
    )
    await session.commit()
    rows = await api_keys_repo.list_for_user(session, user_id=local_user.id)
    return [
        ApiKeyInfo(
            id=row.id,
            name=row.name,
            created_at=row.created_at.isoformat(),
            last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
            revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
        )
        for row in rows
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> None:
    local_user = await users_repo.get_or_create(
        session, clerk_user_id=user.subject, email=user.email
    )
    revoked = await api_keys_repo.revoke(session, user_id=local_user.id, key_id=key_id)
    await session.commit()
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
