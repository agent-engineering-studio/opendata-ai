"""Ingest dell'anagrafica comuni (codice ISTAT, nome, regione, popolazione).

Fonte (discovery 2026-06-12): nessun CSV ISTAT unico porta codici E
popolazione; il dataset `comuni-json` (github.com/matteocontrini/comuni-json,
dati ISTAT, popolazione da censimento 2011) li ha entrambi in un singolo JSON
con codici zero-padded. Per il peer group (fascia popolazione 0.5×–2×) la
stalenza del censimento è irrilevante; i criteri sono dichiarati negli
output. URL sovrascrivibile via COMUNI_ANAGRAFICA_URL.

Upsert idempotente: delete+insert per batch (portabile, come oc_progetti).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import httpx
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from ..db.models import ComuneAnagrafica

log = logging.getLogger("ingest.comuni")

COMUNI_URL = os.getenv(
    "COMUNI_ANAGRAFICA_URL",
    "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json",
)
DOWNLOAD_TIMEOUT = float(os.getenv("COMUNI_ANAGRAFICA_TIMEOUT", "120"))
BATCH_SIZE = 2000


def normalize_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Un record comuni-json → riga comuni_anagrafica (codici normalizzati)."""
    cod = str(rec.get("codice") or "").strip()
    nome = str(rec.get("nome") or "").strip()
    if len(cod) != 6 or not cod.isdigit() or not nome:
        return None
    prov = rec.get("provincia") or {}
    prov_cod = str(prov.get("codice") or "").strip()
    reg = rec.get("regione") or {}
    reg_cod = str(reg.get("codice") or "").strip()
    pop = rec.get("popolazione")
    return {
        "cod_comune": cod,
        "nome": nome,
        "cod_provincia": prov_cod.zfill(3) if prov_cod.isdigit() else cod[:3],
        "cod_regione": str(int(reg_cod)) if reg_cod.isdigit() else None,
        "popolazione": int(pop) if isinstance(pop, (int, float)) else None,
    }


async def ingest_records(engine: AsyncEngine, records: list[dict[str, Any]]) -> int:
    """Upsert idempotente di righe già normalizzate."""
    table = ComuneAnagrafica.__table__
    total = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        keys = [r["cod_comune"] for r in batch]
        async with engine.begin() as conn:
            await conn.execute(delete(table).where(table.c.cod_comune.in_(keys)))
            await conn.execute(insert(table), batch)
        total += len(batch)
    return total


async def sync_comuni(engine: AsyncEngine, url: str | None = None) -> int:
    """Scarica il dataset e popola opendata.comuni_anagrafica."""
    src = url or COMUNI_URL
    log.info("Downloading %s", src)
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(src)
        resp.raise_for_status()
        raw = resp.json()
    if not isinstance(raw, list):
        raise RuntimeError(f"Payload inatteso da {src}: atteso un array JSON")
    seen: set[str] = set()
    records = []
    for rec in raw:
        norm = normalize_record(rec) if isinstance(rec, dict) else None
        if norm and norm["cod_comune"] not in seen:
            seen.add(norm["cod_comune"])
            records.append(norm)
    n = await ingest_records(engine, records)
    log.info("Anagrafica comuni: %d record ingeriti (da %d grezzi)", n, len(raw))
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-comuni-sync",
        description="Popola opendata.comuni_anagrafica (codici ISTAT + popolazione).",
    )
    parser.add_argument("--url", default=None, help=f"sorgente JSON (default: {COMUNI_URL})")
    parser.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL"),
        help="DSN Postgres (default: env DATABASE_URL)",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("serve --database-url o la variabile DATABASE_URL")

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stderr,
    )

    from ..db.session import create_database

    async def _run() -> None:
        db = create_database(args.database_url)
        try:
            n = await sync_comuni(db.engine, url=args.url)
            print(f"OK: {n} comuni in anagrafica")
        finally:
            await db.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
