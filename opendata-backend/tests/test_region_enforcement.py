"""Enforcement dello scope regionale sugli endpoint territoriali (issue #191, F3).

`enforce_region_scope` rifiuta (HTTP 422) un comune fuori dalla regione
configurata (`REGION`), usando `ComuneAnagrafica.cod_regione` come base
autorevole e degradando al prefisso provincia quando l'anagrafica non copre il
comune. `REGION` vuoto → fallback al legacy `TERRITORIO_PROVINCE`.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opendata_backend.config import Settings
from opendata_backend.db.models import Base, ComuneAnagrafica
from opendata_backend.shared.scope import enforce_region_scope


def _strip_schema(metadata: MetaData) -> None:
    for t in metadata.tables.values():
        t.schema = None


def _settings(**kw) -> Settings:
    return Settings(**kw)  # type: ignore[call-arg]


@pytest.fixture
async def session() -> AsyncSession:
    _strip_schema(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        s.add(ComuneAnagrafica(cod_comune="072021", nome="Gioia del Colle",
                               cod_provincia="072", cod_regione="16", popolazione=27000))
        s.add(ComuneAnagrafica(cod_comune="015146", nome="Milano",
                               cod_provincia="015", cod_regione="03", popolazione=1400000))
        await s.commit()
        yield s
    await engine.dispose()


# ── REGION impostato: confronto autorevole su cod_regione ─────────────


async def test_in_region_via_anagrafica_ok(session: AsyncSession) -> None:
    # Non solleva: Gioia del Colle è in Puglia (cod_regione=16).
    await enforce_region_scope(session, "072021", _settings(region_istat="16"))


async def test_out_of_region_via_anagrafica_rejected(session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as ei:
        await enforce_region_scope(session, "015146", _settings(region_istat="16"))
    assert ei.value.status_code == 422
    assert "fuori dalla regione" in ei.value.detail


# ── REGION impostato ma comune non in anagrafica → fallback provincia ─


async def test_unknown_comune_falls_back_to_province_in_scope(session: AsyncSession) -> None:
    # 072010 non è in anagrafica, ma la provincia 072 è di Puglia (da regioni.yaml).
    await enforce_region_scope(session, "072010", _settings(region_istat="16"))


async def test_unknown_comune_out_of_province_rejected(session: AsyncSession) -> None:
    # 015010 non è in anagrafica e la provincia 015 non è di Puglia → 422.
    with pytest.raises(HTTPException) as ei:
        await enforce_region_scope(session, "015010", _settings(region_istat="16"))
    assert ei.value.status_code == 422


# ── REGION vuoto: retro-compat con TERRITORIO_PROVINCE ────────────────


async def test_no_region_legacy_province_scope(session: AsyncSession) -> None:
    s = _settings(region_istat="", territorio_province="072")
    await enforce_region_scope(session, "072021", s)  # ok
    with pytest.raises(HTTPException):
        await enforce_region_scope(session, "015146", s)  # fuori provincia


async def test_no_scope_configured_is_noop(session: AsyncSession) -> None:
    s = _settings(region_istat="", territorio_province="")
    # Nessun limite (dev): qualunque comune passa.
    await enforce_region_scope(session, "015146", s)


async def test_missing_cod_comune_is_noop(session: AsyncSession) -> None:
    await enforce_region_scope(session, None, _settings(region_istat="16"))
    await enforce_region_scope(session, "", _settings(region_istat="16"))


async def test_no_session_falls_back_to_province(session: AsyncSession) -> None:
    # Senza sessione DB non si può leggere l'anagrafica → prefisso provincia.
    await enforce_region_scope(None, "072021", _settings(region_istat="16"))  # ok
    with pytest.raises(HTTPException):
        await enforce_region_scope(None, "015146", _settings(region_istat="16"))
