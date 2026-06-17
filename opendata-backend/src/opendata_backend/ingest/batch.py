"""Batch ricorrente (Fase 5): aggiorna maturità + snapshot civici, idempotente.

Console-script `opendata-batch`, lanciabile da cron off-peak. Per ogni target:
- ri-esegue l'assessment di maturità (force → invalida/aggiorna la cache; anello
  valore⇄maturità via istat);
- crea lo snapshot civico versionato (se non esiste già → idempotente) e apre il check-in.

Lo scheduling resta all'orchestratore esterno (cron / deploy). Gli assessment sono
append-only (storicizzano il trend); gli snapshot non si sovrascrivono.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..civic.checkin import open_checkin_thread
from ..civic.snapshot import SnapshotError, create_snapshot
from ..config import Settings
from ..config_files import _load_yaml
from ..maturity.service import run_assessment

log = logging.getLogger("ingest.batch")


def load_targets() -> list[dict[str, Any]]:
    return list(_load_yaml("batch_targets.yaml").get("targets") or [])


async def run_batch(
    session: AsyncSession, *, targets: list[dict[str, Any]], settings: Settings, snapshot_id: str,
    sources_version: str | None = None,
) -> dict[str, Any]:
    """Esegue il batch per i target dati. Idempotente. Ritorna un riepilogo."""
    sv = sources_version or snapshot_id
    results: list[dict[str, Any]] = []
    for t in targets:
        entity = t["entity"]
        istat = t.get("istat")
        scorecard = await run_assessment(
            session, entity=entity, base_url=t.get("base_url"), settings=settings,
            force=True, istat_code=istat,
        )
        snap_status = "skip"
        if istat:
            try:
                await create_snapshot(session, istat_code=istat, snapshot_id=snapshot_id,
                                      sources_version=sv)
                await session.commit()
                await open_checkin_thread(session, istat_code=istat, snapshot_id=snapshot_id)
                await session.commit()
                snap_status = "created"
            except SnapshotError as exc:
                snap_status = "exists"  # idempotente: lo snapshot del periodo non si sovrascrive
                log.info("snapshot %s per %s già presente: %s", snapshot_id, istat, exc)
        results.append({
            "entity": entity, "istat": istat,
            "level": scorecard.get("level"), "overall": scorecard.get("overall"),
            "snapshot": snap_status,
        })
        log.info("batch target %s (istat=%s): livello=%s snapshot=%s",
                 entity, istat, scorecard.get("level"), snap_status)
    return {"snapshot_id": snapshot_id, "n_targets": len(results), "targets": results}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-batch",
        description="Aggiorna maturità + snapshot civici per i target (off-peak, idempotente).",
    )
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--snapshot-id", required=True, help="periodo pubblico, es. 2026-H1")
    parser.add_argument("--sources-version", default=None)
    args = parser.parse_args()
    if not args.database_url:
        parser.error("serve --database-url o la variabile DATABASE_URL")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s", stream=sys.stderr,
    )

    from ..config import get_settings
    from ..db.session import create_database

    async def _run() -> None:
        db = create_database(args.database_url)
        try:
            async with db.sessionmaker() as session:
                summary = await run_batch(
                    session, targets=load_targets(), settings=get_settings(),
                    snapshot_id=args.snapshot_id, sources_version=args.sources_version,
                )
            print(f"OK: batch {summary['snapshot_id']} su {summary['n_targets']} target")
        finally:
            await db.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
