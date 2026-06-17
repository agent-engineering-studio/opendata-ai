"""Domanda di riuso non soddisfatta (anello valore⇄maturità).

Aggrega i gap di dato del comune (gap_dato del report Territorio + feature_gaps del
feature_store) → lista + penalità Impact deterministica per la maturità dell'ente.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories import territory as repo

# Ogni gap pesa 0.10 sull'Impact, con tetto 0.5 (max -50%).
_PENALTY_PER_GAP = 0.10
_PENALTY_CAP = 0.5


async def unmet_reuse_demand(session: AsyncSession, *, istat_code: str) -> dict[str, Any]:
    """Ritorna {count, items, penalty} dalla domanda di riuso non soddisfatta del comune."""
    place = await repo.get_place_by_istat(session, istat_code)
    items: list[str] = []
    if place is not None:
        report = await repo.latest_report(session, place.id)
        if report and report.payload_jsonb:
            items += list((report.payload_jsonb.get("sezioni") or {}).get("gap_dato") or [])
        fs = await repo.get_feature_store(session, place.id)
        if fs and fs.features_jsonb:
            items += list(fs.features_jsonb.get("feature_gaps") or [])
    # dedup preservando l'ordine
    items = list(dict.fromkeys(items))
    penalty = min(_PENALTY_CAP, len(items) * _PENALTY_PER_GAP)
    return {"count": len(items), "items": items, "penalty": round(penalty, 2)}
