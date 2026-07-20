"""Tests for the OpenPNRR core client and MCP tools (API mocked via pytest-httpx)."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

from opendata_core.openpnrr.client import OpenPnrrClient, OpenPnrrError
from opendata_core.openpnrr.mapping import id_from_url, parse_amount

BASE = "https://openpnrr.it/api/v1"

TERRITORIO_GIOIA = {
    "count": 1,
    "next": None,
    "previous": None,
    "results": [{
        "id": 475, "slug": "gioia-del-colle", "url": f"{BASE}/territori/475",
        "parent": f"{BASE}/territori/134", "denominazione": "Gioia del Colle",
        "istat_id": "072021", "opdm_id": 6472, "tipologia": "C", "identifier": "E038",
    }],
}

PROGETTI_PAGE = {
    "count": 166,
    "next": f"{BASE}/progetti?page=2&territori=475",
    "previous": None,
    "results": [{
        "url": f"{BASE}/progetti/184335", "uid": "abc", "codice_locale_progetto": "010006",
        "titolo": "Presidio ospedaliero", "cup": "J41",
        "misura": f"{BASE}/misure/318",
        "soggetto_attuatore": f"{BASE}/organizzazioni/74196",
        "stato_avanzamento": "in corso", "is_validato": True,
        "finanziamento_totale": "3773260.36", "finanziamento_pnrr": "3773260.36",
        "territori": [475],
    }],
}

PROGETTO_DETAIL = {
    "codice_locale_progetto": "010006", "titolo": "Presidio ospedaliero",
    "finanziamento_pnrr": "3773260.36",
    "pagamenti": [
        {"id": 1, "pagamento_tot": "1277785.88", "pagamento_pnrr": "1277785.88"},
        {"id": 2, "pagamento_tot": "500000.00", "pagamento_pnrr": "500000.00"},
    ],
}

MISURE_PAGE = {
    "count": 412, "next": None, "previous": None,
    "results": [{"id": 1, "codice_identificativo": "M1C1I1.1", "codice_misura": "1.1",
                 "componente": f"{BASE}/componenti/1", "descrizione": "Digitale PA",
                 "tipologia": "investimento", "status": "in corso", "url": f"{BASE}/misure/1"}],
}

SCADENZE_PAGE = {
    "count": 936, "next": None, "previous": None,
    "results": [{"id": 5, "descrizione_breve": "Milestone X", "status": "conclusa",
                 "ita_ue": "UE", "tempistica_completamento_anno": 2021,
                 "tempistica_completamento_trimestre": "T4", "tipologia": "milestone",
                 "url": f"{BASE}/scadenze/5"}],
}


@pytest.fixture(autouse=True)
def _clear_cache():
    OpenPnrrClient.cache_clear()
    yield
    OpenPnrrClient.cache_clear()


# ────────────────────────────── unit: mapping ──────────────────────────────


def test_parse_amount_dot_comma_and_none() -> None:
    assert parse_amount("3773260.36") == pytest.approx(3773260.36)
    assert parse_amount("1.234.567,89") == pytest.approx(1234567.89)  # it thousands+decimals
    assert parse_amount("1000,50") == pytest.approx(1000.50)
    assert parse_amount(None) is None
    assert parse_amount("") is None
    assert parse_amount("n/d") is None


def test_id_from_url() -> None:
    assert id_from_url(f"{BASE}/progetti/184335") == 184335
    assert id_from_url(f"{BASE}/progetti/184335/") == 184335
    assert id_from_url(None) is None
    assert id_from_url(f"{BASE}/progetti/lookup") is None


# ────────────────────────────── client behaviour ───────────────────────────


async def test_resolve_territorio_by_istat(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\?.*istat_id=072021.*"),
                            json=TERRITORIO_GIOIA)
    async with OpenPnrrClient() as c:
        t = await c.resolve_territorio(istat_id="072021")
    assert t is not None
    assert t.id == 475 and t.denominazione == "Gioia del Colle" and t.tipologia == "C"


async def test_no_trailing_slash_on_requests(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\?.*"), json=TERRITORIO_GIOIA)
    async with OpenPnrrClient() as c:
        await c.resolve_territorio(istat_id="072021")
    req = httpx_mock.get_requests()[0]
    assert req.url.path == "/api/v1/territori"  # niente slash finale


async def test_search_progetti_resolves_istat_then_queries(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/territori\?.*istat_id=072021.*"),
                            json=TERRITORIO_GIOIA)
    httpx_mock.add_response(url=re.compile(r".*/progetti\?.*territori=475.*"), json=PROGETTI_PAGE)
    async with OpenPnrrClient() as c:
        out = await c.search_progetti(istat_id="072021", limit=1)
    assert out["total"] == 166
    assert out["has_more"] is True and out["next_offset"] == 1
    r = out["results"][0]
    assert r["id"] == 184335  # estratto dall'url
    assert r["finanziamento_pnrr"] == pytest.approx(3773260.36)
    assert out["licenza"].startswith("ODbL")


async def test_get_progetto_sums_pagamenti(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/progetti/184335$"), json=PROGETTO_DETAIL)
    async with OpenPnrrClient() as c:
        out = await c.get_progetto(184335)
    assert out["pagamenti_totale"] == pytest.approx(1777785.88)
    assert out["source_url"].endswith("/progetti/184335")


async def test_get_progetto_rejects_non_numeric() -> None:
    async with OpenPnrrClient() as c:
        with pytest.raises(ValueError, match="non numerico"):
            await c.get_progetto("lookup")


async def test_search_misure_and_scadenze(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/misure\?.*"), json=MISURE_PAGE)
    httpx_mock.add_response(url=re.compile(r".*/scadenze\?.*"), json=SCADENZE_PAGE)
    async with OpenPnrrClient() as c:
        m = await c.search_misure(codice_misura="1.1", limit=1)
        s = await c.search_scadenze(ita_ue="UE", limit=1)
    assert m["total"] == 412 and m["results"][0]["codice_identificativo"] == "M1C1I1.1"
    assert s["total"] == 936 and s["results"][0]["tempistica_completamento_trimestre"] == "T4"


async def test_404_raises_openpnrr_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/progetti/999999$"), status_code=404, text="not found")
    async with OpenPnrrClient() as c:
        with pytest.raises(OpenPnrrError, match="Not found"):
            await c.get_progetto(999999)


async def test_offset_must_be_multiple_of_limit() -> None:
    async with OpenPnrrClient() as c:
        with pytest.raises(ValueError, match="multiplo"):
            await c.search_progetti(territori=475, limit=20, offset=5)


# ────────────────────────────── tools registration ─────────────────────────


def test_tools_registered_on_server() -> None:
    from openpnrr_mcp.server import build_server

    mcp = build_server()
    # FastMCP espone i tool registrati; verifichiamo i 6 tool minimi.
    import asyncio

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {
        "openpnrr_resolve_territorio",
        "openpnrr_search_progetti",
        "openpnrr_get_progetto",
        "openpnrr_search_misure",
        "openpnrr_search_scadenze",
        "openpnrr_reference_struttura",
    } <= names
