"""Orchestrazione del sito civico: snapshot (+ diff col precedente) + maturità → pagine."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.territory_models import Entity, MaturityAssessment
from .diff import diff_snapshots
from .site import generate_site
from .snapshot import get_snapshot, list_snapshots


async def _maturity_for(session: AsyncSession, comune_name: str) -> dict[str, Any] | None:
    """Scorecard maturità (best-effort) per l'ente il cui nome contiene il comune."""
    if not comune_name:
        return None
    ent = (
        await session.execute(
            select(Entity).where(Entity.name.ilike(f"%{comune_name}%")).limit(1)
        )
    ).scalar_one_or_none()
    if ent is None:
        return None
    ma = (
        await session.execute(
            select(MaturityAssessment).where(MaturityAssessment.entity_id == ent.id)
            .order_by(MaturityAssessment.assessed_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if ma is None:
        return None
    return {
        "level": ma.level, "overall": float(ma.score_overall or 0),
        "dimensions": {
            "policy": float(ma.score_policy or 0), "portal": float(ma.score_portal or 0),
            "quality": float(ma.score_quality or 0), "impact": float(ma.score_impact or 0),
        },
        "unmet_reuse_demand": (ma.details_jsonb or {}).get("unmet_reuse_demand"),
    }


async def build_site(
    session: AsyncSession, *, istat_code: str, snapshot_id: str | None = None
) -> dict[str, str] | None:
    """Genera le pagine del sito civico per il comune. None se nessuno snapshot."""
    snaps = await list_snapshots(session, istat_code)
    if not snaps:
        return None
    ids = [s.snapshot_id for s in snaps]
    target_id = snapshot_id or ids[-1]
    snap = await get_snapshot(session, istat_code, target_id)
    if snap is None:
        return None

    diff = None
    idx = ids.index(target_id) if target_id in ids else -1
    if idx > 0:
        prev = await get_snapshot(session, istat_code, ids[idx - 1])
        if prev is not None:
            diff = diff_snapshots(
                state_a=prev.payload_jsonb or {}, kpi_a=prev.kpi_jsonb or {},
                state_b=snap.payload_jsonb or {}, kpi_b=snap.kpi_jsonb or {},
            )

    comune_name = (snap.payload_jsonb or {}).get("name") or istat_code
    maturity = await _maturity_for(session, comune_name)

    snapshot_dict = {
        "istat_code": snap.istat_code, "snapshot_id": snap.snapshot_id,
        "created_at": snap.created_at.isoformat() if snap.created_at else None,
        "sources_version": snap.sources_version, "kpi_version": snap.kpi_version,
        "payload": snap.payload_jsonb or {}, "kpi": snap.kpi_jsonb or {},
    }
    return generate_site(snapshot_dict, diff=diff, maturity=maturity)
