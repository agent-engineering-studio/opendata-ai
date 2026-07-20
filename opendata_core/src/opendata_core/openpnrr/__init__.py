"""Async client for the OpenPNRR API (openpolis — Italian NRRP open data)."""

from .client import OpenPnrrClient, OpenPnrrError
from .mapping import LICENZA
from .models import Misura, ProgettoSummary, Scadenza, Territorio

__all__ = [
    "OpenPnrrClient",
    "OpenPnrrError",
    "LICENZA",
    "Territorio",
    "ProgettoSummary",
    "Misura",
    "Scadenza",
]
