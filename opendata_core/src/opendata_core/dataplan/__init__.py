"""Copilota Open Data per l'ente (Data Officer AI) — motori puri (#170).

Porta un comune da "zero dati" a una politica open data viva: inventario del
potenziale (D1, catalogo), prioritizzazione valore×sforzo (D2), politica/piano
(D3+). Motori PURI (no FastAPI/LLM/rete): la conoscenza (catalogo, pesi) è
impacchettata o iniettata; l'orchestrazione e le chiamate LLM vivono nel backend.
"""

from .catalog import catalog_by_area, clear_cache, load_catalog
from .models import CandidateDataset, GiaAperto
from .prioritize import RankedCandidate, prioritize

__all__ = [
    "CandidateDataset",
    "GiaAperto",
    "load_catalog",
    "catalog_by_area",
    "clear_cache",
    "prioritize",
    "RankedCandidate",
]
