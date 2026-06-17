"""Router /value — narrazione di valore (Sonnet) e portfolio aggregato."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit
from ..value.narrative import generate_narrative
from ..value.portfolio import build_portfolio

router = APIRouter(tags=["value"])


class NarrativeIn(BaseModel):
    title: str | None = None
    description: str | None = None
    theme: str | None = None
    context: dict[str, Any] | None = None


@router.post("/value/narrative")
async def value_narrative(
    body: NarrativeIn,
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, str]:
    """Narrazione problema→dato→servizio→beneficiario (Sonnet, fallback offline)."""
    context = body.context or {
        "title": body.title, "description": body.description, "theme": body.theme,
    }
    narrative = await generate_narrative(model=settings.claude_model, context=context)
    return {"narrative": narrative}


@router.get("/value/portfolio")
async def value_portfolio(
    entity_id: int | None = Query(default=None),
    region: str | None = Query(default=None),
    hvd: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Aggregati di valore del patrimonio (per ente/regione/categoria HVD)."""
    return await build_portfolio(session, entity_id=entity_id, region=region, hvd=hvd)
