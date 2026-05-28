"""Programmatic API keys — the clear-text token is returned ONCE on creation."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser, require_user
from ..db.repositories import api_keys as api_keys_repo
from ..db.repositories import users as users_repo
from ..db.session import get_db_session

router = APIRouter(tags=["api-keys"])


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class GenerateResponse(BaseModel):
    id: int
    name: str
    token: str  # only returned this once
    created_at: str


@router.post("/api-keys/generate", response_model=GenerateResponse, status_code=201)
async def generate(
    body: GenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(require_user),
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
