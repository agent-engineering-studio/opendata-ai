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
from ..usecases.pugliatrip import run_pugliatrip

router = APIRouter(tags=["usecases"])


class ApriQuiIn(BaseModel):
    istat_codes: list[str]


class PugliaTripIn(BaseModel):
    istat_code: str
    days: int = 3


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


@router.post("/usecases/pugliatrip")
async def pugliatrip(
    body: PugliaTripIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Itinerario turistico meteo-aware per un comune (POI + mobilità + Open-Meteo) + spiegazione."""
    code = body.istat_code.strip()
    if not code:
        raise HTTPException(status_code=422, detail="istat_code obbligatorio")
    return await run_pugliatrip(session, istat_code=code, days=max(1, min(body.days, 7)), settings=settings)
