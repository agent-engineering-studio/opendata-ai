"""Modello dei siti contaminati / bonifiche (SIN-SIR) per la riconciliazione (#128)."""

from __future__ import annotations

from pydantic import BaseModel


class ContaminationInfo(BaseModel):
    """Esito dell'interrogazione MOSAICO (ISPRA) su un poligono/comune (#128 Fase 2a).

    Due segnali distinti:
    - ``sin``: il punto ricade in un **Sito di Interesse Nazionale** (poligono) →
      segnale POLIGONO-PRECISO.
    - ``sir_*``: procedimenti di bonifica **regionali** nel comune (punti attribuiti
      al comune) → segnale a SCALA COMUNALE.

    ``contaminato`` (SIN al punto o almeno un procedimento in stato "contaminato")
    attiva la classificazione BROWNFIELD e la causa di abbandono "contaminazione"
    (§4.4). ``None`` a monte = fonte non interrogabile (confidenza degradata)."""

    contaminato: bool
    sin: bool
    sin_denominazione: str | None = None
    sir_procedimenti: int = 0  # procedimenti di bonifica nel comune
    sir_contaminati: int = 0   # di cui in stato "contaminato" (CONT)
    matrici: list[str] = []    # matrici ambientali del SIN (es. suolo/acque)
    source_url: str
    licenza: str
