"""Low-level get/set helpers — JSON-serialised values, TTL in seconds."""

from __future__ import annotations

import json
import logging
from typing import Any

from .state import get_redis

log = logging.getLogger("opendata-backend.cache")


async def cache_get(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception:
        log.warning("redis GET failed for %s", key, exc_info=True)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def cache_set(key: str, value: Any, *, ttl_seconds: int) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
    except Exception:
        log.warning("redis SET failed for %s", key, exc_info=True)


async def cache_delete(key: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.delete(key)
    except Exception:
        log.warning("redis DEL failed for %s", key, exc_info=True)
