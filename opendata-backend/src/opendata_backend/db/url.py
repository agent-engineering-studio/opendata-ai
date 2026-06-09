"""DSN normalization for the two SQLAlchemy drivers we use.

The same `DATABASE_URL` is consumed by:
- the runtime app (asyncpg, via `create_async_engine`)
- Alembic migrations (psycopg3, sync)

Hosted Postgres providers like Neon hand out plain `postgresql://...` DSNs with
`sslmode=require[&channel_binding=require]`. psycopg3 understands both
parameters; asyncpg does not — it expects `ssl=` via `connect_args` instead.
This module hides that asymmetry behind two helpers.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_ASYNC = "postgresql+asyncpg"
_SYNC = "postgresql+psycopg"
_ACCEPTED = {
    "postgres",
    "postgresql",
    "postgresql+asyncpg",
    "postgresql+psycopg",
    "postgresql+psycopg2",
}


def _parse(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in _ACCEPTED:
        raise ValueError(f"Unsupported DSN scheme: {parsed.scheme!r}")
    return parsed, dict(parse_qsl(parsed.query, keep_blank_values=True))


def to_async_dsn(url: str) -> tuple[str, dict]:
    """Return (asyncpg-compatible URL, connect_args).

    `sslmode` and `channel_binding` are stripped from the URL and translated:
    - sslmode=require|verify-ca|verify-full → connect_args["ssl"] = <mode>
    - sslmode=disable                       → connect_args["ssl"] = False
    - channel_binding=*                     → dropped (psycopg-only)

    When SSL is required we assume the target is a hosted Postgres behind a
    transaction-mode pooler (Neon, Supabase, RDS Proxy) and disable asyncpg's
    prepared-statement cache, which is incompatible with transaction pooling.
    """
    parsed, params = _parse(url)
    connect_args: dict = {}

    sslmode = params.pop("sslmode", None)
    params.pop("channel_binding", None)

    needs_ssl = sslmode in {"require", "verify-ca", "verify-full"}
    if needs_ssl:
        connect_args["ssl"] = sslmode
        connect_args["statement_cache_size"] = 0
    elif sslmode == "disable":
        connect_args["ssl"] = False

    new = parsed._replace(scheme=_ASYNC, query=urlencode(params))
    return urlunparse(new), connect_args


def needs_pooler_safe_engine(url: str) -> bool:
    """True when the DSN points at a TLS-fronted (likely pooled) Postgres."""
    _, params = _parse(url)
    return params.get("sslmode") in {"require", "verify-ca", "verify-full"}


def to_sync_dsn(url: str) -> str:
    """Return a psycopg3 DSN suitable for Alembic.

    psycopg3 understands `sslmode` and `channel_binding`, so the query string
    is passed through unchanged.
    """
    parsed, _ = _parse(url)
    return urlunparse(parsed._replace(scheme=_SYNC))
