"""Router /maturity — assessment maturità open-data di un ente (ODM 2025).

Tutti gli endpoint sono autenticati (Clerk) + rate-limited come gli altri.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..maturity.service import build_ranking, build_scorecard, run_assessment
from ..shared.ratelimit import enforce_rate_limit

router = APIRouter(tags=["maturity"])


class AssessIn(BaseModel):
    entity: str
    base_url: str | None = None
    force: bool = False


@router.post("/maturity/assess")
async def assess(
    body: AssessIn,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Avvia/aggiorna l'assessment di un ente e ritorna la scorecard."""
    entity = body.entity.strip()
    if not entity:
        raise HTTPException(status_code=422, detail="campo 'entity' obbligatorio")
    return await run_assessment(
        session, entity=entity, base_url=body.base_url, settings=settings, force=body.force
    )


@router.get("/maturity/entities/{entity_id}")
async def get_entity_scorecard(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Scorecard dell'ente: 4 dimensioni, livello ODM, raccomandazioni, trend, mediana cluster."""
    scorecard = await build_scorecard(session, entity_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail="ente o assessment non trovato")
    return scorecard


@router.get("/maturity/ranking")
async def ranking(
    entity_type: str | None = Query(default=None, alias="type"),
    region: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Benchmark tra enti (filtrabile per type/regione) + mediana del cluster."""
    return await build_ranking(session, entity_type=entity_type, region=region)
