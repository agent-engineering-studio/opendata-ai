"""Persistenza append-only degli artefatti del Copilota (#222): `dataplan_plans`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.territory_models import DataplanPlan


async def save_plan(
    session: AsyncSession, *, istat_code: str, ente: str | None, tipo: str, payload: dict[str, Any],
) -> DataplanPlan:
    """Salva uno snapshot (mai sovrascrive: append-only, storicizza l'avanzamento)."""
    row = DataplanPlan(istat_code=istat_code, ente=ente, tipo=tipo, payload_jsonb=payload)
    session.add(row)
    await session.flush()
    return row


async def latest_plan(session: AsyncSession, *, istat_code: str, tipo: str) -> DataplanPlan | None:
    """L'ultimo snapshot di un tipo per il comune, o None."""
    return await session.scalar(
        select(DataplanPlan)
        .where(DataplanPlan.istat_code == istat_code, DataplanPlan.tipo == tipo)
        .order_by(desc(DataplanPlan.generato_il), desc(DataplanPlan.id))
        .limit(1)
    )
