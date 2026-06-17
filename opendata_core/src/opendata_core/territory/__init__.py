"""Modalità Territorio (Fase 2): risoluzione luogo + profilo canonico."""

from .models import PlaceRef, TerritoryProfile
from .profile import build_profile
from .resolve import resolve_place

__all__ = ["PlaceRef", "TerritoryProfile", "build_profile", "resolve_place"]
