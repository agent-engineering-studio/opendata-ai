"""Smoke tests for the SearXNG-backed web client using pytest-httpx."""

from __future__ import annotations

import pytest

from opendata_core.web.client import WebClient, WebSearchError, _normalize_base

SEARX = "http://searxng:8080"


def test_normalize_base_default():
    assert _normalize_base(None).startswith("http")


def test_normalize_base_strips_trailing_slash():
    assert _normalize_base("http://searxng:8080/") == "http://searxng:8080/"


def test_normalize_base_adds_scheme():
    assert _normalize_base("searxng:8080") == "http://searxng:8080/"


async def test_search_returns_slim_results(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{SEARX}/search?q=comune+borgo+turismo&format=json",
        json={
            "results": [
                {
                    "url": "https://comune.example.gov.it/turismo",
                    "title": "Borgo che riparte: il turismo lento",
                    "content": "Il comune ha lanciato un progetto di turismo lento...",
                    "engine": "google",
                    "publishedDate": "2025-09-01",
                },
                {"url": "https://x.example.org/y", "title": "Altro", "content": "snippet"},
                {"title": "no url — skipped", "content": "x"},  # dropped (no url)
            ]
        },
    )
    async with WebClient(base_url=SEARX) as c:
        results = await c.search("comune borgo turismo")
    assert len(results) == 2  # the url-less entry is dropped
    first = results[0]
    assert first["url"] == "https://comune.example.gov.it/turismo"
    assert first["title"].startswith("Borgo")
    assert first["date"] == "2025-09-01"
    assert first["snippet"].startswith("Il comune")


async def test_search_respects_max_results(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{SEARX}/search?q=mobilita&format=json",
        json={"results": [{"url": f"https://e/{i}", "title": str(i)} for i in range(10)]},
    )
    async with WebClient(base_url=SEARX) as c:
        results = await c.search("mobilita", max_results=3)
    assert len(results) == 3


async def test_search_non_json_raises_with_hint(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url=f"{SEARX}/search?q=x&format=json",
        text="<html>format not enabled</html>",
        headers={"content-type": "text/html"},
    )
    async with WebClient(base_url=SEARX) as c:
        with pytest.raises(WebSearchError, match="settings.yml"):
            await c.search("x")


async def test_unsupported_provider_raises():
    async with WebClient(provider="tavily", base_url=SEARX) as c:
        with pytest.raises(WebSearchError, match="Unsupported"):
            await c.search("x")


async def test_fetch_returns_truncated_text(httpx_mock):
    page = "https://comune.example.gov.it/delibera"
    httpx_mock.add_response(
        method="GET",
        url=page,
        text="x" * 2000,
        headers={"content-type": "text/html; charset=utf-8"},
    )
    async with WebClient(base_url=SEARX) as c:
        result = await c.fetch(page, max_bytes=500)
    assert result["truncated"] is True
    assert len(result["content"]) == 500
    assert result["size_bytes"] == 2000


async def test_fetch_http_error_raises(httpx_mock):
    bad = "https://comune.example.gov.it/missing"
    httpx_mock.add_response(method="GET", url=bad, status_code=404)
    async with WebClient(base_url=SEARX) as c:
        with pytest.raises(WebSearchError, match="Failed to fetch"):
            await c.fetch(bad)
