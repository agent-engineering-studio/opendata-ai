"""Motore di maturità open-data (ODM 2025 + AgID) — puro e deterministico.

Niente HTTP/LLM/DB. Il giudizio semantico (Haiku) e i pesi sono iniettati dal
chiamante (MCP/backend). Vedi docs e la spec di Fase 1.
"""

from .hvd import HVD_KEYWORDS, match_hvd_category
from .guidance import build_guida_opendata
from .coverage import (
    HVD_LABELS,
    SECTOR_KEYWORDS,
    assess_coverage,
    classify_sector,
    coverage_template,
    infer_entity_type,
)
from .models import (
    DEFAULT_COVERAGE_TEMPLATES,
    DEFAULT_ODM_LEVELS,
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    SECTOR_LABELS,
    CoverageResult,
    DatasetInput,
    DimensionBreakdown,
    DimensionScores,
    MaturityResult,
    QualityScore,
    Recommendation,
    SectorCoverage,
    is_open_license,
    odm_level,
)
from .gap import AzioneGap, GapAnalysis, analyze_gaps
from .quality import assess_quality
from .scoring import assess_entity, build_breakdown, build_recommendations, score_dimensions

__all__ = [
    "DatasetInput",
    "QualityScore",
    "DimensionScores",
    "DimensionBreakdown",
    "Recommendation",
    "MaturityResult",
    "CoverageResult",
    "SectorCoverage",
    "DEFAULT_WEIGHTS",
    "DEFAULT_ODM_LEVELS",
    "DEFAULT_COVERAGE_TEMPLATES",
    "DIMENSIONS",
    "SECTOR_LABELS",
    "SECTOR_KEYWORDS",
    "HVD_LABELS",
    "is_open_license",
    "odm_level",
    "match_hvd_category",
    "HVD_KEYWORDS",
    "assess_quality",
    "assess_entity",
    "assess_coverage",
    "classify_sector",
    "coverage_template",
    "infer_entity_type",
    "build_guida_opendata",
    "score_dimensions",
    "build_breakdown",
    "build_recommendations",
    "analyze_gaps",
    "GapAnalysis",
    "AzioneGap",
]
