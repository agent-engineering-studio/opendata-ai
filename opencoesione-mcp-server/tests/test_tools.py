"""Tests for the OpenCoesione core client and MCP tools (API mocked via pytest-httpx)."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

from opendata_core.opencoesione.client import OpenCoesioneClient, OpenCoesioneError
from opendata_core.opencoesione.mapping import (
    comune_code_int,
    normalize_ciclo,
    parse_amount,
    parse_yyyymmdd,
)

BASE = "https://opencoesione.gov.it/it/api"

TERRITORI_BARI = {
    "count": 1,
    "next": None,
    "results": [
        {
            "denominazione": "Bari",
            "tipo": "C",
            "slug": "bari-comune",
            "cod_reg": 16,
            "cod_prov": 72,
            "cod_com": 72006,
        }
    ],
}

PROGETTI_PAGE = {
    "count": 12402,
    "next": f"{BASE}/progetti.json?page=2",
    "results": [
        {
            "url": f"{BASE}/progetti/4mtra111102/",
            "cod_locale_progetto": "4MTRA111102",
            "oc_titolo_progetto": "Raddoppio tratta ferroviaria",
            "oc_tema_sintetico": "Trasporti",
            "oc_stato_progetto": "In corso",
            "oc_descr_ciclo": "Ciclo di programmazione 2014-2020",
            "oc_finanz_tot_pub_netto": "421465927,95",
            "tot_pagamenti": "94137629,21",
            "percentuale_avanzamento": "22%",
            "soggetti": [],
            "territori": ["bari-comune"],
        }
    ],
}

AGGREGATI_BARI = {
    "contesto": {"nome_territorio": "Bari", "tipo_territorio": "C", "popolazione": 316736},
    "data_aggiornamento": "20260228",
    "aggregati": {
        "totali": {
            "costo_pubblico": "1000000,00",
            "pagamenti": "750000,00",
            "progetti": "100",
        },
        "stati_progetti": {
            "non_avviato": {"label": "Non avviato", "totali": {"progetti": "10"}},
            "in_corso": {"label": "In corso", "totali": {"progetti": "30"}},
            "liquidato": {"label": "Liquidato", "totali": {"progetti": "40"}},
            "concluso": {"label": "Concluso", "totali": {"progetti": "20"}},
        },
        "temi": {
            "energia": {
                "label": "Energia",
                "totali": {
                    "costo_pubblico": "200000,00",
                    "pagamenti": "50000,00",
                    "progetti": "8",
                },
            }
        },
    },
}


@pytest.fixture(autouse=True)
def _clear_shared_cache():
    # The client cache is class-level (shared across instances) — isolate tests.
    OpenCoesioneClient.cache_clear()
    yield
    OpenCoesioneClient.cache_clear()


# ───────────────────────────────── mapping ─────────────────────────────────


def test_parse_amount_italian_format() -> None:
    assert parse_amount("4363566537,13") == pytest.approx(4363566537.13)
    assert parse_amount("1.234,56") == pytest.approx(1234.56)
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount(42) == 42.0


def test_normalize_ciclo_accepts_dash_and_underscore() -> None:
    assert normalize_ciclo("2014-2020") == "2014_2020"
    assert normalize_ciclo("2014_2020") == "2014_2020"
    with pytest.raises(ValueError, match="2014_2020"):
        normalize_ciclo("2015-2021")


def test_comune_code_int_strips_leading_zeros() -> None:
    assert comune_code_int("072006") == 72006
    assert comune_code_int(72006) == 72006
    with pytest.raises(ValueError):
        comune_code_int("bari")


def test_parse_yyyymmdd() -> None:
    assert str(parse_yyyymmdd("20230430")) == "2023-04-30"
    assert parse_yyyymmdd("") is None
    assert parse_yyyymmdd("2023") is None


# ───────────────────────────────── client ──────────────────────────────────


async def test_search_projects_resolves_istat_code(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\.json.*"), json=TERRITORI_BARI)
    httpx_mock.add_response(url=re.compile(r".*/progetti\.json.*"), json=PROGETTI_PAGE)

    async with OpenCoesioneClient(base_url=BASE) as c:
        out = await c.search_projects(cod_comune="072006", tema="trasporti", limit=20)

    assert out["total"] == 12402
    assert out["has_more"] is True
    assert out["next_offset"] == 20
    rec = out["results"][0]
    assert rec["clp"] == "4MTRA111102"
    assert rec["finanziamento_totale"] == pytest.approx(421465927.95)
    assert "territorio=bari-comune" in out["source_url"]
    assert "tema=trasporti" in out["source_url"]
    # The projects request must use the slug, never the raw ISTAT code.
    progetti_req = [r for r in httpx_mock.get_requests() if "progetti.json" in str(r.url)][0]
    assert progetti_req.url.params["territorio"] == "bari-comune"
    assert "cod_comune" not in progetti_req.url.params


async def test_search_projects_rejects_unknown_tema() -> None:
    async with OpenCoesioneClient(base_url=BASE) as c:
        with pytest.raises(ValueError, match="ricerca-e-innovazione"):
            await c.search_projects(territorio="bari-comune", tema="turbofinanza")


async def test_search_projects_rejects_misaligned_offset() -> None:
    async with OpenCoesioneClient(base_url=BASE) as c:
        with pytest.raises(ValueError, match="multiplo"):
            await c.search_projects(territorio="bari-comune", limit=20, offset=7)


async def test_get_project_normalises_clp(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/progetti/4mtra111102.json",
        json={"cod_locale_progetto": "4MTRA111102", "oc_stato_progetto": "In corso"},
    )
    async with OpenCoesioneClient(base_url=BASE) as c:
        out = await c.get_project("4MTRA111102")
    assert out["cod_locale_progetto"] == "4MTRA111102"
    assert out["source_url"].endswith("/progetti/4mtra111102.json")


async def test_unknown_territory_is_actionable(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=re.compile(r".*/territori\.json.*"), json={"count": 0, "results": []}
    )
    async with OpenCoesioneClient(base_url=BASE) as c:
        with pytest.raises(OpenCoesioneError, match="999999"):
            await c.search_projects(cod_comune="999999")


async def test_throttle_429_then_success(httpx_mock: HTTPXMock) -> None:
    url = re.compile(r".*/territori\.json.*")
    httpx_mock.add_response(
        url=url,
        status_code=429,
        json={"detail": "La richiesta è stata limitata. Expected available in 1 second."},
    )
    httpx_mock.add_response(url=url, json=TERRITORI_BARI)
    async with OpenCoesioneClient(base_url=BASE) as c:
        t = await c.resolve_territorio(cod_comune="072006")
    assert t is not None and t.slug == "bari-comune"


# ───────────────────────────── funding capacity ────────────────────────────


async def test_funding_capacity_math(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\.json.*"), json=TERRITORI_BARI)
    httpx_mock.add_response(
        url=re.compile(r".*/aggregati/territori/bari-comune\.json.*"), json=AGGREGATI_BARI
    )
    async with OpenCoesioneClient(base_url=BASE) as c:
        cap = await c.funding_capacity("072006")

    assert cap.territorio == "Bari"
    assert cap.popolazione == 316736
    assert cap.finanziato_totale == pytest.approx(1_000_000.0)
    assert cap.pagamenti_totali == pytest.approx(750_000.0)
    assert cap.spend_ratio == pytest.approx(0.75)
    assert cap.progetti_totali == 100
    # liquidato (40) + concluso (20) count as completed.
    assert cap.progetti_conclusi == 60
    assert cap.conclusi_ratio == pytest.approx(0.6)
    assert cap.source_url.endswith("/aggregati/territori/bari-comune.json")


async def test_funding_capacity_tema_slice(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\.json.*"), json=TERRITORI_BARI)
    httpx_mock.add_response(
        url=re.compile(r".*/aggregati/territori/bari-comune\.json.*"), json=AGGREGATI_BARI
    )
    async with OpenCoesioneClient(base_url=BASE) as c:
        cap = await c.funding_capacity("072006", tema="energia")

    assert cap.tema == "energia"
    assert cap.spend_ratio == pytest.approx(0.25)
    assert cap.progetti_totali == 8
    # Per-theme slices have no per-state breakdown.
    assert cap.progetti_conclusi is None
    assert cap.breakdown_stati == []


async def test_funding_capacity_unknown_tema_lists_available(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\.json.*"), json=TERRITORI_BARI)
    httpx_mock.add_response(
        url=re.compile(r".*/aggregati/territori/bari-comune\.json.*"), json=AGGREGATI_BARI
    )
    async with OpenCoesioneClient(base_url=BASE) as c:
        with pytest.raises(OpenCoesioneError, match="energia"):
            await c.funding_capacity("072006", tema="trasporti")


# ─────────────────────────────── MCP server ────────────────────────────────


async def test_server_registers_all_tools() -> None:
    from opencoesione_mcp.server import build_server

    mcp = build_server()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "opencoesione_search_projects",
        "opencoesione_get_project",
        "opencoesione_territorial_aggregates",
        "opencoesione_search_soggetti",
        "opencoesione_funding_capacity",
        "opencoesione_reference_values",
    }
    for t in tools:
        assert t.annotations is not None
        assert t.annotations.readOnlyHint is True
        assert t.annotations.destructiveHint is False


async def test_tool_output_has_sources_block(httpx_mock: HTTPXMock) -> None:
    from opencoesione_mcp.server import build_server

    httpx_mock.add_response(url=re.compile(r".*/territori\.json.*"), json=TERRITORI_BARI)
    httpx_mock.add_response(
        url=re.compile(r".*/aggregati/territori/bari-comune\.json.*"), json=AGGREGATI_BARI
    )
    mcp = build_server()
    result = await mcp.call_tool("opencoesione_funding_capacity", {"cod_comune": "072006"})
    # FastMCP returns (content, structured) — inspect the structured payload.
    structured = result[1]
    payload = structured.get("result", structured)
    assert payload["spend_ratio"] == pytest.approx(0.75)
    assert payload["sources"][0]["url"].endswith("/aggregati/territori/bari-comune.json")
    assert "CC BY-SA 3.0" in payload["sources"][0]["licenza"]
