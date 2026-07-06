"""Socrata open-data APIs (Discovery/Views/SODA) async client."""

from .client import (
    DEFAULT_BASE_URL,
    SocrataClient,
    SocrataError,
)

__all__ = [
    "SocrataClient",
    "SocrataError",
    "DEFAULT_BASE_URL",
]
