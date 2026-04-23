"""Smoke tests for the CKAN HTTP client using pytest-httpx."""

from __future__ import annotations

import pytest

from ckan_mcp.ckan_client import CkanClient, CkanError


async def test_action_success(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/api/3/action/status_show",
        json={"success": True, "result": {"site_title": "Example", "ckan_version": "2.10"}},
    )
    async with CkanClient() as c:
        result = await c.action("status_show", base_url="https://example.org")
    assert result["site_title"] == "Example"


async def test_action_failure_raises(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="https://example.org/api/3/action/package_show?id=missing",
        json={"success": False, "error": {"message": "Not found"}},
    )
    async with CkanClient() as c:
        with pytest.raises(CkanError):
            await c.action("package_show", base_url="https://example.org", params={"id": "missing"})
