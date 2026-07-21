"""Modelli del motore di aggregazione regionale (#228, cruscotto #227).

Motore PURO: nessuna dipendenza da FastAPI/LLM/rete. Prende in input una lista
di sintesi-comune (iniettate dal backend a partire dal warehouse: anagrafica +
ultimi assessment di maturità) e produce la vista d'insieme della regione.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComuneSummary(BaseModel):
    """Sintesi di un singolo comune, iniettata nel motore.

    `overall`/`dimensioni` sono i punteggi ODM dell'ultimo assessment (None se il
    comune non è ancora stato valutato); `hvd_categorie` sono le categorie HVD
    con almeno un dataset pubblicato.
    """

    istat: str
    nome: str
    popolazione: int | None = None
    overall: float | None = None
    dimensioni: dict[str, float] = Field(default_factory=dict)
    n_dataset: int = 0
    hvd_categorie: list[str] = Field(default_factory=list)


class InterventionHint(BaseModel):
    """Un punto su cui la regione dovrebbe intervenire: un comune debole/senza
    dati, oppure una dimensione ODM debole a livello regionale."""

    tipo: str  # "comune" | "dimensione"
    motivo: str
    # tipo == "comune"
    istat: str | None = None
    nome: str | None = None
    overall: float | None = None
    # tipo == "dimensione"
    dimensione: str | None = None
    mediana: float | None = None


class RegionOverview(BaseModel):
    """Vista d'insieme regionale (persona ente regionale)."""

    regione: str
    cod_regione: str
    comuni_totali: int
    comuni_valutati: int
    distribuzione_stato: dict[str, int]
    mediana_overall: float | None
    hvd_copertura: dict[str, float]
    dimensioni_mediana: dict[str, float]
    dove_intervenire: list[InterventionHint]
