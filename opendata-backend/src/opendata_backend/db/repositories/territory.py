"""Persistenza modalità Territorio: place, segnali, feature_store, report.

Upsert portabili (select-then-update); segnali e feature rigenerati a ogni run
(idempotente). geom NON è gestito qui (lo popola il seed/geocode di Fase 0).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ComuneAnagrafica
from ..territory_models import (
    BusinessCluster,
    FeatureStore,
    Place,
    PopulationProfile,
    TerritoryReport,
    TourismSignal,
    WorkSignal,
)

# Mappa nome-segnale → modello ORM della tabella signal.
_SIGNAL_MODELS = {
    "population": PopulationProfile,
    "business": BusinessCluster,
    "tourism": TourismSignal,
    "work": WorkSignal,
}


async def comune_anagrafica(session: AsyncSession, istat_code: str) -> ComuneAnagrafica | None:
    res = await session.execute(
        select(ComuneAnagrafica).where(ComuneAnagrafica.cod_comune == istat_code)
    )
    return res.scalar_one_or_none()


async def upsert_place(
    session: AsyncSession, *, istat_code: str, name: str, place_type: str = "comune"
) -> Place:
    row = (
        await session.execute(select(Place).where(Place.istat_code == istat_code))
    ).scalar_one_or_none()
    if row is None:
        row = Place(istat_code=istat_code, name=name, type=place_type)
        session.add(row)
        await session.flush()
        return row
    if name:
        row.name = name
    await session.flush()
    return row


async def get_place_by_istat(session: AsyncSession, istat_code: str) -> Place | None:
    res = await session.execute(select(Place).where(Place.istat_code == istat_code))
    return res.scalar_one_or_none()


async def save_signals(
    session: AsyncSession, *, place_id: int, signals: dict[str, dict[str, Any]],
    observed_at: datetime, source: str = "profile",
) -> int:
    """Rigenera i segnali del place per le tabelle note (idempotente per source)."""
    n = 0
    for key, payload in signals.items():
        model = _SIGNAL_MODELS.get(key)
        if model is None or not payload:
            continue
        await session.execute(
            delete(model).where(model.place_id == place_id, model.source == source)
        )
        session.add(model(place_id=place_id, source=source, observed_at=observed_at,
                           payload_jsonb=payload))
        n += 1
    await session.flush()
    return n


async def upsert_feature_store(
    session: AsyncSession, *, place_id: int, features: dict[str, Any], computed_at: datetime
) -> FeatureStore:
    row = (
        await session.execute(select(FeatureStore).where(FeatureStore.place_id == place_id))
    ).scalar_one_or_none()
    if row is None:
        row = FeatureStore(place_id=place_id, features_jsonb=features, computed_at=computed_at)
        session.add(row)
    else:
        row.features_jsonb = features
        row.computed_at = computed_at
    await session.flush()
    return row


async def get_feature_store(session: AsyncSession, place_id: int) -> FeatureStore | None:
    res = await session.execute(select(FeatureStore).where(FeatureStore.place_id == place_id))
    return res.scalar_one_or_none()


async def save_report(
    session: AsyncSession, *, place_id: int, payload: dict[str, Any], created_at: datetime
) -> TerritoryReport:
    row = TerritoryReport(place_id=place_id, created_at=created_at, payload_jsonb=payload)
    session.add(row)
    await session.flush()
    return row
