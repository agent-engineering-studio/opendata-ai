"""Idea Lab — percorso conversazionale di brainstorming dai dati all'idea.

POST /ideas/chat    → un turno del percorso a tappe (stateless: il client
                      rimanda messaggi + dataset/finanziamenti già scoperti)
POST /ideas/report  → la scheda progetto finale (markdown completo)
GET  /ideas/areas   → aree tematiche e tappe, per costruire la UI

LLM-bound come /programma → gate `require_llm_access`; ma ogni tappa ha un
fallback offline deterministico, quindi il percorso non restituisce mai 5xx
per un problema di provider.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..auth import ClerkUser
from ..config import Settings, get_settings
from ..ideas import (
    AREAS,
    STAGE_LABELS,
    STAGES,
    IdeaChatRequest,
    IdeaChatResponse,
    IdeaReportRequest,
    IdeaReportResponse,
    build_report,
    run_chat_turn,
)
from ..llm_access import LLMAccess, require_llm_access
from ..shared.ratelimit import enforce_rate_limit

log = logging.getLogger("opendata-backend.ideas")

router = APIRouter(tags=["ideas"])


@router.get("/ideas/areas")
async def areas(
    user: ClerkUser = Depends(enforce_rate_limit),  # noqa: ARG001 — auth gate
) -> dict:
    return {
        "areas": [{"id": key, "label": val["label"]} for key, val in AREAS.items()],
        "stages": [{"id": s, "label": STAGE_LABELS[s]} for s in STAGES],
    }


@router.post("/ideas/chat", response_model=IdeaChatResponse)
async def chat(
    req: IdeaChatRequest,
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),  # noqa: ARG001 — gate only
) -> IdeaChatResponse:
    log.info(
        "/ideas/chat subject=%s stage=%s area=%s msgs=%d",
        user.subject, req.stage, req.area, len(req.messages),
    )
    return await run_chat_turn(settings, req)


@router.post("/ideas/report", response_model=IdeaReportResponse)
async def report(
    req: IdeaReportRequest,
    settings: Settings = Depends(get_settings),
    user: ClerkUser = Depends(enforce_rate_limit),
    access: LLMAccess = Depends(require_llm_access),  # noqa: ARG001 — gate only
) -> IdeaReportResponse:
    log.info(
        "/ideas/report subject=%s area=%s msgs=%d",
        user.subject, req.area, len(req.messages),
    )
    return await build_report(settings, req)
