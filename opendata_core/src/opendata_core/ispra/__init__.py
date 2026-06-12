"""Async client per ISPRA IdroGEO (pericolosità frane/alluvioni per comune)."""

from .client import IspraClient, IspraError
from .models import HazardSlice, RiskIndicators

__all__ = ["IspraClient", "IspraError", "HazardSlice", "RiskIndicators"]
