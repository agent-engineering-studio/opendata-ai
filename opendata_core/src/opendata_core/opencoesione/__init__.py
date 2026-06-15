"""Async client for the OpenCoesione API (Italian cohesion-policy projects)."""

from .client import OpenCoesioneClient, OpenCoesioneError
from .models import FundingCapacity, ProjectSummary, Territorio

__all__ = [
    "OpenCoesioneClient",
    "OpenCoesioneError",
    "FundingCapacity",
    "ProjectSummary",
    "Territorio",
]
