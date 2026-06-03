"""Cache-aware classification orchestrator.

Flow (in order):
  1. Redis lookup `od:classify:<source>:<dataset_id>:<hash(taxonomy)>` — if hit,
     return the cached dict immediately.
  2. Postgres lookup on `opendata.classifications` keyed by the same triple —
     if hit, hydrate Redis and return.
  3. Anthropic Haiku 4.5 call.
  4. Persist into Postgres + Redis.

The function is intentionally pure on its inputs; the caller wires in the
DB session and (optionally) injects the classifier — making it trivial to
stub in tests without touching the network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import classify as classify_cache
from ..db.repositories import classifications as classifications_repo
from .anthropic_client import Classifier

log = logging.getLogger("opendata-backend.classify.service")


class _ClassifierLike(Protocol):
    async def classify(
        self,
        *,
        dataset_name: str,
        dataset_description: str | None,
        taxonomy: list[str],
    ): ...


@dataclass
class ClassificationResult:
    source: str
    dataset_id: str
    taxonomy: list[str]
    scores: dict[str, float]
    model: str
    cached: bool


async def classify_dataset(
    session: AsyncSession,
    classifier: _ClassifierLike | Classifier,
    *,
    source: str,
    dataset_id: str,
    dataset_name: str,
    dataset_description: str | None,
    taxonomy: list[str],
) -> ClassificationResult:
    if not taxonomy:
        raise ValueError("taxonomy must contain at least one category")

    # Layer 1 — Redis (24h).
    cached = await classify_cache.get(source, dataset_id, taxonomy)
    if cached is not None:
        log.info("classify cache HIT (redis) source=%s dataset=%s", source, dataset_id)
        return ClassificationResult(
            source=source,
            dataset_id=dataset_id,
            taxonomy=taxonomy,
            scores=cached["scores"],
            model=cached.get("model", "unknown"),
            cached=True,
        )

    # Layer 2 — Postgres durable cache.
    row = await classifications_repo.get(
        session, source=source, dataset_id=dataset_id, taxonomy=taxonomy
    )
    if row is not None:
        log.info("classify cache HIT (postgres) source=%s dataset=%s", source, dataset_id)
        payload = {"scores": row.result.get("scores", {}), "model": row.model}
        await classify_cache.set(source, dataset_id, taxonomy, payload)
        return ClassificationResult(
            source=source,
            dataset_id=dataset_id,
            taxonomy=taxonomy,
            scores=row.result.get("scores", {}),
            model=row.model,
            cached=True,
        )

    # Layer 3 — call the LLM.
    log.info("classify cache MISS — calling Haiku source=%s dataset=%s", source, dataset_id)
    resp = await classifier.classify(
        dataset_name=dataset_name,
        dataset_description=dataset_description,
        taxonomy=taxonomy,
    )

    # Persist + warm Redis.
    await classifications_repo.upsert(
        session,
        source=source,
        dataset_id=dataset_id,
        taxonomy=taxonomy,
        result={"scores": resp.scores, "usage": resp.usage},
        model=resp.model,
    )
    await session.commit()
    await classify_cache.set(
        source, dataset_id, taxonomy, {"scores": resp.scores, "model": resp.model}
    )

    return ClassificationResult(
        source=source,
        dataset_id=dataset_id,
        taxonomy=taxonomy,
        scores=resp.scores,
        model=resp.model,
        cached=False,
    )
