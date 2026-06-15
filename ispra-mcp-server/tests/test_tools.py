"""Tests for the IdroGEO client and MCP tool — fixture = real API response."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from opendata_core.ispra.client import IspraClient, IspraError
from opendata_core.ispra.mapping import comune_uid

BASE = "https://idrogeo.isprambiente.it/api"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "idrogeo_barletta.json").read_text()
)


@pytest.fixture(autouse=True)
def _clear_cache():
    IspraClient.cache_clear()
    yield
    IspraClient.cache_clear()


def test_comune_uid_accepts_both_forms() -> None:
    assert comune_uid("072006") == 72006
    assert comune_uid(110002) == 110002
    with pytest.raises(ValueError):
        comune_uid("bari")


async def test_risk_indicators_parses_real_payload(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/pir/comuni/110002", json=FIXTURE)
    async with IspraClient(base_url=BASE) as c:
        ind = await c.risk_indicators("110002")

    assert ind.nome == "Barletta"
    assert ind.area_kmq == pytest.approx(149.448)
    assert ind.popolazione_residente == 92798
    # Aggregato frane P3+P4 — il numero chiave per i vincoli.
    assert ind.frane_p3p4 is not None
    assert ind.frane_p3p4.area_kmq == pytest.approx(0.065)
    # Idraulica P3: 13.894% dell'area comunale, 434 residenti esposti.
    p3 = next(s for s in ind.idraulica if s.classe == "p3")
    assert p3.area_pct == pytest.approx(13.894)
    assert p3.popolazione == 434
    # Frane per classe, dalla più severa.
    assert [s.classe for s in ind.frane] == ["p4", "p3", "p2", "p1", "aa"]
    assert ind.source_url.endswith("/pir/comuni/110002")
    assert "CC BY-SA 3.0" in ind.licenza


async def test_zero_padded_code_hits_int_uid(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/pir/comuni/72006", json=FIXTURE)
    async with IspraClient(base_url=BASE) as c:
        ind = await c.risk_indicators("072006")
    assert ind.cod_comune == "072006"


async def test_unknown_comune_is_actionable(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/pir/comuni/999999", status_code=404)
    async with IspraClient(base_url=BASE) as c:
        with pytest.raises(IspraError, match="codice ISTAT"):
            await c.risk_indicators("999999")


async def test_server_registers_tool_with_annotations() -> None:
    from ispra_mcp.server import build_server

    tools = await build_server().list_tools()
    assert {t.name for t in tools} == {"ispra_risk_indicators"}
    assert tools[0].annotations is not None and tools[0].annotations.readOnlyHint is True


async def test_tool_output_has_sources_and_source_url(httpx_mock: HTTPXMock) -> None:
    from ispra_mcp.server import build_server

    httpx_mock.add_response(url=f"{BASE}/pir/comuni/110002", json=FIXTURE)
    mcp = build_server()
    result = await mcp.call_tool("ispra_risk_indicators", {"cod_comune": "110002"})
    payload = result[1]
    assert payload["nome"] == "Barletta"
    assert payload["source_url"].endswith("/pir/comuni/110002")
    assert "CC BY-SA 3.0" in payload["sources"][0]["licenza"]
