"""Web-search + fetch async client (SearXNG by default)."""

from .client import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_PROVIDER,
    DEFAULT_SEARXNG_BASE_URL,
    MAX_FETCH_BYTES,
    SUPPORTED_PROVIDERS,
    WebClient,
    WebSearchError,
)

__all__ = [
    "WebClient",
    "WebSearchError",
    "DEFAULT_PROVIDER",
    "DEFAULT_SEARXNG_BASE_URL",
    "DEFAULT_MAX_RESULTS",
    "MAX_FETCH_BYTES",
    "SUPPORTED_PROVIDERS",
]
