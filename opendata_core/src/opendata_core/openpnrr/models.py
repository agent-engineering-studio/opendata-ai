"""Pydantic models for OpenPNRR records returned by the core client.

I payload OpenPNRR portano molti campi grezzi; il client ritorna viste snelle
e tipizzate più il record grezzo dove utile. Gli importi sono parsati in float
da ``mapping.parse_amount``.
"""

from __future__ import annotations

from pydantic import BaseModel


class Territorio(BaseModel):
    """Una riga di /territori — il ponte tra codice ISTAT e id OpenPNRR."""

    id: int
    slug: str
    denominazione: str
    istat_id: str | None = None
    opdm_id: int | None = None
    tipologia: str | None = None  # C | P | R | E …
    identifier: str | None = None
    url: str | None = None


class ProgettoSummary(BaseModel):
    """Vista snella di un risultato di /progetti."""

    id: int | None = None
    codice_locale_progetto: str | None = None
    titolo: str | None = None
    cup: str | None = None
    misura: str | None = None
    soggetto_attuatore: str | None = None
    stato_avanzamento: str | None = None
    is_validato: bool | None = None
    finanziamento_totale: float | None = None
    finanziamento_pnrr: float | None = None
    territori: list = []
    url: str | None = None


class Misura(BaseModel):
    """Vista snella di una misura PNRR (/misure)."""

    id: int
    codice_identificativo: str | None = None
    codice_misura: str | None = None
    componente: str | None = None
    descrizione: str | None = None
    tipologia: str | None = None
    status: str | None = None
    url: str | None = None


class Scadenza(BaseModel):
    """Vista snella di una scadenza/milestone PNRR (/scadenze)."""

    id: int
    descrizione_breve: str | None = None
    status: str | None = None
    ita_ue: str | None = None
    tempistica_completamento_anno: int | None = None
    tempistica_completamento_trimestre: str | None = None  # es. "T4"
    tipologia: str | None = None
    url: str | None = None
