"""Pydantic models for OpenCoesione records returned by the core client.

Project list/detail payloads carry 100+ raw fields; the client returns slim,
typed summaries plus the raw record where useful. Amounts are parsed from the
Italian decimal-comma strings into floats by ``mapping.parse_amount``.
"""

from __future__ import annotations

from pydantic import BaseModel


class Territorio(BaseModel):
    """One row of /territori — the bridge between ISTAT codes and API slugs."""

    denominazione: str
    tipo: str  # C | P | R | E
    slug: str
    cod_reg: int
    cod_prov: int
    cod_com: int


class ProjectSummary(BaseModel):
    """Slim view of a /progetti list result."""

    clp: str
    titolo: str | None = None
    tema: str | None = None
    stato: str | None = None
    ciclo: str | None = None
    natura: str | None = None
    finanziamento_totale: float | None = None
    pagamenti: float | None = None
    percentuale_avanzamento: str | None = None
    soggetti: list[dict] = []
    territori: list[str] = []
    url: str | None = None  # resolvable API detail URL


class StatoBreakdown(BaseModel):
    """Per-state slice of the territorial aggregates."""

    stato: str
    progetti: int
    costo_pubblico: float | None = None
    pagamenti: float | None = None


class FundingCapacity(BaseModel):
    """Historical spending-capacity indicator for a territory.

    ``spend_ratio`` = total payments / total public cost: an honest proxy of how
    much of the funding secured by the territory was actually spent.
    Computed from ONE call to /aggregati/territori/{slug}.json (which accepts a
    ``ciclo_programmazione`` filter); when ``tema`` is set, ratios come from the
    per-theme aggregate slice and the per-state breakdown is not available.
    """

    territorio: str
    slug: str
    popolazione: int | None = None
    ciclo: str | None = None
    tema: str | None = None
    finanziato_totale: float | None = None
    pagamenti_totali: float | None = None
    spend_ratio: float | None = None
    progetti_totali: int | None = None
    progetti_conclusi: int | None = None
    conclusi_ratio: float | None = None
    breakdown_stati: list[StatoBreakdown] = []
    data_aggiornamento: str | None = None
    source_url: str
