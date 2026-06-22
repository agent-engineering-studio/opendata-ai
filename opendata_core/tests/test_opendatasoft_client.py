"""Smoke tests for the OpenDataSoft Explore v2.1 client (pytest-httpx)."""

from __future__ import annotations

import pytest

from opendata_core.opendatasoft.client import (
    OpenDataSoftClient,
    OpenDataSoftError,
    _normalize_base,
)

BASE = "https://public.opendatasoft.com"


def test_normalize_base_default() -> None:
    assert _normalize_base(None) == BASE + "/"


def test_normalize_base_adds_scheme_and_strips_slash() -> None:
    assert _normalize_base("data.issy.com/") == "https://data.issy.com/"


async def test_search_datasets_builds_url_and_params(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/explore/v2.1/catalog/datasets?where=transport&limit=5&offset=0",
        json={"total_count": 1, "results": [{"dataset_id": "x"}]},
    )
    async with OpenDataSoftClient() as c:
        out = await c.search_datasets(where="transport", limit=5)
    assert out["total_count"] == 1
    assert out["results"][0]["dataset_id"] == "x"


async def test_limit_capped_at_100(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/explore/v2.1/catalog/datasets?limit=100&offset=0",
        json={"total_count": 0, "results": []},
    )
    async with OpenDataSoftClient() as c:
        await c.search_datasets(limit=9999)  # deve venire capato a 100


async def test_records_path_and_query(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=(
            "https://data.issy.com/api/explore/v2.1/catalog/datasets/arbres/records"
            "?where=hauteur%3E10&limit=20&offset=0"
        ),
        json={"total_count": 2, "results": [{"id": 1}, {"id": 2}]},
    )
    async with OpenDataSoftClient() as c:
        out = await c.records("arbres", base_url="data.issy.com", where="hauteur>10")
    assert out["total_count"] == 2


async def test_error_status_raises(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE}/api/explore/v2.1/catalog/datasets/missing",
        status_code=404,
        json={"message": "Dataset not found", "error_code": "DatasetNotFoundError"},
    )
    async with OpenDataSoftClient() as c:
        with pytest.raises(OpenDataSoftError, match="Dataset not found"):
            await c.dataset("missing")
