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

# ── Copertura tematica/settoriale (Fase A) ───────────────────────────
#
# Settori = vocabolario dei temi DCAT-AP_IT (Data Theme EU). Una "collection
# ottimale" non è "tanti dataset" ma "i dataset giusti per il ruolo dell'ente":
# il template per tipo di ente elenca i settori attesi (core) con una priorità
# (1 = più atteso). I settori fuori dal template restano valorizzati ma non
# pesano sul punteggio di copertura.

SECTOR_LABELS: dict[str, str] = {
    "AGRI": "Agricoltura, pesca e alimentazione",
    "ECON": "Economia e finanze",
    "EDUC": "Istruzione, cultura e sport",
    "ENVI": "Ambiente",
    "ENER": "Energia",
    "HEAL": "Salute",
    "GOVE": "Governo e settore pubblico",
    "JUST": "Giustizia e sicurezza pubblica",
    "REGI": "Territorio, urbanistica e città",
    "SOCI": "Popolazione e società",
    "TECH": "Scienza e tecnologia",
    "TRAN": "Trasporti e mobilità",
    "INTR": "Questioni internazionali",
}

# Template della collection ottimale per tipo di ente: settore → priorità.
# La presenza nel dizionario marca il settore come "core" (atteso) per quel tipo.
DEFAULT_COVERAGE_TEMPLATES: dict[str, dict[str, int]] = {
    "comune": {
        "GOVE": 1, "TRAN": 2, "ENVI": 3, "SOCI": 4,
        "REGI": 5, "ECON": 6, "EDUC": 7,
    },
    "regione": {
        "HEAL": 1, "TRAN": 2, "ENVI": 3, "ECON": 4, "AGRI": 5,
        "SOCI": 6, "EDUC": 7, "ENER": 8, "GOVE": 9,
    },
    "provincia": {
        "TRAN": 1, "EDUC": 2, "ENVI": 3, "GOVE": 4, "REGI": 5,
    },
    # Fallback per agenzie/enti generici: i settori trasversali di base.
    "ente": {
        "GOVE": 1, "ECON": 2, "SOCI": 3, "ENVI": 4, "TRAN": 5,
    },
}

DEFAULT_ENTITY_TYPE = "ente"

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
class DimensionBreakdown:
    """Spiegazione di una dimensione: cosa misura e quali sotto-metriche la trainano.

    `drivers` sono le sotto-metriche (etichetta, valore 0–100) ordinate dalla più
    debole; `weakest` ne riassume in linguaggio naturale le 1–3 sotto soglia.
    """

    dimension: str          # policy | portal | quality | impact
    label: str
    score: float            # 0–100 (= il valore aggregato della dimensione)
    description: str         # cosa misura la dimensione
    drivers: tuple[tuple[str, float], ...] = ()
    weakest: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": self.label,
            "score": self.score,
            "description": self.description,
            "drivers": [{"label": lbl, "value": val} for lbl, val in self.drivers],
            "weakest": list(self.weakest),
        }


@dataclass(frozen=True)
class SectorCoverage:
    """Copertura di un singolo settore tematico per un ente."""

    code: str
    label: str
    n_datasets: int
    share: float            # quota sul totale dei dataset valutati (0–1)
    is_core: bool           # atteso per questo tipo di ente
    present: bool           # almeno un dataset nel settore
    priority: int | None = None  # priorità nel template (1 = più atteso); None se non-core

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "n_datasets": self.n_datasets,
            "share": round(self.share, 3),
            "is_core": self.is_core,
            "present": self.present,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class CoverageResult:
    """Analisi di copertura tematica: quali settori l'ente copre vs. la
    collection ottimale attesa per il suo tipo, più la copertura HVD."""

    entity_type: str
    sectors: tuple[SectorCoverage, ...]       # tutti i settori, con conteggi
    missing_core: tuple[SectorCoverage, ...]  # core attesi ma assenti, per priorità
    hvd_present: tuple[str, ...]
    hvd_missing: tuple[str, ...]
    coverage_score: float                     # 0–100: quota di settori core coperti
    n_classified: int
    n_unclassified: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "coverage_score": self.coverage_score,
            "sectors": [s.as_dict() for s in self.sectors],
            "missing_core": [s.as_dict() for s in self.missing_core],
            "hvd_present": list(self.hvd_present),
            "hvd_missing": list(self.hvd_missing),
            "n_classified": self.n_classified,
            "n_unclassified": self.n_unclassified,
        }


@dataclass(frozen=True)
class MaturityResult:
    """Esito completo dell'assessment di un ente."""

    n_datasets: int
    scores: DimensionScores
    recommendations: tuple[Recommendation, ...]
    dataset_quality: tuple[QualityScore, ...]
    insufficient_data: bool = False
    coverage: "CoverageResult | None" = None
    breakdown: tuple[DimensionBreakdown, ...] = ()
