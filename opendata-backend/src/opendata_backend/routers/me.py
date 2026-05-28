"""Per-user state — stubs until Postgres is wired up in step 4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import ClerkUser, require_user

router = APIRouter(tags=["me"])


@router.get("/me/favorites")
async def list_favorites(user: ClerkUser = Depends(require_user)) -> dict:
    raise HTTPException(status_code=501, detail="favorites not implemented yet (step 4)")


@router.post("/me/favorites")
async def add_favorite(user: ClerkUser = Depends(require_user)) -> dict:
    raise HTTPException(status_code=501, detail="favorites not implemented yet (step 4)")


@router.get("/me/history")
async def list_history(user: ClerkUser = Depends(require_user)) -> dict:
    raise HTTPException(status_code=501, detail="history not implemented yet (step 4)")
