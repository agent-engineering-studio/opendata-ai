"""Socrata tool implementations registered on the FastMCP server.

Each tool takes an optional `base_url` so the same server can query any
Socrata portal. When omitted, `SOCRATA_DEFAULT_BASE_URL` from the
environment is used.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from opendata_core.socrata import SocrataClient

_DESC_MAX = 400


def _truncate(text: str | None) -> str | None:
    if isinstance(text, str) and len(text) > _DESC_MAX:
        return text[:_DESC_MAX] + "…"
    return text


def _slim_catalog_result(item: dict[str, Any]) -> dict[str, Any]:
    """Stripped catalog search result: id + the useful `resource`/`classification` fields."""
    resource = item.get("resource") or {}
    classification = item.get("classification") or {}
    slim: dict[str, Any] = {"dataset_id": resource.get("id")}
    if resource.get("name"):
        slim["title"] = resource["name"]
    if resource.get("description"):
        slim["description"] = _truncate(resource["description"])
    if resource.get("type"):
        slim["type"] = resource["type"]
    if resource.get("updatedAt"):
        slim["updated_at"] = resource["updatedAt"]
    if classification.get("domain_category"):
        slim["category"] = classification["domain_category"]
    if classification.get("domain_tags"):
        slim["tags"] = classification["domain_tags"]
    if item.get("permalink"):
        slim["permalink"] = item["permalink"]
    return slim


def _slim_view(item: dict[str, Any]) -> dict[str, Any]:
    """Stripped dataset metadata (Views API): id/name/description + column schema."""
    slim: dict[str, Any] = {"dataset_id": item.get("id")}
    for k in ("name", "category"):
        if item.get(k):
            slim[k] = item[k]
    if item.get("description"):
        slim["description"] = _truncate(item["description"])
    if item.get("tags"):
        slim["tags"] = item["tags"]
    columns = item.get("columns")
    if isinstance(columns, list):
        slim["columns"] = [
            {"name": c.get("name"), "field_name": c.get("fieldName"), "type": c.get("dataTypeName")}
            for c in columns
        ]
    return slim


def register_tools(mcp: FastMCP) -> None:
    """Register all Socrata tools on the given FastMCP instance."""

    @mcp.tool()
    async def socrata_search_datasets(
        q: str | None = None,
        domains: str | None = None,
        limit: int = 5,
        offset: int = 0,
        order: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Search a portal's dataset catalog (Discovery API). Returns total_count + slim list.

        Args:
            q: Free-text query.
            domains: Comma-separated Socrata domains to search. Defaults to the
                target portal's own domain (derived from `base_url`).
            limit: Max datasets to return (default 5, capped at 10 for LLM context).
            offset: Pagination offset.
            order: Discovery API ordering (e.g. "relevance", "name", "-updatedAt").
            base_url: Portal root URL (e.g. https://data.cityofnewyork.us). Defaults
                to SOCRATA_DEFAULT_BASE_URL.
        """
        limit = min(int(limit), 10)
        async with SocrataClient() as c:
            result = await c.search_datasets(
                base_url=base_url, q=q, domains=domains, limit=limit,
                offset=int(offset), order=order,
            )
        slimmed = [_slim_catalog_result(r) for r in result.get("results", [])]
        return {"total_count": result.get("total_count", 0), "results": slimmed}

    @mcp.tool()
    async def socrata_dataset_show(dataset_id: str, base_url: str | None = None) -> dict[str, Any]:
        """Retrieve full metadata for a dataset (name, description, column schema).

        Args:
            dataset_id: The dataset's four-four identifier (from socrata_search_datasets).
            base_url: Portal root URL.
        """
        async with SocrataClient() as c:
            result = await c.dataset(dataset_id, base_url=base_url)
        return _slim_view(result)

    @mcp.tool()
    async def socrata_dataset_records(
        dataset_id: str,
        where: str | None = None,
        select: str | None = None,
        order_by: str | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Query rows of a dataset (tabular data) via SoQL. Returns count + records.

        Args:
            dataset_id: The dataset's four-four identifier.
            where: SoQL filter (e.g. 'altezza>10 AND specie="Quercia"').
            select: SoQL select/aggregation (e.g. "specie, count(*) as tot").
            order_by: SoQL ordering (e.g. "altezza DESC").
            q: SoQL full-text search term.
            limit: Max rows (default 20, capped at 100).
            offset: Pagination offset.
            base_url: Portal root URL.
        """
        async with SocrataClient() as c:
            records = await c.records(
                dataset_id, base_url=base_url, where=where, select=select,
                order_by=order_by, q=q, limit=min(int(limit), 100), offset=int(offset),
            )
        return {"count": len(records), "results": records}
