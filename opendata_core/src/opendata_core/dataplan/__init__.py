"""Copilota Open Data per l'ente (Data Officer AI) — motori puri (#170).

Porta un comune da "zero dati" a una politica open data viva: inventario del
potenziale (D1, catalogo), prioritizzazione valore×sforzo (D2), politica/piano
(D3+). Motori PURI (no FastAPI/LLM/rete): la conoscenza (catalogo, pesi) è
impacchettata o iniettata; l'orchestrazione e le chiamate LLM vivono nel backend.
"""

from .catalog import catalog_by_area, clear_cache, load_catalog
from .models import CandidateDataset, GiaAperto
from .policy import (
    LICENZA_CONSIGLIATA,
    Piano,
    PianoVoce,
    Politica,
    SezionePolitica,
    build_piano,
    build_politica,
    render_piano_markdown,
    render_politica_markdown,
)
from .kpi import PlanKpi, plan_kpi
from .prioritize import RankedCandidate, prioritize
from .state import AccompanimentState, PercorsoStep, accompaniment_state
from .privacy import (
    PrivacyChecklist,
    PrivacyRule,
    all_families,
    checklist_for,
    family_for,
    rules_for,
)

__all__ = [
    "CandidateDataset",
    "GiaAperto",
    "load_catalog",
    "catalog_by_area",
    "clear_cache",
    "prioritize",
    "RankedCandidate",
    "checklist_for",
    "family_for",
    "rules_for",
    "all_families",
    "PrivacyChecklist",
    "PrivacyRule",
    "build_piano",
    "build_politica",
    "render_piano_markdown",
    "render_politica_markdown",
    "Piano",
    "PianoVoce",
    "Politica",
    "SezionePolitica",
    "LICENZA_CONSIGLIATA",
    "accompaniment_state",
    "AccompanimentState",
    "PercorsoStep",
    "plan_kpi",
    "PlanKpi",
]
