"""Read-only access to the local OpenCoesione mirror (`opendata.oc_progetti`).

The table is created and populated by the backend (`opendata-opencoesione-sync`
CLI + Alembic migrations) — this module NEVER writes and does not import the
backend ORM: plain SQLAlchemy core with bound parameters, no free-form SQL.

Activated only when the OPENCOESIONE_DB_URL env var is set; without it the
server stays a pure live-API wrapper (Claude Desktop use). The mirror has one
row per (project, comune) — per-comune aggregations are correct by
construction; cross-comune sums would double-count multi-comune projects,
which is why every query here is territory-scoped.

`tema` matching: the mirror stores the CSV labels ('Trasporti e mobilità'),
while callers often pass API slugs ('trasporti', 'cultura-e-turismo') — the
filter is a case-insensitive substring match with dashes treated as spaces.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

DB_URL_ENV = "OPENCOESIONE_DB_URL"

#: Bulk states counted as completed (CSV labels, see backend ingest).
STATI_CONCLUSI_LABELS = ("Concluso", "Liquidato")

_engine: AsyncEngine | None = None
_engine_url: str | None = None


def db_url() -> str | None:
    """The configured mirror DSN, or None when the local tool must stay off."""
    return os.getenv(DB_URL_ENV) or None


def _to_async_dsn(url: str) -> str:
    """Default sync DSNs to their async drivers (asyncpg / aiosqlite)."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _table(url: str) -> str:
    """Schema-qualified on Postgres; SQLite (tests) has no schemas."""
    return "oc_progetti" if url.startswith("sqlite") else "opendata.oc_progetti"


def get_engine() -> AsyncEngine:
    """Lazy per-process engine; re-created if the env var changes (tests)."""
    global _engine, _engine_url
    url = db_url()
    if url is None:
        raise RuntimeError(f"{DB_URL_ENV} non configurato")
    if _engine is None or _engine_url != url:
        if _engine is not None:
            # Old engine for a different URL — let GC close it (tests only).
            pass
        _engine = create_async_engine(_to_async_dsn(url))
        _engine_url = url
    return _engine


def _tema_filter(tema: str | None) -> tuple[str, dict[str, Any]]:
    if not tema:
        return "", {}
    needle = tema.strip().lower().replace("-", " ").replace("_", " ")
    return " AND LOWER(tema) LIKE :tema ", {"tema": f"%{needle}%"}


def _ciclo_filter(ciclo: str | None) -> tuple[str, dict[str, Any]]:
    if not ciclo:
        return "", {}
    norm = ciclo.strip().replace("-", "_").replace(" ", "_")
    return " AND ciclo = :ciclo ", {"ciclo": norm}


async def dataset_info() -> dict[str, Any]:
    """Freshness metadata for the `sources` block (max ingested_at + row count)."""
    eng = get_engine()
    t = _table(db_url() or "")
    async with eng.connect() as conn:
        row = (
            await conn.execute(
                text(f"SELECT COUNT(*) AS n, MAX(ingested_at) AS latest FROM {t}")  # noqa: S608
            )
        ).one()
    return {"records": int(row.n or 0), "ingested_at": str(row.latest) if row.latest else None}


async def spend_by_tema(cod_comune: str, ciclo: str | None = None) -> list[dict[str, Any]]:
    eng = get_engine()
    t = _table(db_url() or "")
    cf, cp = _ciclo_filter(ciclo)
    sql = (
        f"SELECT tema, COUNT(*) AS progetti, "  # noqa: S608
        f"SUM(finanziamento_totale) AS finanziato, SUM(pagamenti) AS pagamenti "
        f"FROM {t} WHERE cod_comune = :comune{cf} "
        f"GROUP BY tema ORDER BY finanziato DESC"
    )
    async with eng.connect() as conn:
        rows = (await conn.execute(text(sql), {"comune": cod_comune, **cp})).mappings().all()
    return [
        {
            "tema": r["tema"],
            "progetti": int(r["progetti"]),
            "finanziato": float(r["finanziato"] or 0),
            "pagamenti": float(r["pagamenti"] or 0),
        }
        for r in rows
    ]


