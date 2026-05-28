"""Module-level holder for the async Redis client.

Populated by `main.lifespan` when REDIS_URL is configured; left None
otherwise (cache reads become straight misses and writes are no-ops).
"""

from __future__ import annotations

import redis.asyncio as redis

_client: redis.Redis | None = None


def set_redis(client: redis.Redis | None) -> None:
    global _client
    _client = client


def get_redis() -> redis.Redis | None:
    return _client
