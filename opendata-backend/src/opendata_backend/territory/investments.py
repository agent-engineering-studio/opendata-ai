"""Aggregatore della spesa pubblica/opere sul comune via OpenCoesione.

Riusa `opendata_core.opencoesione.OpenCoesioneClient` (client REST live). Normalizza
i progetti nella tabella canonica `investment` (uno per progetto, payload_jsonb).
Idempotente: sostituisce gli investimenti `opencoesione` del place a ogni run.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from opendata_core.opencoesione import OpenCoesioneClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.territory_models import Investment

log = logging.getLogger("opendata-backend.territory.investments")


async def fetch_investments(
    *, cod_comune: str, max_projects: int = 50, client: OpenCoesioneClient | None = None
) -> dict[str, Any]:
    """Progetti + aggregati OpenCoesione per un comune. Fail-safe → strutture vuote."""
    owns = client is None
    c = client or OpenCoesioneClient()
    if owns:
        await c.__aenter__()
    try:
        try:
            aggregates = await c.territorial_aggregates(cod_comune=cod_comune)
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenCoesione aggregati non disponibili per %s: %s", cod_comune, exc)
            aggregates = {}
        try:
            search = await c.search_projects(cod_comune=cod_comune, limit=max_projects)
            projects = search.get("results", [])
            total = int(search.get("total") or len(projects))
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenCoesione progetti non disponibili per %s: %s", cod_comune, exc)
            projects, total = [], 0
    finally:
        if owns:
            await c.__aexit__(None, None, None)
    return {"projects": projects, "aggregates": aggregates, "total": total}


def _amount(project: dict[str, Any]) -> float | None:
    val = project.get("finanziamento_totale")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


async def persist_investments(
    session: AsyncSession,
    *,
    place_id: int,
    projects: list[dict[str, Any]],
    observed_at: datetime,
    source: str = "opencoesione",
) -> int:
    """Sostituisce gli investimenti del place per la sorgente data (idempotente)."""
    await session.execute(
        delete(Investment).where(Investment.place_id == place_id, Investment.source == source)
    )
    for p in projects:
        session.add(Investment(
            place_id=place_id, source=source, observed_at=observed_at, payload_jsonb=p
        ))
    await session.flush()
    return len(projects)


def summarize_investments(projects: list[dict[str, Any]]) -> dict[str, Any]:
    """Sintesi deterministica: totale finanziato, n. progetti, ripartizione per tema."""
    by_tema: dict[str, float] = {}
    total_funding = 0.0
    for p in projects:
        amt = _amount(p) or 0.0
        total_funding += amt
        tema = p.get("tema") or "Altro"
        by_tema[tema] = by_tema.get(tema, 0.0) + amt
    top = sorted(by_tema.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "n_progetti": len(projects),
        "finanziamento_totale": round(total_funding, 2),
        "per_tema": [{"tema": t, "finanziamento": round(v, 2)} for t, v in top],
    }
