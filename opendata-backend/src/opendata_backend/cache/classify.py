"""Cache wrapper for /datasets/classify — keyed by (source, dataset_id, taxonomy hash).

Classifications are stable for the lifetime of a (dataset, taxonomy) pair;
caching for 24h saves the Claude Haiku API call (most expensive surface
after the multi-source fan-out).
"""

from __future__ import annotations

from .store import cache_get, cache_set
from ..db.repositories.classifications import taxonomy_hash

TTL_SECONDS = 24 * 60 * 60


def _key(source: str, dataset_id: str, taxonomy: list[str]) -> str:
    return f"od:classify:{source}:{dataset_id}:{taxonomy_hash(taxonomy)}"


async def get(source: str, dataset_id: str, taxonomy: list[str]) -> dict | None:
    return await cache_get(_key(source, dataset_id, taxonomy))


async def set(source: str, dataset_id: str, taxonomy: list[str], result: dict) -> None:
    await cache_set(_key(source, dataset_id, taxonomy), result, ttl_seconds=TTL_SECONDS)
