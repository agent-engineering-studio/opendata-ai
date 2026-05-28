"""Classification results — durable cache of `/datasets/classify` outputs."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Classification


def taxonomy_hash(taxonomy: list[str]) -> str:
    """Stable hash of a sorted taxonomy list — keys the classify cache."""
    canonical = json.dumps(sorted(taxonomy), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


async def get(
    session: AsyncSession,
    *,
    source: str,
    dataset_id: str,
    taxonomy: list[str],
) -> Classification | None:
    res = await session.execute(
        select(Classification).where(
            Classification.source == source,
            Classification.dataset_id == dataset_id,
            Classification.taxonomy_hash == taxonomy_hash(taxonomy),
        )
    )
    return res.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    source: str,
    dataset_id: str,
    taxonomy: list[str],
    result: dict,
    model: str,
) -> Classification:
    stmt = (
        insert(Classification)
        .values(
            source=source,
            dataset_id=dataset_id,
            taxonomy_hash=taxonomy_hash(taxonomy),
            result=result,
            model=model,
        )
        .on_conflict_do_update(
            constraint="uq_classifications_dataset_taxonomy",
            set_={"result": result, "model": model},
        )
        .returning(Classification)
    )
    res = await session.execute(stmt)
    return res.scalar_one()
