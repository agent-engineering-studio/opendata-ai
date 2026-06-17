"""Modelli e costanti del motore di maturità (Fase 1).

Tutto puro e deterministico: nessun HTTP/LLM/DB. Il giudizio semantico (Haiku) è
INIETTATO dal chiamante come `semantic_clarity` ∈ [0,1]; i pesi delle dimensioni
sono iniettabili (default qui sotto, override via config nel backend/MCP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ── Formati / licenze ────────────────────────────────────────────────

# Formati non-proprietari (≥3 stelle Berners-Lee).
OPEN_FORMATS = {
    "csv", "tsv", "json", "geojson", "xml", "rdf", "ttl", "n3", "nt",
    "jsonld", "json-ld", "ods", "kml", "gml", "sparql", "owl",
}
# Formati strutturati ma proprietari (2 stelle).
PROPRIETARY_STRUCTURED = {"xls", "xlsx", "shp", "mdb", "accdb"}
# Formati RDF (4 stelle).
RDF_FORMATS = {"rdf", "ttl", "n3", "nt", "jsonld", "json-ld", "owl", "sparql"}
# Machine-readable = strutturati (aperti o proprietari): ≥2 stelle.
MACHINE_READABLE = OPEN_FORMATS | PROPRIETARY_STRUCTURED

# Licenze aperte note (prefix/slug, lowercase). `isopen` di CKAN ha precedenza.
_OPEN_LICENSE_HINTS = (
    "cc-by", "cc0", "cc-zero", "ccby", "odbl", "odc", "pddl",
    "iodl", "creative commons", "public domain", "dl-by", "dati aperti",
)


def is_open_license(license_id: str | None, license_title: str | None, isopen: bool | None) -> bool:
    """True se la licenza è aperta. `isopen` di CKAN ha precedenza, poi euristica."""
    if isopen is not None:
        return bool(isopen)
    blob = f"{license_id or ''} {license_title or ''}".lower()
    return any(h in blob for h in _OPEN_LICENSE_HINTS)


# ── Pesi e livelli ODM (default; override via config) ────────────────

DEFAULT_WEIGHTS: dict[str, float] = {
    "policy": 0.25,
    "portal": 0.25,
    "quality": 0.30,
    "impact": 0.20,
}

# Soglie crescenti su score_overall (0–100) → livello scala ODM 2025.
DEFAULT_ODM_LEVELS: list[tuple[float, str]] = [
    (0.0, "Beginner"),
    (40.0, "Follower"),
    (60.0, "Fast-tracker"),
    (80.0, "Trend-setter"),
]

DIMENSIONS = ("policy", "portal", "quality", "impact")

# Sotto questa soglia di dataset l'assessment è marcato "dato insufficiente"
# (no punteggi falsi su basi troppo piccole).
DEFAULT_MIN_DATASETS = 3
INSUFFICIENT_LEVEL = "Dato insufficiente"


def odm_level(score_overall: float, levels: list[tuple[float, str]] | None = None) -> str:
    """Mappa un punteggio 0–100 al livello ODM via soglie crescenti."""
    table = levels or DEFAULT_ODM_LEVELS
    name = table[0][1]
    for threshold, label in table:
        if score_overall >= threshold:
            name = label
    return name


# ── Strutture dati ───────────────────────────────────────────────────


@dataclass(frozen=True)
class DatasetInput:
    """Dataset CKAN normalizzato per la valutazione."""

    id: str
    title: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    theme: str | None = None
    license_id: str | None = None
    license_is_open: bool = False
    modified: datetime | None = None
    frequency: str | None = None
    formats: tuple[str, ...] = ()          # lowercase, dalle distribution
    resource_urls: tuple[str, ...] = ()
    has_linked_data: bool = False          # SPARQL endpoint / link a altri dati

    @property
    def has_distribution(self) -> bool:
        return bool(self.resource_urls) or bool(self.formats)

    @property
    def keyword_blob(self) -> str:
        parts = [self.title or "", self.description or "", self.theme or "", " ".join(self.tags)]
        return " ".join(parts).lower()

    @staticmethod
    def from_ckan(pkg: dict[str, Any]) -> "DatasetInput":
        """Normalizza un pacchetto CKAN (Action API) in DatasetInput."""
        from .ckan_norm import normalize_ckan_package

        return normalize_ckan_package(pkg)


@dataclass(frozen=True)
class QualityScore:
    """Punteggio di qualità di un singolo dataset."""

    dataset_id: str
    stars_5: int
    fair_f: float
    fair_a: float
    fair_i: float
    fair_r: float
    dcat_ap_it: float
    iso25012: float
    iso25012_detail: dict[str, float] = field(default_factory=dict)
    license_open: bool = False
    hvd_category: str | None = None
    freshness_days: int | None = None

    @property
    def fair_mean(self) -> float:
        return (self.fair_f + self.fair_a + self.fair_i + self.fair_r) / 4.0

    @property
    def composite(self) -> float:
        """Qualità composita 0–1: media di 5-star (norm.), FAIR, DCAT, ISO."""
        return (self.stars_5 / 5.0 + self.fair_mean + self.dcat_ap_it + self.iso25012) / 4.0


@dataclass(frozen=True)
class DimensionScores:
    policy: float
    portal: float
    quality: float
    impact: float
    overall: float
    level: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "portal": self.portal,
            "quality": self.quality,
            "impact": self.impact,
            "overall": self.overall,
            "level": self.level,
        }


@dataclass(frozen=True)
class Recommendation:
    code: str
    severity: str       # "alta" | "media" | "bassa"
    dimension: str
    message: str
    affected_count: int


@dataclass(frozen=True)
class MaturityResult:
    """Esito completo dell'assessment di un ente."""

    n_datasets: int
    scores: DimensionScores
    recommendations: tuple[Recommendation, ...]
    dataset_quality: tuple[QualityScore, ...]
    insufficient_data: bool = False
