"""Creazione e lettura di snapshot civici versionati (non sovrascrivibili).

Uno snapshot cattura lo stato del comune (report + feature + progetti) e i KPI
civici calcolati, sotto un `snapshot_id` pubblico (es. 2026-H1). Riproducibile:
porta sources_version e kpi_version.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories import territory as repo
from ..db.territory_models import CivicSnapshot, Investment
from .kpi import compute_kpis, kpi_version


class SnapshotError(RuntimeError):
    """Snapshot già esistente o stato non disponibile."""


async def build_state(session: AsyncSession, istat_code: str) -> dict[str, Any] | None:
    """Assembla lo stato corrente del comune dal data warehouse. None se assente."""
    place = await repo.get_place_by_istat(session, istat_code)
    if place is None:
        return None
    fs = await repo.get_feature_store(session, place.id)
    fjson = fs.features_jsonb or {} if fs else {}
    rows = (
        await session.execute(select(Investment).where(Investment.place_id == place.id))
    ).scalars().all()
    projects = [r.payload_jsonb or {} for r in rows]
    anag = await repo.comune_anagrafica(session, istat_code)
    return {
        "name": place.name,
        "features": fjson.get("features", {}),
        "investimenti": fjson.get("investments", {}),
        "projects": projects,
        "population": anag.popolazione if anag else None,
        "stato_suolo": fjson.get("stato_suolo", []),  # record §4.5 (Parte V, #130)
    }


async def create_snapshot(
    session: AsyncSession, *, istat_code: str, snapshot_id: str,
    sources_version: str, state: dict[str, Any] | None = None,
) -> CivicSnapshot:
    """Crea uno snapshot versionato (errore se (istat, snapshot_id) esiste già)."""
    existing = (
        await session.execute(
            select(CivicSnapshot).where(
                CivicSnapshot.istat_code == istat_code,
                CivicSnapshot.snapshot_id == snapshot_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise SnapshotError(f"snapshot {snapshot_id} già esistente per {istat_code} (non si sovrascrive)")

    if state is None:
        state = await build_state(session, istat_code)
    if state is None:
        raise SnapshotError(f"nessuno stato per {istat_code}: genera prima un report territoriale")

    kpis = compute_kpis(state)
    row = CivicSnapshot(
        istat_code=istat_code, snapshot_id=snapshot_id,
        created_at=datetime.now(timezone.utc),
        sources_version=sources_version, kpi_version=kpi_version(),
        payload_jsonb=state, kpi_jsonb=kpis,
    )
    session.add(row)
    await session.flush()
    return row


async def get_snapshot(
    session: AsyncSession, istat_code: str, snapshot_id: str
) -> CivicSnapshot | None:
    res = await session.execute(
        select(CivicSnapshot).where(
            CivicSnapshot.istat_code == istat_code, CivicSnapshot.snapshot_id == snapshot_id
        )
    )
    return res.scalar_one_or_none()


async def list_snapshots(session: AsyncSession, istat_code: str) -> list[CivicSnapshot]:
    res = await session.execute(
        select(CivicSnapshot).where(CivicSnapshot.istat_code == istat_code)
        .order_by(CivicSnapshot.snapshot_id.asc())
    )
    return list(res.scalars().all())
