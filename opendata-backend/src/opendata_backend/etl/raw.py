"""Versioning idempotente dei raw (Layer 1) in opendata.raw_ingest.

`record_raw` calcola lo sha256 del payload canonicalizzato e inserisce solo se nuovo
→ rieseguibile senza duplicati. La licenza è sempre tracciata.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.territory_models import RawIngest


def payload_sha(payload: Any) -> str:
    """sha256 del payload canonicalizzato (chiavi ordinate)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def record_raw(
    session: AsyncSession, *, source: str, payload: Any, license: str,
    dataset_id: str | None = None,
) -> tuple[RawIngest, bool]:
    """Registra un raw se non già presente (per sha). Ritorna (riga, created)."""
    sha = payload_sha(payload)
    existing = (
        await session.execute(select(RawIngest).where(RawIngest.sha == sha))
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    row = RawIngest(source=source, dataset_id=dataset_id, license=license, sha=sha,
                    payload_jsonb=payload if isinstance(payload, dict) else {"value": payload})
    session.add(row)
    await session.flush()
    return row, True
