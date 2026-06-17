"""Materializzazione delle feature in feature_store (legge i segnali canonici)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories import territory as repo
from ..db.territory_models import MobilityNode
from .engineering import compute_features


async def materialize_features(session: AsyncSession, *, istat_code: str) -> dict[str, Any] | None:
    """Calcola e scrive le feature del comune in feature_store. None se place assente.

    Richiede un profilo già presente in feature_store (generato da /territory/report).
    """
    place = await repo.get_place_by_istat(session, istat_code)
    if place is None:
        return None
    fs = await repo.get_feature_store(session, place.id)
    profile = (fs.features_jsonb or {}).get("profile", {}) if fs else {}

    mobility_rows = (
        await session.execute(select(MobilityNode).where(MobilityNode.place_id == place.id))
    ).scalars().all()
    mobility = [r.payload_jsonb or {} for r in mobility_rows]

    anag = await repo.comune_anagrafica(session, istat_code)
    population = anag.popolazione if anag else None

    result = compute_features(
        business=profile.get("business"), tourism=profile.get("tourism"),
        mobility=mobility, population=population,
    )

    merged = dict(fs.features_jsonb) if fs and fs.features_jsonb else {}
    merged["features"] = result["features"]
    merged["feature_gaps"] = result["gaps"]
    await repo.upsert_feature_store(
        session, place_id=place.id, features=merged, computed_at=datetime.now(timezone.utc)
    )
    await session.commit()
    return {"place_id": place.id, **result}
