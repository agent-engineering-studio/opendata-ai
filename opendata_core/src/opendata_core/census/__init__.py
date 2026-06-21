"""Connettori a dati censuari comunali (8milaCensus)."""

from .lavoro import fetch_lavoro_comune
from .welfare import fetch_welfare_comune

__all__ = ["fetch_lavoro_comune", "fetch_welfare_comune"]
