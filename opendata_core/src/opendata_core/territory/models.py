"""Modelli della modalità Territorio (Fase 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlaceRef:
    """Luogo risolto: codice ISTAT + nome + centroide + confine GeoJSON."""

    name: str
    istat_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    geojson: dict[str, Any] | None = None


@dataclass(frozen=True)
class TerritoryProfile:
    """Profilo canonico del territorio (segnali population/business/tourism/work)."""

    population: dict[str, Any] = field(default_factory=dict)
    business: dict[str, Any] = field(default_factory=dict)
    tourism: dict[str, Any] = field(default_factory=dict)
    work: dict[str, Any] = field(default_factory=dict)

    def as_signals(self) -> dict[str, dict[str, Any]]:
        """Mappa nome-segnale → payload, per la persistenza nelle tabelle signal."""
        return {
            "population": self.population,
            "business": self.business,
            "tourism": self.tourism,
            "work": self.work,
        }
