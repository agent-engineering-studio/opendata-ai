"""Router /usecases — use case applicativi (ApriQui AI, PugliaTrip Brain)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..usecases.apriqui import run_apriqui

router = APIRouter(tags=["usecases"])


class ApriQuiIn(BaseModel):
    istat_codes: list[str]


@router.post("/usecases/apriqui")
async def apriqui(
    body: ApriQuiIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Attrattività 0–100 per categoria di attività in uno o più comuni (confronto) + spiegazione."""
    codes = [c.strip() for c in body.istat_codes if c.strip()]
    if not codes:
        raise HTTPException(status_code=422, detail="istat_codes non può essere vuoto")
    return await run_apriqui(session, istat_codes=codes, settings=settings)
