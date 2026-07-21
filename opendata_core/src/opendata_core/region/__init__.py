"""Motore di aggregazione regionale (#228, cruscotto #227) — motore PURO.

Compone le sintesi-comune (maturità + copertura HVD, iniettate dal backend) in
una vista d'insieme della regione: distribuzione per stato, mediane, copertura
HVD e "dove intervenire". Nessun FastAPI/LLM/rete: la query al warehouse e la
narrativa vivono nel backend.
"""

from .aggregate import aggregate_region
from .models import ComuneSummary, InterventionHint, RegionOverview

__all__ = [
    "aggregate_region",
    "ComuneSummary",
    "InterventionHint",
    "RegionOverview",
]
