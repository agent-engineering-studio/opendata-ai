"""Motore di maturità open-data (ODM 2025 + AgID) — puro e deterministico.

Niente HTTP/LLM/DB. Il giudizio semantico (Haiku) e i pesi sono iniettati dal
chiamante (MCP/backend). Vedi docs e la spec di Fase 1.
"""

from .hvd import HVD_KEYWORDS, match_hvd_category
from .models import (
    DEFAULT_ODM_LEVELS,
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    DatasetInput,
    DimensionScores,
    MaturityResult,
    QualityScore,
    Recommendation,
    is_open_license,
    odm_level,
)
from .quality import assess_quality
from .scoring import assess_entity, build_recommendations, score_dimensions

__all__ = [
    "DatasetInput",
    "QualityScore",
    "DimensionScores",
    "Recommendation",
    "MaturityResult",
    "DEFAULT_WEIGHTS",
    "DEFAULT_ODM_LEVELS",
    "DIMENSIONS",
    "is_open_license",
    "odm_level",
    "match_hvd_category",
    "HVD_KEYWORDS",
    "assess_quality",
    "assess_entity",
    "score_dimensions",
    "build_recommendations",
]
