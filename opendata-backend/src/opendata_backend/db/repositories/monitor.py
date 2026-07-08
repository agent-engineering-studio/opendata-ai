"""Persistenza monitoraggio: target da controllare + run append-only (#88).

`monitor_runs` è append-only (1 riga per run, come `maturity_assessments`) →
`latest_run` dà lo stato precedente da cui calcolare freshness/regressione/diff.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..territory_models import MonitorRun, MonitorTarget


async def list_active_targets(session: AsyncSession) -> list[MonitorTarget]:
    res = await session.execute(select(MonitorTarget).where(MonitorTarget.active.is_(True)))
    return list(res.scalars().all())


async def list_targets_by_entity(session: AsyncSession, entity_id: int) -> list[MonitorTarget]:
    res = await session.execute(select(MonitorTarget).where(MonitorTarget.entity_id == entity_id))
    return list(res.scalars().all())


async def create_target(
    session: AsyncSession,
    *,
    url: str | None = None,
    kind: str = "dataset",
    entity_id: int | None = None,
    source: str | None = None,
    dataset_id: str | None = None,
    accrual_periodicity: str | None = None,
    webhook_url: str | None = None,
    notify_email: str | None = None,
) -> MonitorTarget:
    if kind == "dataset" and not url:
        raise ValueError("un target 'dataset' richiede un url")
    if kind == "maturity" and entity_id is None:
        raise ValueError("un watch 'maturity' richiede entity_id")
    row = MonitorTarget(
        url=url, kind=kind, entity_id=entity_id, source=source, dataset_id=dataset_id,
        accrual_periodicity=accrual_periodicity, webhook_url=webhook_url, notify_email=notify_email,
    )
    session.add(row)
    await session.flush()
    return row


async def get_target(session: AsyncSession, target_id: int) -> MonitorTarget | None:
    return await session.get(MonitorTarget, target_id)


async def latest_run(session: AsyncSession, target_id: int) -> MonitorRun | None:
    res = await session.execute(
        select(MonitorRun)
        .where(MonitorRun.target_id == target_id)
        .order_by(MonitorRun.run_at.desc(), MonitorRun.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def save_run(
    session: AsyncSession,
    *,
    target_id: int,
    esito: str,
    findings: list[dict[str, Any]],
    diff: dict[str, Any],
    quality_score: float | None = None,
    notified: bool = False,
) -> MonitorRun:
    row = MonitorRun(
        target_id=target_id, esito=esito, quality_score=quality_score,
        findings_jsonb=findings, diff_jsonb=diff, notified=notified,
    )
    session.add(row)
    await session.flush()
    return row


async def run_trend(session: AsyncSession, target_id: int, *, limit: int = 20) -> list[MonitorRun]:
    res = await session.execute(
        select(MonitorRun)
        .where(MonitorRun.target_id == target_id)
        .order_by(MonitorRun.run_at.desc(), MonitorRun.id.desc())
        .limit(limit)
    )
    return list(res.scalars().all())
