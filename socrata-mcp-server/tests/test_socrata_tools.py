"""Smoke tests for the Socrata MCP server: tool registration + slimming helpers."""

from __future__ import annotations

from socrata_mcp.server import build_server
from socrata_mcp.tools import _slim_catalog_result, _slim_view


async def test_tools_registered() -> None:
    mcp = build_server()
    names = {t.name for t in await mcp.list_tools()}
    assert {"socrata_search_datasets", "socrata_dataset_show", "socrata_dataset_records"} <= names


def test_slim_catalog_result_keeps_useful_fields_and_truncates() -> None:
    item = {
        "resource": {
            "id": "abcd-1234",
            "name": "Alberi",
            "description": "x" * 500,
            "type": "dataset",
            "updatedAt": "2026-01-01T00:00:00.000Z",
        },
        "classification": {"domain_category": "Ambiente", "domain_tags": ["alberi", "verde"]},
        "permalink": "https://data.example.org/d/abcd-1234",
    }
    slim = _slim_catalog_result(item)
    assert slim["dataset_id"] == "abcd-1234"
    assert slim["title"] == "Alberi"
    assert slim["category"] == "Ambiente"
    assert slim["tags"] == ["alberi", "verde"]
    assert slim["description"].endswith("…") and len(slim["description"]) == 401


def test_slim_catalog_result_handles_missing_resource() -> None:
    slim = _slim_catalog_result({})
    assert slim == {"dataset_id": None}


def test_slim_view_keeps_columns_schema() -> None:
    item = {
        "id": "abcd-1234",
        "name": "Alberi",
        "description": "Censimento alberi comunali",
        "tags": ["alberi"],
        "columns": [
            {"name": "Altezza", "fieldName": "altezza", "dataTypeName": "number"},
            {"name": "Specie", "fieldName": "specie", "dataTypeName": "text"},
        ],
    }
    slim = _slim_view(item)
    assert slim["dataset_id"] == "abcd-1234"
    assert slim["columns"] == [
        {"name": "Altezza", "field_name": "altezza", "type": "number"},
        {"name": "Specie", "field_name": "specie", "type": "text"},
    ]


def test_slim_view_handles_missing_columns() -> None:
    slim = _slim_view({"id": "x"})
    assert slim == {"dataset_id": "x"}
