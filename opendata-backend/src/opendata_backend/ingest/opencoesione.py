"""Ingest the OpenCoesione bulk CSV (progetti_esteso) into `opendata.oc_progetti`.

Discovery on the real bulk files (2026-06-12):
  - National archives: https://opencoesione.gov.it/it/opendata/progetti_esteso.zip
    (all cycles) and progetti_esteso_<ciclo>.zip with the DASH cycle form
    (e.g. progetti_esteso_2014-2020.zip).
  - Regional archives: .../it/opendata/regioni/progetti_esteso_<SIGLA>[_<ciclo>].zip
    (e.g. progetti_esteso_PUG_2014-2020.zip).
  - The zip member name is date-stamped (progetti_esteso_PUG_2021-2027_20260228.csv)
    → always pick the first *.csv member, never assume the name.
  - CSV: ';' delimited, UTF-8 with BOM, 202 columns. Amounts use the Italian
    decimal comma. COD_COMUNE is MULTI-VALUED (':::'-joined 9-digit codes,
    region(3)+province(3)+progressive(3)) → exploded into one row per comune
    with ISTAT-normalised codes ('016071059' → comune '071059', provincia
    '071', regione '16').

Upsert is idempotent per (clp, cod_comune): each batch deletes the keys it is
about to insert, then inserts — portable SQL (works on Postgres and on the
SQLite test suite), no dialect-specific ON CONFLICT.

Licence of the bulk data: CC BY 4.0 (cite OpenCoesione downstream).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx
from sqlalchemy import delete, insert, tuple_
from sqlalchemy.ext.asyncio import AsyncEngine

from opendata_core.opencoesione.mapping import normalize_ciclo, parse_amount

from ..db.models import OcProgetto

log = logging.getLogger("ingest.opencoesione")

BULK_BASE_URL = os.getenv(
    "OPENCOESIONE_BULK_BASE_URL", "https://opencoesione.gov.it/it/opendata"
)
DOWNLOAD_TIMEOUT = float(os.getenv("OPENCOESIONE_BULK_TIMEOUT", "600"))
DEFAULT_BATCH_SIZE = 1000

_CICLO_IN_DESCR = re.compile(r"(\d{4})\s*[-–]\s*(\d{4})")

#: CSV columns consumed by the slim record (the full row goes into `raw`).
_COL_CLP = "COD_LOCALE_PROGETTO"
_COL_TITOLO = "OC_TITOLO_PROGETTO"
_COL_TEMA = "OC_TEMA_SINTETICO"
_COL_NATURA = "CUP_DESCR_NATURA"
_COL_STATO = "OC_STATO_PROGETTO"
_COL_CICLO = "OC_DESCR_CICLO"
_COL_FINANZ = "OC_FINANZ_TOT_PUB_NETTO"
_COL_PAGAMENTI = "TOT_PAGAMENTI"
_COL_COMUNI = "COD_COMUNE"
_COL_PROVINCE = "COD_PROVINCIA"
_COL_REGIONI = "COD_REGIONE"
_COL_ATTUATORE = "OC_DENOM_ATTUATORE"


def bulk_url(ciclo: str | None = None, regione: str | None = None) -> str:
    """Build the bulk archive URL for an optional cycle and/or region sigla.

    `ciclo` accepts both '2014-2020' and '2014_2020'; filenames use the dash
    form. `regione` is the OpenCoesione sigla (PUG, LOM, …), case-insensitive.
    """
    ciclo_dash = normalize_ciclo(ciclo).replace("_", "-") if ciclo else None
    if regione:
        name = f"progetti_esteso_{regione.strip().upper()}"
        if ciclo_dash:
            name += f"_{ciclo_dash}"
        return f"{BULK_BASE_URL}/regioni/{name}.zip"
    name = "progetti_esteso"
    if ciclo_dash:
        name += f"_{ciclo_dash}"
    return f"{BULK_BASE_URL}/{name}.zip"


# ───────────────────────────── normalisation ─────────────────────────────


def _split_multi(value: str | None) -> list[str]:
    return [t.strip() for t in (value or "").split(":::") if t.strip()]


def _ciclo_from_descr(descr: str | None) -> str | None:
    """'Ciclo di programmazione 2021-2027' → '2021_2027' (mapping form)."""
    m = _CICLO_IN_DESCR.search(descr or "")
    if not m:
        return None
    try:
        return normalize_ciclo(f"{m.group(1)}_{m.group(2)}")
    except ValueError:
        return None


def _decompose_code9(token: str) -> tuple[str | None, str | None, str]:
    """9-digit bulk localisation code → (regione, provincia, comune ISTAT).

    '016071059' → ('16', '071', '071059'). 6-digit tokens are taken as
    already-ISTAT comune codes; anything else is kept verbatim as comune.
    """
    tok = token.strip()
    if len(tok) == 9 and tok.isdigit():
        return str(int(tok[:3])), tok[3:6], tok[3:]
    if len(tok) == 6 and tok.isdigit():
        return None, tok[:3], tok
    return None, None, tok


def explode_row(row: dict[str, str], *, keep_raw: bool) -> list[dict[str, Any]]:
    """Turn one bulk CSV row into one record per comune (ISTAT-normalised).

    Projects without comune-level localisation produce a single record with
    cod_comune='' and provincia/regione from their own (possibly multi-valued
    → first token) columns. `raw` is attached to the FIRST record only.
    """
    clp = (row.get(_COL_CLP) or "").strip()
    if not clp:
        return []

    base: dict[str, Any] = {
        "clp": clp,
        "titolo": (row.get(_COL_TITOLO) or "").strip() or None,
        "tema": (row.get(_COL_TEMA) or "").strip() or None,
        "natura": (row.get(_COL_NATURA) or "").strip() or None,
        "stato": (row.get(_COL_STATO) or "").strip() or None,
        "ciclo": _ciclo_from_descr(row.get(_COL_CICLO)),
        "finanziamento_totale": parse_amount(row.get(_COL_FINANZ)),
        "pagamenti": parse_amount(row.get(_COL_PAGAMENTI)),
        "soggetto_attuatore": (row.get(_COL_ATTUATORE) or "").strip() or None,
        "raw": None,
        "ingested_at": datetime.now(timezone.utc),
    }

    comuni = _split_multi(row.get(_COL_COMUNI))
    records: list[dict[str, Any]] = []
    if comuni:
        seen: set[str] = set()
        for token in comuni:
            regione, provincia, comune = _decompose_code9(token)
            if comune in seen:
                continue
            seen.add(comune)
            rec = dict(base)
            rec.update(cod_comune=comune, cod_provincia=provincia, cod_regione=regione)
            records.append(rec)
    else:
        prov_tokens = _split_multi(row.get(_COL_PROVINCE))
        reg_tokens = _split_multi(row.get(_COL_REGIONI))
        provincia = prov_tokens[0][3:] if prov_tokens and len(prov_tokens[0]) == 6 else None
        regione = str(int(reg_tokens[0])) if reg_tokens and reg_tokens[0].isdigit() else None
        records.append(
            {**base, "cod_comune": "", "cod_provincia": provincia, "cod_regione": regione}
        )

    if keep_raw and records:
        records[0]["raw"] = dict(row)
    return records


# ───────────────────────────── CSV streaming ─────────────────────────────


def iter_bulk_csv(zip_path: Path) -> Iterator[dict[str, str]]:
    """Stream rows from the first *.csv member of a bulk zip (no full load)."""
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"Nessun CSV dentro {zip_path}")
        member = members[0]
        log.info("Streaming %s from %s", member, zip_path.name)
        with zf.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            yield from csv.DictReader(text, delimiter=";")


async def download_bulk(url: str, dest_dir: Path) -> Path:
    """Stream-download the bulk zip to disk (these archives reach hundreds of MB)."""
    dest = dest_dir / url.rstrip("/").split("/")[-1]
    log.info("Downloading %s", url)
    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Bulk non trovato: {url} — verifica sigla regione/ciclo "
                    "(es. --regione PUG --ciclo 2014-2020)."
                )
            resp.raise_for_status()
            with dest.open("wb") as f:
                async for chunk in resp.aiter_bytes(1 << 20):
                    f.write(chunk)
    log.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


# ───────────────────────────── upsert ─────────────────────────────


async def _flush_batch(engine: AsyncEngine, batch: list[dict[str, Any]]) -> None:
    """Idempotent, portable upsert: delete the incoming keys, then insert."""
    if not batch:
        return
    table = OcProgetto.__table__
    keys = [(r["clp"], r["cod_comune"]) for r in batch]
    async with engine.begin() as conn:
        await conn.execute(
            delete(table).where(tuple_(table.c.clp, table.c.cod_comune).in_(keys))
        )
        await conn.execute(insert(table), batch)


async def ingest_csv(
    engine: AsyncEngine,
    zip_path: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
    keep_raw: bool = True,
) -> dict[str, int]:
    """Ingest a bulk zip into oc_progetti. Returns {rows_csv, records, batches}."""
    stats = {"rows_csv": 0, "records": 0, "batches": 0}
    batch: list[dict[str, Any]] = []
    pending_keys: set[tuple[str, str]] = set()
    for row in iter_bulk_csv(zip_path):
        stats["rows_csv"] += 1
        for rec in explode_row(row, keep_raw=keep_raw):
            key = (rec["clp"], rec["cod_comune"])
            if key in pending_keys:
                continue  # duplicate within the same batch would break the upsert
            pending_keys.add(key)
            batch.append(rec)
        if len(batch) >= batch_size:
            await _flush_batch(engine, batch)
            stats["records"] += len(batch)
            stats["batches"] += 1
            batch, pending_keys = [], set()
        if limit is not None and stats["rows_csv"] >= limit:
            break
    if batch:
        await _flush_batch(engine, batch)
        stats["records"] += len(batch)
        stats["batches"] += 1
    log.info(
        "Ingest done: %d CSV rows → %d records in %d batches",
        stats["rows_csv"], stats["records"], stats["batches"],
    )
    return stats


async def sync_bulk(
    engine: AsyncEngine,
    *,
    ciclo: str | None = None,
    regione: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
    keep_raw: bool = True,
) -> dict[str, int]:
    """Download the requested bulk archive and ingest it."""
    url = bulk_url(ciclo=ciclo, regione=regione)
    with tempfile.TemporaryDirectory(prefix="oc-bulk-") as tmp:
        zip_path = await download_bulk(url, Path(tmp))
        return await ingest_csv(
            engine, zip_path, batch_size=batch_size, limit=limit, keep_raw=keep_raw
        )


# ───────────────────────────── CLI ─────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-opencoesione-sync",
        description=(
            "Scarica il bulk OpenCoesione (CC BY 4.0) e popola opendata.oc_progetti. "
            "Senza argomenti scarica il dataset nazionale completo (~tutti i cicli)."
        ),
    )
    parser.add_argument("--ciclo", help="es. 2014-2020 (default: tutti i cicli)")
    parser.add_argument("--regione", help="sigla OpenCoesione, es. PUG (default: nazionale)")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="DSN Postgres (default: env DATABASE_URL)",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, help="ferma dopo N righe CSV (smoke test)")
    parser.add_argument(
        "--no-raw", action="store_true",
        help="non salvare il record grezzo 202-colonne (riduce molto lo spazio)",
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
            stats = await sync_bulk(
                db.engine,
                ciclo=args.ciclo,
                regione=args.regione,
                batch_size=args.batch_size,
                limit=args.limit,
                keep_raw=not args.no_raw,
            )
            print(
                f"OK: {stats['records']} record (da {stats['rows_csv']} righe CSV, "
                f"{stats['batches']} batch)"
            )
        finally:
            await db.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
