"""Persistenza maturità: entità + snapshot storicizzati di qualità/assessment.

Snapshot append-only (1 riga per run, chiave assessed_at) → trend. Upsert entità
con select-then-update (portabile SQLite/Postgres, niente ON CONFLICT dialettale).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..territory_models import DatasetQuality, Entity, MaturityAssessment


async def upsert_entity(
    session: AsyncSession,
    *,
    name: str,
    ckan_org_id: str | None = None,
    entity_type: str | None = None,
    region: str | None = None,
    portal_url: str | None = None,
) -> Entity:
    """Trova l'ente per ckan_org_id (poi per name) o lo crea; aggiorna i campi noti."""
    row: Entity | None = None
    if ckan_org_id:
        row = (
            await session.execute(select(Entity).where(Entity.ckan_org_id == ckan_org_id))
        ).scalar_one_or_none()
    if row is None and name:
        row = (
            await session.execute(select(Entity).where(Entity.name == name))
        ).scalar_one_or_none()
    if row is None:
        row = Entity(
            name=name, ckan_org_id=ckan_org_id, type=entity_type,
            region=region, portal_url=portal_url,
        )
        session.add(row)
        await session.flush()
        return row
    if name:
        row.name = name
    if ckan_org_id:
        row.ckan_org_id = ckan_org_id
    if entity_type:
        row.type = entity_type
    if region:
        row.region = region
    if portal_url:
        row.portal_url = portal_url
    await session.flush()
    return row


async def save_dataset_quality(
    session: AsyncSession,
    *,
    entity_id: int,
    qualities: Iterable[Any],
    assessed_at: datetime,
    source: str = "ckan",
) -> int:
    n = 0
    for q in qualities:
        session.add(DatasetQuality(
            entity_id=entity_id, source=source, dataset_id=q.dataset_id, assessed_at=assessed_at,
            stars_5=q.stars_5, fair_f=q.fair_f, fair_a=q.fair_a, fair_i=q.fair_i, fair_r=q.fair_r,
            dcat_ap_it_compliance=q.dcat_ap_it, iso25012_jsonb=q.iso25012_detail,
            license_open_bool=q.license_open, hvd_category=q.hvd_category,
            freshness_days=q.freshness_days,
        ))
        n += 1
    await session.flush()
    return n


async def save_assessment(
    session: AsyncSession,
    *,
    entity_id: int,
    scores: Any,
    details: dict[str, Any],
    assessed_at: datetime,
) -> MaturityAssessment:
    row = MaturityAssessment(
        entity_id=entity_id, assessed_at=assessed_at,
        score_policy=scores.policy, score_portal=scores.portal, score_quality=scores.quality,
        score_impact=scores.impact, score_overall=scores.overall, level=scores.level,
        details_jsonb=details,
    )
    session.add(row)
    await session.flush()
    return row


async def get_entity(session: AsyncSession, entity_id: int) -> Entity | None:
    return await session.get(Entity, entity_id)


async def latest_assessment(session: AsyncSession, entity_id: int) -> MaturityAssessment | None:
    res = await session.execute(
        select(MaturityAssessment)
        .where(MaturityAssessment.entity_id == entity_id)
        .order_by(MaturityAssessment.assessed_at.desc(), MaturityAssessment.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def last_two_assessments(
    session: AsyncSession, entity_id: int
) -> list[MaturityAssessment]:
    """Gli ultimi due assessment (dal più recente): base del confronto di #103."""
    res = await session.execute(
        select(MaturityAssessment)
        .where(MaturityAssessment.entity_id == entity_id)
        .order_by(MaturityAssessment.assessed_at.desc(), MaturityAssessment.id.desc())
        .limit(2)
    )
    return list(res.scalars().all())


async def assessment_trend(session: AsyncSession, entity_id: int) -> list[MaturityAssessment]:
    res = await session.execute(
        select(MaturityAssessment)
        .where(MaturityAssessment.entity_id == entity_id)
        .order_by(MaturityAssessment.assessed_at.asc(), MaturityAssessment.id.asc())
    )
    return list(res.scalars().all())


async def ranking(
    session: AsyncSession, *, entity_type: str | None = None, region: str | None = None
) -> list[tuple[Entity, MaturityAssessment]]:
    """Ultimo assessment per ogni ente (filtrato per type/region), ordinato desc per overall."""
    stmt = select(Entity)
    if entity_type:
        stmt = stmt.where(Entity.type == entity_type)
    if region:
        stmt = stmt.where(Entity.region == region)
    entities = list((await session.execute(stmt)).scalars().all())
    out: list[tuple[Entity, MaturityAssessment]] = []
    for ent in entities:
        latest = await latest_assessment(session, ent.id)
        if latest is not None:
            out.append((ent, latest))
    out.sort(key=lambda pair: float(pair[1].score_overall or 0), reverse=True)
    return out
