"""Cache wrapper for /datasets/fetch — keyed by SHA-1 of the resource URL.

Open data portals are slow and the same resource URL is hit many times in a
short window (the UI re-renders, an AI agent re-asks, …). A 6-hour TTL
balances freshness vs. backend load.
"""

from __future__ import annotations

import hashlib

from .store import cache_get, cache_set

TTL_SECONDS = 6 * 60 * 60


def _key(url: str) -> str:
    return "od:fetch:" + hashlib.sha1(url.encode()).hexdigest()


async def get(url: str) -> dict | None:
    return await cache_get(_key(url))


async def set(url: str, payload: dict) -> None:
    await cache_set(_key(url), payload, ttl_seconds=TTL_SECONDS)
