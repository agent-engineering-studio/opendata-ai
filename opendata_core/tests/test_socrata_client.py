"""Smoke tests for the Socrata Discovery/Views/SODA client (pytest-httpx)."""

from __future__ import annotations

import pytest

from opendata_core.socrata.client import (
    SocrataClient,
    SocrataError,
    _host,
    _normalize_base,
)

BASE = "https://data.cityofnewyork.us"


def test_normalize_base_default() -> None:
    from opendata_core.socrata.client import DEFAULT_BASE_URL

    assert _normalize_base(None) == DEFAULT_BASE_URL + "/"


def test_normalize_base_adds_scheme_and_strips_slash() -> None:
    assert _normalize_base("data.cityofchicago.org/") == "https://data.cityofchicago.org/"


def test_host_extracts_netloc() -> None:
    assert _host(BASE) == "data.cityofnewyork.us"


async def test_search_datasets_scopes_to_domain_by_default(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{BASE}/api/catalog/v1?q=transport&domains=data.cityofnewyork.us"
            "&limit=5&offset=0"
        ),
        json={"resultSetSize": 1, "results": [{"resource": {"id": "abcd-1234"}}]},
    )
    async with SocrataClient() as c:
        out = await c.search_datasets(base_url=BASE, q="transport", limit=5)
    assert out["total_count"] == 1
    assert out["results"][0]["resource"]["id"] == "abcd-1234"


async def test_limit_capped_at_100(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/catalog/v1?domains=data.cityofnewyork.us&limit=100&offset=0",
        json={"resultSetSize": 0, "results": []},
    )
    async with SocrataClient() as c:
        await c.search_datasets(base_url=BASE, limit=9999)  # deve venire capato a 100


async def test_dataset_calls_views_api(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/views/abcd-1234.json",
        json={"id": "abcd-1234", "name": "Alberi", "columns": []},
    )
    async with SocrataClient() as c:
        out = await c.dataset("abcd-1234", base_url=BASE)
    assert out["name"] == "Alberi"


async def test_records_path_and_soql_query(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            f"{BASE}/resource/abcd-1234.json"
            "?%24where=altezza%3E10&%24limit=20&%24offset=0"
        ),
        json=[{"id": "1"}, {"id": "2"}],
    )
    async with SocrataClient() as c:
        out = await c.records("abcd-1234", base_url=BASE, where="altezza>10")
    assert len(out) == 2


async def test_records_non_list_response_returns_empty(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/resource/abcd-1234.json?%24limit=20&%24offset=0",
        json={"error": True, "message": "unexpected shape"},
    )
    async with SocrataClient() as c:
        out = await c.records("abcd-1234", base_url=BASE)
    assert out == []


async def test_error_status_raises(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/views/missing.json",
        status_code=404,
        json={"message": "Dataset not found"},
    )
    async with SocrataClient() as c:
        with pytest.raises(SocrataError, match="Dataset not found"):
            await c.dataset("missing", base_url=BASE)
