"""Fixed-window per-user rate limit backed by Redis.

The current window is identified by the truncated wall-clock minute so any
client (in any process) hits the same counter for the same user inside the
same minute. When Redis is not configured the limiter is a no-op — calls
sail through and the FastAPI dependency does not raise.

Future work: per-plan limits keyed on subscription tier (step 6+).
"""

from __future__ import annotations

import logging
import time

from fastapi import Depends, HTTPException, status

from ..auth import ClerkUser, require_user
from ..cache.state import get_redis
from ..config import Settings, get_settings

log = logging.getLogger("opendata-backend.ratelimit")


def _window_key(subject: str, *, now: float) -> str:
    bucket = int(now // 60)
    return f"od:ratelimit:{subject}:{bucket}"


async def enforce_rate_limit(
    user: ClerkUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> ClerkUser:
    """Increment the current-minute counter and 429 if it crosses the limit.

    Returns the authenticated user so handlers can chain
    `user: ClerkUser = Depends(enforce_rate_limit)` instead of repeating
    `require_user` separately.
    """
    client = get_redis()
    if client is None or settings.rate_limit_per_minute <= 0:
        return user

    key = _window_key(user.subject, now=time.time())
    try:
        current = await client.incr(key)
        if current == 1:
            await client.expire(key, 70)
    except Exception:
        log.warning("ratelimit Redis call failed for %s", user.subject, exc_info=True)
        return user

    if current > settings.rate_limit_per_minute:
        retry_after = 60 - int(time.time() % 60)
        log.info(
            "rate limit hit subject=%s count=%d limit=%d",
            user.subject, current, settings.rate_limit_per_minute,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded; slow down",
            headers={"Retry-After": str(retry_after)},
        )
    return user
