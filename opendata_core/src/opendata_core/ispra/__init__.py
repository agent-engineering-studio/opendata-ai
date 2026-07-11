"""Async client per ISPRA IdroGEO (pericolosità frane/alluvioni per comune)."""

from .client import IspraClient, IspraError
from .landcover import LandCoverClient
from .models import HazardSlice, LandCoverInfo, RiskIndicators

__all__ = [
    "IspraClient", "IspraError", "HazardSlice", "RiskIndicators",
    "LandCoverClient", "LandCoverInfo",
]
