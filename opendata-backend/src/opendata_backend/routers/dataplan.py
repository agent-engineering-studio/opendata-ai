"""Router /dataplan/* — Copilota Open Data per l'ente (#222, backend di #170).

Espone il percorso "dal zero dati a una politica open data viva": diagnosi →
inventario → piano → politica → brief. Autenticato + rate-limited come gli altri.
Rispetta lo scoping regione (#191): un comune fuori `REGION` → 422.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..dataplan import service
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..shared.scope import enforce_region_scope

router = APIRouter(prefix="/dataplan", tags=["dataplan"])


class PoliticaIn(BaseModel):
    licenza: str | None = None


class BriefIn(BaseModel):
    candidate_id: str


@router.get("/{istat_code}/diagnosi")
async def diagnosi(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001
) -> dict[str, Any]:
    """Quanto sei aperto oggi: baseline maturità (se esiste) + adempimenti già aperti."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    return await service.diagnosi(session, settings, istat_code=istat_code.strip())


@router.get("/{istat_code}/inventario")
async def inventario(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001
) -> dict[str, Any]:
    """Catalogo dei dataset candidati (D1) contestualizzato al comune."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    return service.inventario(istat_code=istat_code.strip())


@router.get("/{istat_code}/piano")
async def piano(
    istat_code: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001
) -> dict[str, Any]:
    """Candidati prioritizzati (valore×sforzo) + piano di pubblicazione."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    return await service.piano(session, istat_code=istat_code.strip())


@router.post("/{istat_code}/politica")
async def politica(
    istat_code: str,
    body: PoliticaIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001
) -> dict[str, Any]:
    """Genera (e storicizza) la bozza di Politica Open Data. LLM opzionale (R11)."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    return await service.genera_politica(
        session, settings, istat_code=istat_code.strip(), licenza=body.licenza,
    )


@router.post("/{istat_code}/brief")
async def brief(
    istat_code: str,
    body: BriefIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001
) -> dict[str, Any]:
    """Export brief operativo per un dataset candidato (passi + privacy + DCAT)."""
    await enforce_region_scope(session, istat_code.strip(), settings)
    out = await service.brief(
        session, settings, istat_code=istat_code.strip(), candidate_id=body.candidate_id.strip(),
    )
    if out is None:
        raise HTTPException(status_code=404, detail=f"Dataset candidato '{body.candidate_id}' non nel catalogo.")
    return out
