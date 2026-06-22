"""OpenDataSoft Explore API v2.1 async client."""

from .client import (
    DEFAULT_BASE_URL,
    OpenDataSoftClient,
    OpenDataSoftError,
)

__all__ = [
    "OpenDataSoftClient",
    "OpenDataSoftError",
    "DEFAULT_BASE_URL",
]
