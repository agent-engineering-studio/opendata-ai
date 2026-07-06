"""Connettori a dati censuari comunali (8milaCensus)."""

from .casa import fetch_casa_comune
from .istruzione import fetch_grado_istruzione_comune
from .lavoro import fetch_lavoro_comune
from .welfare import fetch_welfare_comune

__all__ = [
    "fetch_casa_comune", "fetch_grado_istruzione_comune", "fetch_lavoro_comune", "fetch_welfare_comune",
]
