"""Best-effort MCP specialist connection (degraded mode).

A specialist whose MCP server is unreachable at startup must NOT crash the
backend (crash-loop): `_add_mcp_specialist` logs and skips it, leaving the
other specialists to serve. Only a genuine `CancelledError` (cooperative
shutdown) must still propagate.
"""

from __future__ import annotations

import asyncio

import pytest

from opendata_backend.factory import OrchestratorSession


def _bare_session() -> OrchestratorSession:
    # Bypass __init__: the helper only needs self._enter_mcp_tool/_enter_agent.
    return OrchestratorSession.__new__(OrchestratorSession)


@pytest.mark.asyncio
async def test_add_mcp_specialist_skips_on_connect_failure() -> None:
    s = _bare_session()

    async def boom(_name: str, _url: str, _desc: str):
        raise RuntimeError("connection refused")

    async def _enter_agent(*_a, **_k):
        raise AssertionError("agent must not be built when MCP connect fails")

    s._enter_mcp_tool = boom  # type: ignore[method-assign]
    s._enter_agent = _enter_agent  # type: ignore[method-assign]

    participants: list = []
    # Must neither raise nor append — the backend keeps starting in degraded mode.
    await s._add_mcp_specialist(
        chat_client=object(),
        instructions="x",
        name="web",
        url="http://web-mcp:8088/mcp",
        description="d",
        default_options=None,
        participants=participants,
    )
    assert participants == []


@pytest.mark.asyncio
async def test_add_mcp_specialist_appends_on_success() -> None:
    s = _bare_session()
    sentinel_tool = object()
    sentinel_agent = object()
    captured: dict = {}

    async def ok(_name: str, _url: str, _desc: str):
        return sentinel_tool

    async def _enter_agent(chat_client, instructions, name, tools, default_options):
        captured.update(name=name, tools=tools)
        return sentinel_agent

    s._enter_mcp_tool = ok  # type: ignore[method-assign]
    s._enter_agent = _enter_agent  # type: ignore[method-assign]

    participants: list = []
    await s._add_mcp_specialist(
        chat_client=object(),
        instructions="x",
        name="ckan",
        url="http://ckan-mcp:8080/mcp",
        description="d",
        default_options=None,
        participants=participants,
    )
    assert participants == [sentinel_agent]
    assert captured == {"name": "ckan", "tools": [sentinel_tool]}


@pytest.mark.asyncio
async def test_add_mcp_specialist_propagates_cancellation() -> None:
    s = _bare_session()

    async def cancel(_name: str, _url: str, _desc: str):
        raise asyncio.CancelledError

    s._enter_mcp_tool = cancel  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await s._add_mcp_specialist(
            chat_client=object(),
            instructions="x",
            name="web",
            url="u",
            description="d",
            default_options=None,
            participants=[],
        )
