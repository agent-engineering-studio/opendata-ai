"""Router /monitor — stato dell'ultimo controllo per i target di un ente (#88).

Sola lettura: il runner (`opendata-monitor`, cron) è l'unico a scrivere. Espone
l'ultimo esito per ciascun target monitorato dell'ente, così la UI può
mostrare "tutto ok" o le segnalazioni senza dover leggere direttamente il DB.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import ClerkUser
from ..db.repositories import monitor as repo
from ..db.session import get_db_session
from ..shared.ratelimit import enforce_rate_limit

log = logging.getLogger("opendata-backend.monitor.router")
router = APIRouter(tags=["monitor"])


@router.get("/monitor/{entity_id}")
async def get_entity_monitor_status(
    entity_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: ClerkUser = Depends(enforce_rate_limit),
) -> dict[str, Any]:
    """Ultimo esito di monitoraggio per ogni target dell'ente. Lista vuota se non ci sono target."""
    targets = await repo.list_targets_by_entity(session, entity_id)
    log.info("/monitor/%d subject=%s n_target=%d", entity_id, user.subject, len(targets))

    out: list[dict[str, Any]] = []
    for t in targets:
        run = await repo.latest_run(session, t.id)
        out.append({
            "id": t.id,
            "url": t.url,
            "source": t.source,
            "dataset_id": t.dataset_id,
            "accrual_periodicity": t.accrual_periodicity,
            "active": t.active,
            "ultimo_run": None if run is None else {
                "run_at": run.run_at.isoformat(),
                "esito": run.esito,
                "quality_score": float(run.quality_score) if run.quality_score is not None else None,
                "findings": run.findings_jsonb or [],
                "diff": run.diff_jsonb or {},
            },
        })
    return {"entity_id": entity_id, "targets": out}
