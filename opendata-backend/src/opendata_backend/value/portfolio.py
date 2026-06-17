"""Portfolio del valore: aggregati da dataset_quality (+ reuse da favorites/classifications).

Deduplica all'ultimo snapshot per (source, dataset_id). Filtri opzionali per ente/
regione/categoria HVD.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Classification, Favorite
from ..db.territory_models import DatasetQuality, Entity


async def _reuse_index(session: AsyncSession) -> dict[tuple[str, str], float]:
    """Mappa (source, dataset_id) → reuse score, da conteggi raggruppati (2 query)."""
    idx: dict[tuple[str, str], float] = {}
    fav = await session.execute(
        select(Favorite.source, Favorite.dataset_id, func.count()).group_by(
            Favorite.source, Favorite.dataset_id
        )
    )
    for source, did, n in fav.all():
        idx[(source, did)] = idx.get((source, did), 0.0) + int(n) * 25
    cls = await session.execute(
        select(Classification.source, Classification.dataset_id, func.count()).group_by(
            Classification.source, Classification.dataset_id
        )
    )
    for source, did, n in cls.all():
        idx[(source, did)] = idx.get((source, did), 0.0) + int(n) * 10
    return {k: min(100.0, v) for k, v in idx.items()}


async def build_portfolio(
    session: AsyncSession,
    *,
    entity_id: int | None = None,
    region: str | None = None,
    hvd: str | None = None,
) -> dict[str, Any]:
    """Aggregati di portfolio sull'ultimo snapshot di qualità per dataset."""
    stmt = select(DatasetQuality)
    if entity_id is not None:
        stmt = stmt.where(DatasetQuality.entity_id == entity_id)
    if region:
        stmt = stmt.join(Entity, Entity.id == DatasetQuality.entity_id).where(Entity.region == region)
    if hvd:
        stmt = stmt.where(DatasetQuality.hvd_category == hvd)
    rows = list((await session.execute(stmt)).scalars().all())

    # dedup: ultimo snapshot per (source, dataset_id)
    latest: dict[tuple[str, str], DatasetQuality] = {}
    for r in rows:
        key = (r.source, r.dataset_id)
        cur = latest.get(key)
        if cur is None or (r.assessed_at and cur.assessed_at and r.assessed_at > cur.assessed_at):
            latest[key] = r
    datasets = list(latest.values())
    n = len(datasets)
    if n == 0:
        return {
            "count": 0, "pct_hvd": None, "pct_open_license": None,
            "avg_freshness_days": None, "avg_stars": None, "avg_reuse": None,
        }

    reuse_idx = await _reuse_index(session)
    pct_hvd = round(100.0 * sum(1 for d in datasets if d.hvd_category) / n, 1)
    pct_open = round(100.0 * sum(1 for d in datasets if d.license_open_bool) / n, 1)
    fresh = [d.freshness_days for d in datasets if d.freshness_days is not None]
    stars = [d.stars_5 for d in datasets if d.stars_5 is not None]
    reuse_vals = [reuse_idx.get((d.source, d.dataset_id), 0.0) for d in datasets]
    return {
        "count": n,
        "pct_hvd": pct_hvd,
        "pct_open_license": pct_open,
        "avg_freshness_days": round(mean(fresh), 1) if fresh else None,
        "avg_stars": round(mean(stars), 2) if stars else None,
        "avg_reuse": round(mean(reuse_vals), 1) if reuse_vals else None,
    }
