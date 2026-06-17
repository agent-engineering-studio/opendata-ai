"""Modelli del motore di valore (Fase 2). Puro e deterministico.

Riusa `DatasetInput` del motore di maturità. Il `reuse_score` (uso reale sulla
piattaforma) è INIETTATO dal backend e non entra nell'overall art. 14.
"""

from __future__ import annotations

from dataclasses import dataclass

# I 4 criteri di valore dell'art. 14 Dir. (UE) 2019/1024 (Open Data).
VALUE_CRITERIA = ("socioeconomic", "audience_sme", "revenue", "combinability")


@dataclass(frozen=True)
class CombinabilityProfile:
    """Chiavi spaziali/temporali che rendono un dataset combinabile con altri."""

    spatial_keys: tuple[str, ...]
    temporal_keys: tuple[str, ...]
    score: float  # 0–100

    @property
    def has_spatial(self) -> bool:
        return bool(self.spatial_keys)

    @property
    def has_temporal(self) -> bool:
        return bool(self.temporal_keys)


@dataclass(frozen=True)
class ValueScore:
    """Punteggio di valore di un dataset (art. 14) + categoria HVD + reuse iniettato."""

    socioeconomic: float
    audience_sme: float
    revenue: float
    combinability: float
    overall: float
    hvd_category: str | None = None
    reuse_score: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "socioeconomic": self.socioeconomic,
            "audience_sme": self.audience_sme,
            "revenue": self.revenue,
            "combinability": self.combinability,
            "overall": self.overall,
            "hvd_category": self.hvd_category,
            "reuse_score": self.reuse_score,
        }