async def capacity(cod_comune: str, ciclo: str | None = None) -> dict[str, Any]:
    eng = get_engine()
    t = _table(db_url() or "")
    cf, cp = _ciclo_filter(ciclo)
    placeholders = ", ".join(f":s{i}" for i in range(len(STATI_CONCLUSI_LABELS)))
    sql = (
        f"SELECT COUNT(*) AS progetti, "  # noqa: S608
        f"SUM(finanziamento_totale) AS finanziato, SUM(pagamenti) AS pagamenti, "
        f"SUM(CASE WHEN stato IN ({placeholders}) THEN 1 ELSE 0 END) AS conclusi "
        f"FROM {t} WHERE cod_comune = :comune{cf}"
    )
    params: dict[str, Any] = {"comune": cod_comune, **cp}
    params.update({f"s{i}": s for i, s in enumerate(STATI_CONCLUSI_LABELS)})
    async with eng.connect() as conn:
        r = (await conn.execute(text(sql), params)).mappings().one()
    progetti = int(r["progetti"] or 0)
    finanziato = float(r["finanziato"] or 0)
    pagamenti = float(r["pagamenti"] or 0)
    conclusi = int(r["conclusi"] or 0)
    return {
        "cod_comune": cod_comune,
        "ciclo": cp.get("ciclo"),
        "progetti_totali": progetti,
        "progetti_conclusi": conclusi,
        "finanziato_totale": finanziato,
        "pagamenti_totali": pagamenti,
        "spend_ratio": round(pagamenti / finanziato, 4) if finanziato else None,
        "conclusi_ratio": round(conclusi / progetti, 4) if progetti else None,
    }


async def top_soggetti(
    cod_comune: str | None = None,
    cod_provincia: str | None = None,
    cod_regione: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    eng = get_engine()
    t = _table(db_url() or "")
    where, params = "", {}
    if cod_comune:
        where, params = "cod_comune = :v", {"v": cod_comune}
    elif cod_provincia:
        where, params = "cod_provincia = :v", {"v": cod_provincia}
    elif cod_regione:
        where, params = "cod_regione = :v", {"v": cod_regione}
    else:
        raise ValueError("Serve cod_comune, cod_provincia o cod_regione")
    sql = (
        f"SELECT soggetto_attuatore, COUNT(*) AS progetti, "  # noqa: S608
        f"SUM(finanziamento_totale) AS finanziato "
        f"FROM {t} WHERE {where} AND soggetto_attuatore IS NOT NULL "
        f"GROUP BY soggetto_attuatore ORDER BY progetti DESC LIMIT :lim"
    )
    params["lim"] = max(1, min(int(limit), 50))
    async with eng.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    return [
        {
            "soggetto_attuatore": r["soggetto_attuatore"],
            "progetti": int(r["progetti"]),
            "finanziato": float(r["finanziato"] or 0),
        }
        for r in rows
    ]


async def compare_comuni(
    cod_comuni: list[str], tema: str | None = None, ciclo: str | None = None
) -> list[dict[str, Any]]:
    if not cod_comuni:
        raise ValueError("Serve almeno un codice comune")
    eng = get_engine()
    t = _table(db_url() or "")
    tf, tp = _tema_filter(tema)
    cf, cp = _ciclo_filter(ciclo)
    placeholders = ", ".join(f":c{i}" for i in range(len(cod_comuni)))
    sql = (
        f"SELECT cod_comune, COUNT(*) AS progetti, "  # noqa: S608
        f"SUM(finanziamento_totale) AS finanziato, SUM(pagamenti) AS pagamenti "
        f"FROM {t} WHERE cod_comune IN ({placeholders}){tf}{cf} "
        f"GROUP BY cod_comune ORDER BY finanziato DESC"
    )
    params: dict[str, Any] = {f"c{i}": c.strip() for i, c in enumerate(cod_comuni)}
    params.update(tp)
    params.update(cp)
    async with eng.connect() as conn:
        rows = (await conn.execute(text(sql), params)).mappings().all()
    by_comune = {r["cod_comune"]: r for r in rows}
    out: list[dict[str, Any]] = []
    for c in cod_comuni:
        r = by_comune.get(c.strip())
        fin = float(r["finanziato"] or 0) if r else 0.0
        pag = float(r["pagamenti"] or 0) if r else 0.0
        out.append(
            {
                "cod_comune": c.strip(),
                "progetti": int(r["progetti"]) if r else 0,
                "finanziato": fin,
                "pagamenti": pag,
                "spend_ratio": round(pag / fin, 4) if fin else None,
            }
        )
    return out
