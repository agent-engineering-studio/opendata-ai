"""Tests for the product MCP server: backend proxy client (mocked) + tool registration."""

from __future__ import annotations

import re

import pytest
from pytest_httpx import HTTPXMock

from opendata_mcp.client import BackendClient, BackendError

BASE = "http://backend.test"


def _client() -> BackendClient:
    return BackendClient(base_url=BASE, api_key="od_test", timeout=5)


# ────────────────────────────── proxy client ───────────────────────────────


async def test_search_forwards_query_and_bearer(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE}/datasets/search",
        json={"text": "trovati 2 dataset", "resources": [{"url": "http://x/a.csv"}]},
    )
    async with _client() as c:
        out = await c.search_datasets("piste ciclabili Bologna", prefer_geo=True)
    assert out["text"].startswith("trovati")
    req = httpx_mock.get_requests()[0]
    assert req.headers["authorization"] == "Bearer od_test"
    import json
    body = json.loads(req.content)
    assert body["query"] == "piste ciclabili Bologna" and body["prefer_geo"] is True


async def test_territory_report_forwards_istat(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/territory/report", json={"istat_code": "072021"})
    async with _client() as c:
        out = await c.territory_report(istat_code="072021", temi=["ambiente"])
    assert out["istat_code"] == "072021"


async def test_maturity_and_quality_and_classify(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/maturity/assess", json={"level": "Intermediate"})
    httpx_mock.add_response(url=f"{BASE}/quality/profile", json={"punteggio": 80})
    httpx_mock.add_response(url=f"{BASE}/datasets/classify", json={"scores": {"energy": 0.9}})
    async with _client() as c:
        assert (await c.maturity_assess(entity="comune-di-x"))["level"] == "Intermediate"
        assert (await c.quality_profile(content="a,b\n1,2"))["punteggio"] == 80
        cl = await c.classify(source="ckan", dataset_id="d1", dataset_name="D1",
                              taxonomy=["energy"])
        assert cl["scores"]["energy"] == 0.9


async def test_auth_error_is_clean(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/datasets/search", status_code=401, text="no")
    async with _client() as c:
        with pytest.raises(BackendError, match="autenticazione"):
            await c.search_datasets("x")


async def test_http_error_is_clean(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/quality/profile"), status_code=500, text="boom")
    async with _client() as c:
        with pytest.raises(BackendError, match="HTTP 500"):
            await c.quality_profile(content="a,b")


async def test_no_bearer_when_key_absent(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE}/datasets/search", json={"text": "ok", "resources": []})
    async with BackendClient(base_url=BASE, api_key=None, timeout=5) as c:
        await c.search_datasets("x")
    assert "authorization" not in httpx_mock.get_requests()[0].headers


# ────────────────────────────── tool layer ─────────────────────────────────


async def test_territorio_requires_istat_code() -> None:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.fastmcp.exceptions import ToolError

    from opendata_mcp import tools

    mcp = FastMCP(name="t")
    tools.register_tools(mcp)
    names = {t.name for t in await mcp.list_tools()}
    assert "territorio_analizza_comune" in names
    # missing istat_code → clean MCP error (BackendError wrapped as ToolError),
    # not a crash. No backend call is made.
    with pytest.raises(ToolError, match="istat_code"):
        await mcp.call_tool("territorio_analizza_comune", {"nome_comune": "Bari"})


def test_tools_registered_on_server() -> None:
    import asyncio

    from opendata_mcp.server import build_server

    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {
        "esplora_cerca_dataset",
        "territorio_analizza_comune",
        "maturita_scorecard_ente",
        "qualita_diagnosi_dataset",
        "classifica_dataset",
    } <= names
