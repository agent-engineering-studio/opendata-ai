"""Smoke tests for the ODS MCP server: tool registration + dataset slimming."""

from __future__ import annotations

from ods_mcp.server import build_server
from ods_mcp.tools import _slim_dataset


async def test_tools_registered() -> None:
    mcp = build_server()
    names = {t.name for t in await mcp.list_tools()}
    assert {"ods_search_datasets", "ods_dataset_show", "ods_dataset_records"} <= names


def test_slim_dataset_keeps_useful_metas_and_truncates() -> None:
    item = {
        "dataset_id": "popolazione",
        "metas": {"default": {
            "title": "Popolazione",
            "description": "x" * 500,
            "theme": ["Società"],
            "records_count": 8000,
            "unused": "drop me",
        }},
    }
    slim = _slim_dataset(item)
    assert slim["dataset_id"] == "popolazione"
    assert slim["title"] == "Popolazione"
    assert slim["records_count"] == 8000
    assert "unused" not in slim
    assert slim["description"].endswith("…") and len(slim["description"]) == 401


def test_slim_dataset_handles_missing_metas() -> None:
    slim = _slim_dataset({"dataset_id": "x"})
    assert slim == {"dataset_id": "x"}
