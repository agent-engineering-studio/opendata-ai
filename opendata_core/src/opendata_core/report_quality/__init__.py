"""Qualità dei report territoriali — gate di autovalutazione (motore PURO).

Derivato dalla rubric "Qualità dei report territoriali" (Documento di metodo
Parte IV). I gate sono deterministici, comune-agnostici e fail-safe: operano sul
testo del report + i metadati iniettati (popolazione, anno, evidenze), non
bloccano la pubblicazione (il chiamante annota il footer). Vedi `gates.py`.
"""

from .gates import (
    SOGLIA_PUBBLICAZIONE,
    Finding,
    QualitaReport,
    gate_certificazioni,
    gate_denominatore,
    gate_dedup,
    gate_freshness,
    gate_vincoli,
    valuta_report,
)

__all__ = [
    "valuta_report",
    "QualitaReport",
    "Finding",
    "SOGLIA_PUBBLICAZIONE",
    "gate_freshness",
    "gate_denominatore",
    "gate_certificazioni",
    "gate_dedup",
    "gate_vincoli",
]
