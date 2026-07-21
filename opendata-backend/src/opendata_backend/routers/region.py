"""Cruscotto regionale — endpoint (#229, F2 di #227).

Vista d'insieme e classifica dei comuni della regione (`REGION`). Autenticati e
rate-limited; lo scoping è implicito (i dati escono già filtrati sulla regione
del deployment), quindi non serve `enforce_region_scope` — non c'è un comune in
input da validare.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..region import service as region_service
from ..shared.ratelimit import enforce_rate_limit

router = APIRouter(prefix="/regione", tags=["regione"])


@router.get("/overview")
async def overview(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    return await region_service.overview(session, settings)


@router.get("/comuni")
async def comuni(
    provincia: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    return await region_service.comuni(session, settings, provincia=provincia)


@router.get("/idee")
async def idee(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    return await region_service.ideas(session, settings)
