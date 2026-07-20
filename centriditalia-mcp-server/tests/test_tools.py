"""Tests for the Centri d'Italia core client (local CSV mirror) and MCP tools."""

from __future__ import annotations

import os

import pytest
from pytest_httpx import HTTPXMock

from opendata_core.centriditalia.client import CentriDItaliaClient
from opendata_core.centriditalia.mapping import DATASETS, norm_istat, parse_float, parse_int

CENTRI_CSV = (
    "rilevazione_data,centro_id,centro_denominazione,comune_denominazione,"
    "comune_codice_istat,provincia_cm_codice_istat,regione_codice_istat,ente_gestore,"
    "costo_giornaliero_per_ospite,presenze_giornaliere,capienza,operativita,"
    "tipologia_centro,tipologia_ospiti,procedura_affidamento\n"
    "2022-12-31,189440,BASILIADE,L'AQUILA,066049,066,13,COOP,22.77,50,50,ATTIVO,CAS ADULTI,ADULTI,GARA\n"
    "2023-12-31,189440,BASILIADE,L'AQUILA,066049,066,13,COOP,24.00,40,60,ATTIVO,CAS ADULTI,ADULTI,GARA\n"
    "2023-12-31,200001,ALTRO,L'AQUILA,066049,066,13,COOP2,20.00,10,30,ATTIVO,HOTSPOT,ADULTI,GARA\n"
    "2023-12-31,300000,FUORI,MILANO,015146,015,03,COOP3,30.0,5,10,CHIUSO,CAS ADULTI,ADULTI,GARA\n"
)
SAIP_CSV = (
    "progetto_codice,data_riferimento,ente_locale_progetto,tipologia,capienza,presenze,"
    "comune_denominazione,comune_codice_istat,provincia_cm_codice_istat,provincia_cm_sigla,"
    "regione_denominazione,regione_codice_istat\n"
    "P1,2024,Comune AQ,ORDINARI,20,15,L'AQUILA,066049,066,AQ,ABRUZZO,13\n"
)
SAIS_CSV = (
    "sai_struttura_id,sai_struttura_denominazione,comune_denominazione,comune_codice_istat,"
    "provincia_cm_codice_istat,regione_codice_istat,sai_struttura_tipologia,sai_progetto_codice,"
    "sai_progetto_denominazione,data_inizio,data_fine,data_rilevazione,capienza,presenze_giornaliere\n"
    "S1,Struttura 1,L'AQUILA,066049,066,13,APPARTAMENTO,P1,Prog 1,2020-01-01,,2024,10,8\n"
)
CSV_BY_DATASET = {"centri": CENTRI_CSV, "sai_progetti": SAIP_CSV, "sai_strutture": SAIS_CSV}


def _client_with_mirror(tmp_path) -> CentriDItaliaClient:
    """Build a mirror from the small CSVs above (no network)."""
    db = os.path.join(tmp_path, "m.sqlite")
    c = CentriDItaliaClient(db_path=db)
    sources = {}
    for name, txt in CSV_BY_DATASET.items():
        p = os.path.join(tmp_path, f"{name}.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(txt)
        sources[name] = p
    c._build(sources)
    return c


# ────────────────────────────── unit: mapping ──────────────────────────────


def test_parse_helpers() -> None:
    assert parse_int("50") == 50
    assert parse_int("22.77") == 22
    assert parse_int("") is None
    assert parse_float("22,77") == pytest.approx(22.77)
    assert parse_float("30.0") == pytest.approx(30.0)
    assert parse_float("n/d") is None


def test_norm_istat() -> None:
    assert norm_istat("66049", 6) == "066049"
    assert norm_istat("16", 2) == "16"
    assert norm_istat(72, 3) == "072"
    assert norm_istat(None, 6) is None


# ────────────────────────────── client queries ─────────────────────────────


async def test_search_centri_by_territory(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    aq = await c.search_centri(comune_codice_istat="066049")
    assert aq["count"] == 3  # tre righe AQ (189440 x2 + 200001)
    mi = await c.search_centri(comune_codice_istat="015146")
    assert mi["count"] == 1
    assert aq["licenza"].startswith("CC-BY 4.0")
    assert "migrantidb" in aq["source_url"]


async def test_search_centri_type_filter(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    out = await c.search_centri(regione_codice_istat="13", tipologia_centro="hotspot")
    assert out["count"] == 1
    assert out["results"][0]["centro_id"] == "200001"


async def test_get_centro_time_series(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    out = await c.get_centro("189440")
    assert out["count"] == 2
    assert [r["costo_giornaliero_per_ospite"] for r in out["results"]] == [22.77, 24.0]


async def test_territorio_aggregate_uses_latest_per_centro(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    agg = (await c.territorio_aggregate(comune_codice_istat="066049"))["aggregato"]
    # 189440 latest(2023): cap 60, pres 40; 200001: cap 30, pres 10 → 90 / 50
    assert agg["centri"] == 2
    assert agg["capienza_totale"] == 90
    assert agg["presenze_totali"] == 50
    assert agg["costo_medio_giornaliero"] == pytest.approx(22.0)  # (24+20)/2


async def test_territorio_aggregate_requires_code(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    with pytest.raises(ValueError, match="codice ISTAT"):
        await c.territorio_aggregate()


async def test_search_sai(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    p = await c.search_sai(kind="progetti", regione_codice_istat="13")
    s = await c.search_sai(kind="strutture", comune_codice_istat="066049")
    assert p["count"] == 1 and p["results"][0]["progetto_codice"] == "P1"
    assert s["count"] == 1 and s["results"][0]["sai_struttura_id"] == "S1"


async def test_reference_values(tmp_path) -> None:
    c = _client_with_mirror(str(tmp_path))
    ref = await c.reference_values()
    assert set(ref["tipologia_centro"]) == {"CAS ADULTI", "HOTSPOT"}
    assert ref["licenza"].startswith("CC-BY 4.0")


# ─────────────────────── download → build (mocked S3) ───────────────────────


async def test_ensure_ready_downloads_and_builds(tmp_path, httpx_mock: HTTPXMock) -> None:
    for name, spec in DATASETS.items():
        httpx_mock.add_response(url=spec["url"], text=CSV_BY_DATASET[name],
                                headers={"content-type": "text/csv"})
    db = os.path.join(str(tmp_path), "dl.sqlite")
    async with CentriDItaliaClient(db_path=db) as c:
        info = await c.ensure_ready(force=True)
    assert info["version"] == "v2026"
    assert info["rows"]["centri"] == 4
    assert os.path.exists(db)


# ────────────────────────────── tools registration ─────────────────────────


def test_tools_registered_on_server() -> None:
    import asyncio

    from centriditalia_mcp.server import build_server

    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {
        "centriditalia_search_centri",
        "centriditalia_get_centro",
        "centriditalia_territorio_aggregate",
        "centriditalia_search_sai",
        "centriditalia_reference_values",
    } <= names
