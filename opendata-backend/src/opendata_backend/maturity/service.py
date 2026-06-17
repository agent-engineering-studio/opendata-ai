"""Orchestrazione dell'assessment di maturità di un ente.

harvest (cap) → assess (deterministico + Haiku semantico opzionale) → persisti
snapshot storicizzati → costruisci scorecard (4 dim, livello, raccomandazioni,
trend, mediana cluster). Cache Redis per (entity, base_url).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from statistics import median
from typing import Any

from opendata_core.maturity import MaturityResult, assess_entity
from opendata_core.maturity.harvest import HarvestResult, harvest_entity
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache.store import cache_get, cache_set
from ..config import Settings
from ..config_files import maturity_weights
from ..db.repositories import maturity as repo
from .semantic import semantic_clarity_map

log = logging.getLogger("opendata-backend.maturity")


def _weights() -> dict[str, float]:
    return maturity_weights()["weights"]


def _cache_key(entity: str, base_url: str | None) -> str:
    return f"od:maturity:{base_url or 'default'}:{entity.strip().lower()}"


def _details(result: MaturityResult, harvest: HarvestResult) -> dict[str, Any]:
    return {
        "n_datasets": result.n_datasets,
        "total_on_portal": harvest.total,
        "truncated": harvest.truncated,
        "insufficient_data": result.insufficient_data,
        "dimensions": result.scores.as_dict(),
        "recommendations": [
            {"code": r.code, "severity": r.severity, "dimension": r.dimension,
             "message": r.message, "affected_count": r.affected_count}
            for r in result.recommendations
        ],
    }


async def _semantic(harvest: HarvestResult, settings: Settings) -> dict[str, float]:
    if not settings.anthropic_api_key:
        return {}
    items = [
        {"id": d.id, "title": d.title or "", "description": d.description or ""}
        for d in harvest.datasets
    ]
    return await semantic_clarity_map(items, model=settings.claude_classify_model)


async def run_assessment(
    session: AsyncSession, *, entity: str, base_url: str | None, settings: Settings,
    force: bool = False, istat_code: str | None = None,
) -> dict[str, Any]:
    """Esegue (o riusa da cache) l'assessment di un ente e ritorna la scorecard.

    `istat_code` (opzionale) collega l'ente a un comune: la domanda di riuso non
    soddisfatta (gap di dato) riduce l'Impact — anello valore⇄maturità.
    """
    key = _cache_key(entity, base_url)
    if not force:
        cached = await cache_get(key)
        if cached is not None:
            return cached

    harvest = await harvest_entity(
        entity, base_url=base_url, max_datasets=settings.maturity_max_datasets
    )
    if harvest.truncated:
        log.info(
            "maturity: ente %s troncato a %d/%d dataset",
            entity, len(harvest.datasets), harvest.total,
        )
    semantic = await _semantic(harvest, settings)

    demand = {"count": 0, "items": [], "penalty": 0.0}
    if istat_code:
        from .reuse_demand import unmet_reuse_demand

        demand = await unmet_reuse_demand(session, istat_code=istat_code)
    result = assess_entity(
        list(harvest.datasets), weights=_weights(), semantic=semantic,
        reuse_demand_penalty=demand["penalty"],
    )

    assessed_at = datetime.now(timezone.utc)
    ent = await repo.upsert_entity(
        session, name=harvest.org_title or entity, ckan_org_id=harvest.ckan_org_id,
        entity_type="ente", portal_url=base_url,
    )
    await repo.save_dataset_quality(
        session, entity_id=ent.id, qualities=result.dataset_quality, assessed_at=assessed_at
    )
    details = _details(result, harvest)
    details["unmet_reuse_demand"] = demand
    await repo.save_assessment(
        session, entity_id=ent.id, scores=result.scores,
        details=details, assessed_at=assessed_at,
    )
    await session.commit()

    scorecard = await build_scorecard(session, ent.id)
    if scorecard is not None:
        await cache_set(key, scorecard, ttl_seconds=settings.maturity_cache_ttl_seconds)
    return scorecard or {}


async def _cluster_median(session: AsyncSession, entity_type: str | None) -> float | None:
    rows = await repo.ranking(session, entity_type=entity_type)
    overalls = [float(a.score_overall or 0) for _, a in rows]
    return round(median(overalls), 1) if overalls else None


async def build_scorecard(session: AsyncSession, entity_id: int) -> dict[str, Any] | None:
    """Scorecard dell'ente dall'ultimo snapshot + trend + mediana cluster."""
    ent = await repo.get_entity(session, entity_id)
    if ent is None:
        return None
    latest = await repo.latest_assessment(session, entity_id)
    if latest is None:
        return None
    details = latest.details_jsonb or {}
    trend = [
        {"assessed_at": a.assessed_at.isoformat(), "overall": float(a.score_overall or 0),
         "level": a.level}
        for a in await repo.assessment_trend(session, entity_id)
    ]
    return {
        "entity": {
            "id": ent.id, "name": ent.name, "type": ent.type, "region": ent.region,
            "ckan_org_id": ent.ckan_org_id,
        },
        "assessed_at": latest.assessed_at.isoformat(),
        "level": latest.level,
        "overall": float(latest.score_overall or 0),
        "dimensions": {
            "policy": float(latest.score_policy or 0),
            "portal": float(latest.score_portal or 0),
            "quality": float(latest.score_quality or 0),
            "impact": float(latest.score_impact or 0),
        },
        "recommendations": details.get("recommendations", []),
        "n_datasets": details.get("n_datasets"),
        "truncated": details.get("truncated"),
        "insufficient_data": details.get("insufficient_data", False),
        "unmet_reuse_demand": details.get("unmet_reuse_demand", {"count": 0, "items": [], "penalty": 0.0}),
        "trend": trend,
        "cluster_median": await _cluster_median(session, ent.type),
    }


async def build_ranking(
    session: AsyncSession, *, entity_type: str | None, region: str | None
) -> dict[str, Any]:
    rows = await repo.ranking(session, entity_type=entity_type, region=region)
    items = [
        {
            "entity": {"id": e.id, "name": e.name, "type": e.type, "region": e.region},
            "overall": float(a.score_overall or 0), "level": a.level,
            "dimensions": {
                "policy": float(a.score_policy or 0), "portal": float(a.score_portal or 0),
                "quality": float(a.score_quality or 0), "impact": float(a.score_impact or 0),
            },
        }
        for e, a in rows
    ]
    overalls = [it["overall"] for it in items]
    return {
        "count": len(items),
        "median_overall": round(median(overalls), 1) if overalls else None,
        "ranking": items,
    }
