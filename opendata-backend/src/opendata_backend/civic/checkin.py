"""Check-in periodico: alla creazione di un nuovo snapshot apre un thread di
revisione community con il riepilogo automatico "cosa è cambiato"."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repositories import community as community_repo
from .diff import checkin_summary, diff_snapshots
from .snapshot import get_snapshot, list_snapshots


async def open_checkin_thread(
    session: AsyncSession, *, istat_code: str, snapshot_id: str
) -> dict[str, Any] | None:
    """Crea il thread di revisione per lo snapshot (vs il precedente). None se è il primo."""
    snaps = await list_snapshots(session, istat_code)
    ids = [s.snapshot_id for s in snaps]
    if snapshot_id not in ids:
        return None
    idx = ids.index(snapshot_id)
    if idx == 0:
        return None  # primo snapshot: niente confronto, niente check-in
    prev = await get_snapshot(session, istat_code, ids[idx - 1])
    cur = await get_snapshot(session, istat_code, snapshot_id)
    if prev is None or cur is None:
        return None

    diff = diff_snapshots(
        state_a=prev.payload_jsonb or {}, kpi_a=prev.kpi_jsonb or {},
        state_b=cur.payload_jsonb or {}, kpi_b=cur.kpi_jsonb or {},
    )
    summary = checkin_summary(diff, snapshot_a=ids[idx - 1], snapshot_b=snapshot_id)

    thread = await community_repo.create_thread(
        session, istat_code=istat_code, topic_type="snapshot", topic_ref=snapshot_id,
        title=f"Revisione {snapshot_id} — cosa è cambiato", created_by="system",
    )
    await community_repo.create_post(session, thread_id=thread.id, body=summary, author="system")
    await session.flush()
    return {"thread_id": thread.id, "summary": summary,
            "opere_concluse": diff["summary"]["opere_concluse"]}
