"""Redis-backed cache + rate-limit primitives.

`store.py` holds the low-level get_json/set_json wrappers; the three module
files (`fetch.py`, `classify.py`, `by_category.py`) carry namespace-specific
key builders and TTLs. The Redis client is created at app startup
(`main.lifespan`) and shared across modules through `state.get_redis()`.
"""

from .state import get_redis, set_redis
from .store import cache_get, cache_set, cache_delete

__all__ = ["cache_delete", "cache_get", "cache_set", "get_redis", "set_redis"]
