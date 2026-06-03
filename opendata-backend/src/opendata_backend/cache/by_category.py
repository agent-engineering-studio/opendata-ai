"""Cache wrapper for /datasets/by-category — short TTL (the map page polls).

The UI's `/mappa` page calls /by-category every time the user navigates;
caching for 5 minutes keeps the response near-instant while still picking
up freshly-published datasets within a few minutes.
"""

from __future__ import annotations

import hashlib
import json

from .store import cache_get, cache_set

TTL_SECONDS = 5 * 60


def _key(category: str, base_url: str | None, region: str | None) -> str:
    payload = json.dumps(
        {"category": category, "base_url": base_url, "region": region},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    return "od:by-category:" + hashlib.sha1(payload).hexdigest()


async def get(category: str, base_url: str | None, region: str | None) -> dict | None:
    return await cache_get(_key(category, base_url, region))


async def set(
    category: str,
    base_url: str | None,
    region: str | None,
    payload: dict,
) -> None:
    await cache_set(_key(category, base_url, region), payload, ttl_seconds=TTL_SECONDS)
