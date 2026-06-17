"""Router /territory — report territoriale strutturato (modello canonico) + profilo.

Distinto da /territorio + /programma (fan-out conversazionale): qui il report nasce
dal data warehouse canonico (place/signal/investment/feature_store) + narrazione Sonnet.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..territory.service import build_report, get_profile

router = APIRouter(tags=["territory"])


class ReportIn(BaseModel):
    istat_code: str
    temi: list[str] | None = None
    anno_da: int | None = None
    anno_a: int | None = None


@router.post("/territory/report")
async def territory_report(
    body: ReportIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Genera il report territoriale del comune (profilo, investimenti, segnali, gap) + narrazione."""
    istat = body.istat_code.strip()
    if not istat:
        raise HTTPException(status_code=422, detail="campo 'istat_code' obbligatorio")
    return await build_report(
        session, istat_code=istat, temi=body.temi,
        anno_da=body.anno_da, anno_a=body.anno_a, settings=settings,
    )


@router.get("/territory/{istat_code}/profile")
async def territory_profile(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Profilo canonico cache-ato del comune (feature_store)."""
    profile = await get_profile(session, istat_code.strip())
    if profile is None:
        raise HTTPException(status_code=404, detail="profilo non disponibile: genera prima un report")
    return profile
