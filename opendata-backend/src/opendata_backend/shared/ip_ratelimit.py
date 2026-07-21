"""Per-IP and global request rate limit, applied as HTTP middleware (#235).

Unlike the per-user limiter (`ratelimit.enforce_rate_limit`, a FastAPI
dependency keyed off the authenticated subject), this runs BEFORE auth and so
protects UNauthenticated traffic too — including the public read-only views of
a self-hosted deployment. It is Redis-backed when `REDIS_URL` is set (shared
across processes) and falls back to a bounded in-process fixed-window counter
otherwise, so a Regione that hosts the backend without Redis still gets basic
DoS protection.

Fail-open by design: any Redis error or unexpected condition lets the request
through — a rate limiter must never take the whole API down.
"""

from __future__ import annotations

import logging
import time

from starlette.requests import Request

from ..cache.state import get_redis
from ..config import Settings

log = logging.getLogger("opendata-backend.ratelimit.ip")

# In-process fallback counters for the CURRENT minute bucket only. When the
# wall-clock minute rolls over the whole map is dropped, so memory is bounded by
# the number of distinct client IPs seen within a single minute — negligible for
# a monitoring dashboard.
_local_counts: dict[str, int] = {}
_local_bucket: int = -1


def _client_ip(request: Request) -> str:
    """Best-effort client IP. Trusts the left-most `X-Forwarded-For` hop when
    present (the deployment sits behind a Traefik reverse proxy), else the
    socket peer address."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _local_incr(key: str, bucket: int) -> int:
    """Increment the in-process counter for `key`, resetting the map on a new
    minute bucket. Safe under asyncio: no `await` between read and write."""
    global _local_bucket, _local_counts
    if bucket != _local_bucket:
        _local_bucket = bucket
        _local_counts = {}
    _local_counts[key] = _local_counts.get(key, 0) + 1
    return _local_counts[key]


async def _incr(key: str, bucket: int) -> int:
    """New counter value for `key` in `bucket`. Redis when available, else the
    in-process fallback. Returns 0 (fail-open) on any Redis error."""
    client = get_redis()
    if client is None:
        return _local_incr(key, bucket)
    rkey = f"od:iprl:{key}:{bucket}"
    try:
        current = await client.incr(rkey)
        if current == 1:
            await client.expire(rkey, 70)
        return int(current)
    except Exception:  # noqa: BLE001 — never let the limiter break the app
        log.warning("ip-ratelimit Redis call failed for %s", key, exc_info=True)
        return 0


async def check_request(request: Request, settings: Settings) -> int | None:
    """Retry-After seconds if `request` should be rejected with 429, else None.

    Enforces the per-IP limit and, when configured, a global limit across all
    IPs. Both use a fixed 60-second window."""
    ip_limit = settings.rate_limit_ip_per_minute
    global_limit = settings.rate_limit_global_per_minute
    if ip_limit <= 0 and global_limit <= 0:
        return None

    now = time.time()
    bucket = int(now // 60)
    retry_after = 60 - int(now % 60)

    if ip_limit > 0:
        ip = _client_ip(request)
        count = await _incr(f"ip:{ip}", bucket)
        if count > ip_limit:
            log.info("ip rate limit hit ip=%s count=%d limit=%d", ip, count, ip_limit)
            return retry_after

    if global_limit > 0:
        gcount = await _incr("global", bucket)
        if gcount > global_limit:
            log.info("global rate limit hit count=%d limit=%d", gcount, global_limit)
            return retry_after

    return None


def _reset_local() -> None:
    """Test hook — clear the in-process counters."""
    global _local_bucket, _local_counts
    _local_bucket = -1
    _local_counts = {}
