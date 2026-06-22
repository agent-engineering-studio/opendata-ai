"""OpenDataSoft tool implementations registered on the FastMCP server.

Each tool takes an optional `base_url` so the same server can query any ODS
portal. When omitted, `ODS_DEFAULT_BASE_URL` from the environment is used.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from opendata_core.opendatasoft import OpenDataSoftClient

_KEEP_META = {"title", "description", "theme", "keyword", "publisher", "license",
              "modified", "records_count"}


def _slim_dataset(item: dict[str, Any]) -> dict[str, Any]:
    """Stripped dataset descriptor: id + the useful `metas.default` fields."""
    metas = item.get("metas") or {}
    default = metas.get("default") or {}
    slim: dict[str, Any] = {"dataset_id": item.get("dataset_id")}
    for k in _KEEP_META:
        if default.get(k) not in (None, "", []):
            slim[k] = default[k]
    if isinstance(slim.get("description"), str) and len(slim["description"]) > 400:
        slim["description"] = slim["description"][:400] + "…"
    return slim


def register_tools(mcp: FastMCP) -> None:
    """Register all OpenDataSoft tools on the given FastMCP instance."""

    @mcp.tool()
    async def ods_search_datasets(
        q: str | None = None,
        where: str | None = None,
        limit: int = 5,
        offset: int = 0,
        order_by: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Search a portal's dataset catalog. Returns total_count + slim dataset list.

        Args:
            q: Free-text query (mapped to an ODSQL full-text `where` when `where` is omitted).
            where: Raw ODSQL filter clause (e.g. 'publisher:"Comune di X"'). Overrides `q`.
            limit: Max datasets to return (default 5, capped at 10 for LLM context).
            offset: Pagination offset.
            order_by: ODSQL ordering (e.g. "modified desc").
            base_url: Portal root URL (e.g. https://public.opendatasoft.com). Defaults to ODS_DEFAULT_BASE_URL.
        """
        limit = min(int(limit), 10)
        effective_where = where or q
        async with OpenDataSoftClient() as c:
            result = await c.search_datasets(
                base_url=base_url, where=effective_where, limit=limit,
                offset=int(offset), order_by=order_by,
            )
        slimmed = [_slim_dataset(d) for d in result.get("results", [])]
        return {"total_count": result.get("total_count", 0), "results": slimmed}

    @mcp.tool()
    async def ods_dataset_show(dataset_id: str, base_url: str | None = None) -> dict[str, Any]:
        """Retrieve full metadata for a dataset (fields, metas, attachments).

        Args:
            dataset_id: The dataset identifier (from ods_search_datasets).
            base_url: Portal root URL.
        """
        async with OpenDataSoftClient() as c:
            result = await c.dataset(dataset_id, base_url=base_url)
        # Surface a slim view + the field schema, keeping payload small.
        slim = _slim_dataset(result)
        fields = result.get("fields")
        if isinstance(fields, list):
            slim["fields"] = [
                {"name": f.get("name"), "type": f.get("type"), "label": f.get("label")}
                for f in fields
            ]
        return slim

    @mcp.tool()
    async def ods_dataset_records(
        dataset_id: str,
        where: str | None = None,
        select: str | None = None,
        order_by: str | None = None,
        limit: int = 20,
        offset: int = 0,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Query rows of a dataset (tabular data) via ODSQL. Returns total_count + records.

        Args:
            dataset_id: The dataset identifier.
            where: ODSQL filter (e.g. 'anno=2023 AND comune:"Bari"' or a free-text term).
            select: ODSQL select/aggregation (e.g. "comune, sum(popolazione) as tot").
            order_by: ODSQL ordering (e.g. "popolazione desc").
            limit: Max rows (default 20, capped at 100).
            offset: Pagination offset.
            base_url: Portal root URL.
        """
        async with OpenDataSoftClient() as c:
            return await c.records(
                dataset_id, base_url=base_url, where=where, select=select,
                order_by=order_by, limit=min(int(limit), 100), offset=int(offset),
            )
