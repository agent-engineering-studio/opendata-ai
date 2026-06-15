"""Modelli Pydantic degli indicatori di rischio IdroGEO (livello comunale)."""

from __future__ import annotations

from pydantic import BaseModel


class HazardSlice(BaseModel):
    """Una classe di pericolosità: superficie e popolazione esposte."""

    classe: str  # p4 | p3 | p2 | p1 | aa | p3p4 (aggregato frane)
    area_kmq: float | None = None
    area_pct: float | None = None
    popolazione: int | None = None
    popolazione_pct: float | None = None


class RiskIndicators(BaseModel):
    """Indicatori di pericolosità frane + idraulica per un comune.

    Le classi sono ordinate dalla più severa; ``frane_p3p4`` è l'aggregato
    "pericolosità elevata o molto elevata" — il numero che conta per i
    vincoli di espansione (spec 07).
    """

    cod_comune: str
    nome: str
    area_kmq: float | None = None
    popolazione_residente: int | None = None
    frane: list[HazardSlice] = []
    frane_p3p4: HazardSlice | None = None
    idraulica: list[HazardSlice] = []
    source_url: str
    licenza: str
