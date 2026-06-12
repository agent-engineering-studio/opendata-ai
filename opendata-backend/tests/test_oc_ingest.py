"""Tests for the OpenCoesione bulk ingest (CSV → opendata.oc_progetti).

Runs on in-memory SQLite (schema stripped, like the other DB tests): the
ingest SQL is intentionally portable (delete+insert upsert, no ON CONFLICT).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from opendata_backend.db.models import Base, OcProgetto
from opendata_backend.ingest.opencoesione import bulk_url, explode_row, ingest_csv

CSV_HEADER = (
    "COD_LOCALE_PROGETTO;OC_TITOLO_PROGETTO;OC_TEMA_SINTETICO;CUP_DESCR_NATURA;"
    "OC_STATO_PROGETTO;OC_DESCR_CICLO;OC_FINANZ_TOT_PUB_NETTO;TOT_PAGAMENTI;"
    "COD_COMUNE;COD_PROVINCIA;COD_REGIONE;OC_DENOM_ATTUATORE"
)
CSV_ROWS = [
    # Single-comune project (Bari).
    "1ABC;Riqualificazione waterfront;Ambiente;REALIZZAZIONE DI LAVORI PUBBLICI;"
    "Concluso;Ciclo di programmazione 2014-2020;1000000,50;900000,00;"
    "016072006;016072;016;COMUNE DI BARI",
    # Multi-comune project (':::' — Vico del Gargano + Vieste).
    "2DEF;Strada a scorrimento veloce;Trasporti e mobilità;REALIZZAZIONE DI LAVORI PUBBLICI;"
    "In corso;Ciclo di programmazione 2021-2027;500000,00;100000,00;"
    "016071059:::016071060;016071;016;ANAS SPA",
    # Province-level project, no comune localisation.
    "3GHI;Programma formazione;Occupazione e lavoro;ACQUISTO DI SERVIZI;"
    "Liquidato;Ciclo di programmazione 2014-2020;200000,00;200000,00;"
    ";016072;016;REGIONE PUGLIA",
]


def _strip_schema(metadata: MetaData) -> None:
    for table in metadata.tables.values():
        table.schema = None


@pytest.fixture
async def engine() -> AsyncEngine:
    _strip_schema(Base.metadata)
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def bulk_zip(tmp_path: Path) -> Path:
    csv_path = tmp_path / "progetti_esteso_TEST_20260228.csv"
    # The real files are UTF-8 with BOM — reproduce it.
    csv_path.write_text("﻿" + CSV_HEADER + "\n" + "\n".join(CSV_ROWS) + "\n", "utf-8")
    zip_path = tmp_path / "progetti_esteso_TEST.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(csv_path, csv_path.name)
    return zip_path


# ───────────────────────────── unit: URL + explode ─────────────────────────


def test_bulk_url_variants() -> None:
    assert bulk_url() .endswith("/it/opendata/progetti_esteso.zip")
    assert bulk_url(ciclo="2014-2020").endswith("/progetti_esteso_2014-2020.zip")
    assert bulk_url(ciclo="2014_2020").endswith("/progetti_esteso_2014-2020.zip")
    assert bulk_url(regione="pug").endswith("/regioni/progetti_esteso_PUG.zip")
    assert bulk_url(ciclo="2021-2027", regione="PUG").endswith(
        "/regioni/progetti_esteso_PUG_2021-2027.zip"
    )
    with pytest.raises(ValueError):
        bulk_url(ciclo="1999-2004")


def test_explode_row_multi_comune_and_normalisation() -> None:
    row = dict(zip(CSV_HEADER.split(";"), CSV_ROWS[1].split(";")))
    records = explode_row(row, keep_raw=True)
    assert len(records) == 2
    assert [r["cod_comune"] for r in records] == ["071059", "071060"]
    assert all(r["cod_provincia"] == "071" and r["cod_regione"] == "16" for r in records)
    assert all(r["ciclo"] == "2021_2027" for r in records)
    assert records[0]["finanziamento_totale"] == pytest.approx(500000.0)
    # raw only on the first comune row.
    assert records[0]["raw"] is not None
    assert records[1]["raw"] is None


def test_explode_row_without_comune_falls_back_to_provincia() -> None:
    row = dict(zip(CSV_HEADER.split(";"), CSV_ROWS[2].split(";")))
    records = explode_row(row, keep_raw=False)
    assert len(records) == 1
    rec = records[0]
    assert rec["cod_comune"] == ""
    assert rec["cod_provincia"] == "072"
    assert rec["cod_regione"] == "16"
    assert rec["raw"] is None


# ───────────────────────────── integration: ingest ─────────────────────────


async def test_ingest_explodes_normalises_and_is_idempotent(
    engine: AsyncEngine, bulk_zip: Path
) -> None:
    stats = await ingest_csv(engine, bulk_zip)
    assert stats["rows_csv"] == 3
    assert stats["records"] == 4  # 1 + 2 (exploded) + 1 (no comune)

    async with engine.connect() as conn:
        total = (await conn.execute(select(func.count()).select_from(OcProgetto))).scalar()
        assert total == 4
        bari = (
            await conn.execute(select(OcProgetto).where(OcProgetto.cod_comune == "072006"))
        ).mappings().one()
        assert bari["clp"] == "1ABC"
        assert float(bari["finanziamento_totale"]) == pytest.approx(1000000.50)
        assert float(bari["pagamenti"]) == pytest.approx(900000.0)
        assert bari["ciclo"] == "2014_2020"
        assert bari["stato"] == "Concluso"
        assert bari["soggetto_attuatore"] == "COMUNE DI BARI"

    # Second run: delete+insert upsert keeps the row count stable.
    stats2 = await ingest_csv(engine, bulk_zip)
    assert stats2["records"] == 4
    async with engine.connect() as conn:
        total = (await conn.execute(select(func.count()).select_from(OcProgetto))).scalar()
        assert total == 4


async def test_ingest_respects_limit_and_no_raw(engine: AsyncEngine, bulk_zip: Path) -> None:
    stats = await ingest_csv(engine, bulk_zip, limit=1, keep_raw=False)
    assert stats["rows_csv"] == 1
    async with engine.connect() as conn:
        rows = (await conn.execute(select(OcProgetto.raw))).scalars().all()
    assert rows == [None]
