"""Agente di monitoraggio schedulato — motore puro (Punto 05 #88).

Dato un target (dataset/risorsa di un ente) e lo stato del run precedente,
`run_checks` produce una lista di finding deterministica (freshness/qualità/
link) e `diff_runs` confronta due run per capire cosa è cambiato. Niente
FastAPI/LLM/I-O qui: il runner (`opendata_backend.monitor`) raccoglie i dati
(fetch HTTP, ri-profilazione) e chiama questo motore, che resta testabile
offline. Fail-safe per costruzione: ogni controllo restituisce `None`/lista
vuota quando i dati non bastano per un giudizio, mai un numero inventato.
"""

from __future__ import annotations

from .engine import diff_runs, run_checks
from .freshness import check_freshness
from .links import check_links
from .quality_regression import check_quality_regression

__all__ = [
    "run_checks", "diff_runs", "check_freshness", "check_quality_regression", "check_links",
]
