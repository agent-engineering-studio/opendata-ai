"""Tests per l'ingest dell'anagrafica comuni (peer group, spec 08)."""

from __future__ import annotations

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.ingest.comuni import ingest_records, normalize_record

RAW = [
    {"nome": "Barletta", "codice": "110002", "popolazione": 94239,
     "regione": {"codice": "16", "nome": "Puglia"}, "provincia": {"codice": 110}},
    {"nome": "Bari", "codice": "072006", "popolazione": 315933,
     "regione": {"codice": "16", "nome": "Puglia"}, "provincia": {"codice": 72}},
    {"nome": "Rotto", "codice": "xx", "popolazione": None,
     "regione": {}, "provincia": {}},  # scartato
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


def test_normalize_record_pads_and_validates() -> None:
    rec = normalize_record(RAW[0])
    assert rec == {
        "cod_comune": "110002", "nome": "Barletta", "cod_provincia": "110",
        "cod_regione": "16", "popolazione": 94239,
    }
    bari = normalize_record(RAW[1])
    assert bari["cod_provincia"] == "072"  # zero-padded a 3
    assert normalize_record(RAW[2]) is None  # codice non valido → scartato


async def test_ingest_is_idempotent(engine: AsyncEngine) -> None:
    records = [r for r in (normalize_record(x) for x in RAW) if r]
    assert await ingest_records(engine, records) == 2
    assert await ingest_records(engine, records) == 2  # secondo run: upsert
    async with engine.connect() as conn:
        n = (await conn.execute(select(func.count()).select_from(ComuneAnagrafica))).scalar()
    assert n == 2
