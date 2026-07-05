"""Idea Lab — percorso conversazionale dai dati aperti a un'idea finanziabile."""

from .coach import run_chat_turn
from .models import (
    AREAS,
    STAGE_LABELS,
    STAGES,
    IdeaChatRequest,
    IdeaChatResponse,
    IdeaReportRequest,
    IdeaReportResponse,
    IdeaScoutRequest,
    IdeaScoutResponse,
)
from .report import build_report
from .scout import scout_area

__all__ = [
    "AREAS",
    "STAGES",
    "STAGE_LABELS",
    "IdeaChatRequest",
    "IdeaChatResponse",
    "IdeaReportRequest",
    "IdeaReportResponse",
    "IdeaScoutRequest",
    "IdeaScoutResponse",
    "run_chat_turn",
    "build_report",
    "scout_area",
]
