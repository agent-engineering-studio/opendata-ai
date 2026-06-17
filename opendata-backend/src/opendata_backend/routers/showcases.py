"""Router /showcases — galleria di showcase dichiarativi (YAML) + esecuzione."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..showcase import get_showcase, list_showcases, run_showcase

router = APIRouter(tags=["showcases"])


@router.get("/showcases")
async def showcases_list(
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Elenco degli showcase disponibili (metadati dai file YAML)."""
    return {"showcases": list_showcases()}


@router.get("/showcases/{showcase_id}/run")
async def showcase_run(
    showcase_id: str,
    istat: str = Query(..., description="codice ISTAT del comune (join spaziale)"),
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Esegue lo showcase per un comune e ritorna dati + spec di visualizzazione."""
    if get_showcase(showcase_id) is None:
        raise HTTPException(status_code=404, detail="showcase non trovato")
    result = await run_showcase(session, showcase_id, istat_code=istat.strip())
    if result is None:
        raise HTTPException(status_code=404, detail="showcase non trovato")
    return result
