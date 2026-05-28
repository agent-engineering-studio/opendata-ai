"""Programmatic API keys — stub until Postgres + Clerk are wired up."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import ClerkUser, require_user

router = APIRouter(tags=["api-keys"])


@router.post("/api-keys/generate")
async def generate(user: ClerkUser = Depends(require_user)) -> dict:
    raise HTTPException(status_code=501, detail="api-keys not implemented yet (step 4)")
