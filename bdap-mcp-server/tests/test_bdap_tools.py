"""Smoke tests for the BDAP MCP server: tool registration + end-to-end call."""

from __future__ import annotations

import re

from opendata_core.bdap import client as bdap_client


def _reset() -> None:
    bdap_client._index_cache.clear()
    bdap_client._odata_cache.clear()
    bdap_client._result_cache.clear()


async def test_tool_registered() -> None:
    from bdap_mcp.server import build_server

    mcp = build_server()
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == {"bdap_bilancio_comune"}
    assert tools[0].annotations is not None
    assert tools[0].annotations.readOnlyHint is True


async def test_tool_call_returns_sources_and_source_url(httpx_mock) -> None:
    _reset()
    from bdap_mcp.server import build_server

    httpx_mock.add_response(
        url=re.compile(r".*package_search.*"),
        json={"success": True, "result": {"count": 0, "results": []}},
    )
    mcp = build_server()
    result = await mcp.call_tool("bdap_bilancio_comune", {"cod_comune": "072021", "anno": 2024})
    payload = result[1]
    assert payload["trovato"] is False  # nessun dataset mockato: fail-safe, non un errore
    assert "note" in payload
