"""CKAN tool implementations registered on the FastMCP server.

Each tool takes an optional `base_url` so the same server can query any CKAN
portal. When omitted, `CKAN_DEFAULT_BASE_URL` from the environment is used.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .ckan_client import DOWNLOADABLE_FORMATS, CkanClient

_KEEP_RESOURCE_FIELDS = {"id", "url", "name", "format", "description", "mimetype", "size"}
_KEEP_PACKAGE_FIELDS = {
    "id", "name", "title", "notes", "license_title",
    "metadata_modified", "organization", "resources", "tags",
}


def _slim_package(pkg: dict[str, Any]) -> dict[str, Any]:
    """Return a stripped-down package dict with only the fields the agent needs."""
    slim: dict[str, Any] = {k: pkg[k] for k in _KEEP_PACKAGE_FIELDS if k in pkg}
    if "notes" in slim and isinstance(slim["notes"], str) and len(slim["notes"]) > 400:
        slim["notes"] = slim["notes"][:400] + "…"
    if "organization" in slim and isinstance(slim["organization"], dict):
        slim["organization"] = slim["organization"].get("name", "")
    if "resources" in slim and isinstance(slim["resources"], list):
        slim["resources"] = [
            {k: r[k] for k in _KEEP_RESOURCE_FIELDS if k in r}
            for r in slim["resources"]
        ]
    if "tags" in slim and isinstance(slim["tags"], list):
        slim["tags"] = [t.get("name", "") for t in slim["tags"] if isinstance(t, dict)]
    return slim


def register_tools(mcp: FastMCP) -> None:
    """Register all CKAN tools on the given FastMCP instance."""

    @mcp.tool()
    async def ckan_status_show(base_url: str | None = None) -> dict[str, Any]:
        """Check a CKAN portal is reachable and return site metadata (version, extensions, site title).

        Args:
            base_url: Root URL of the CKAN portal (e.g. https://data.gov.uk). Defaults to CKAN_DEFAULT_BASE_URL.
        """
        async with CkanClient() as c:
            result = await c.action("status_show", base_url=base_url)
            return {"base_url": base_url, "status": result}

    @mcp.tool()
    async def ckan_package_search(
        q: str = "*:*",
        fq: str | None = None,
        rows: int = 5,
        start: int = 0,
        sort: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Search datasets (Solr query). Returns count, facets and result list.

        Args:
            q: Solr query string (e.g. "air quality", "title:transport").
            fq: Solr filter query (e.g. "organization:ministry-of-x").
            rows: Max results to return (default 5, hard-capped at 10 to stay within LLM context).
            start: Pagination offset.
            sort: Solr sort expression (e.g. "metadata_modified desc").
            base_url: Portal root URL.
        """
        rows = min(rows, 10)
        params: dict[str, Any] = {"q": q, "rows": rows, "start": start}
        if fq:
            params["fq"] = fq
        if sort:
            params["sort"] = sort
        async with CkanClient() as c:
            result = await c.action("package_search", base_url=base_url, params=params)
        slimmed = [_slim_package(p) for p in result.get("results", [])]
        return {"count": result.get("count", 0), "results": slimmed}

    @mcp.tool()
    async def ckan_package_show(id: str, base_url: str | None = None) -> dict[str, Any]:
        """Retrieve full metadata for a dataset (resources, tags, organization, extras).

        Args:
            id: Dataset name or UUID.
            base_url: Portal root URL.
        """
        async with CkanClient() as c:
            result = await c.action("package_show", base_url=base_url, params={"id": id})
        return _slim_package(result)

    @mcp.tool()
    async def ckan_organization_list(
        all_fields: bool = False,
        limit: int = 100,
        base_url: str | None = None,
    ) -> list[Any]:
        """List organizations on the portal.

        Args:
            all_fields: If True, returns full org objects; otherwise just names.
            limit: Max number of organizations to return.
            base_url: Portal root URL.
        """
        params = {"all_fields": str(all_fields).lower(), "limit": limit}
        async with CkanClient() as c:
            return await c.action("organization_list", base_url=base_url, params=params)

    @mcp.tool()
    async def ckan_organization_show(
        id: str,
        include_datasets: bool = False,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve metadata for an organization (optionally including its datasets).

        Args:
            id: Organization name or UUID.
            include_datasets: If True, embed datasets owned by the organization.
            base_url: Portal root URL.
        """
        params = {"id": id, "include_datasets": str(include_datasets).lower()}
        async with CkanClient() as c:
            return await c.action("organization_show", base_url=base_url, params=params)

    @mcp.tool()
    async def ckan_group_list(
        all_fields: bool = False,
        limit: int = 100,
        base_url: str | None = None,
    ) -> list[Any]:
        """List groups (thematic categories) on the portal.

        Args:
            all_fields: If True, returns full group objects; otherwise just names.
            limit: Max number of groups to return.
            base_url: Portal root URL.
        """
        params = {"all_fields": str(all_fields).lower(), "limit": limit}
        async with CkanClient() as c:
            return await c.action("group_list", base_url=base_url, params=params)

    @mcp.tool()
    async def ckan_group_show(
        id: str,
        include_datasets: bool = False,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve metadata for a group.

        Args:
            id: Group name or UUID.
            include_datasets: If True, embed datasets in the group.
            base_url: Portal root URL.
        """
        params = {"id": id, "include_datasets": str(include_datasets).lower()}
        async with CkanClient() as c:
            return await c.action("group_show", base_url=base_url, params=params)

    @mcp.tool()
    async def ckan_tag_list(
        query: str | None = None,
        all_fields: bool = False,
        base_url: str | None = None,
    ) -> list[Any]:
        """List or search tags.

        Args:
            query: Optional substring to filter tags.
            all_fields: If True, returns full tag objects; otherwise just names.
            base_url: Portal root URL.
        """
        params: dict[str, Any] = {"all_fields": str(all_fields).lower()}
        if query:
            params["query"] = query
        async with CkanClient() as c:
            return await c.action("tag_list", base_url=base_url, params=params)

    @mcp.tool()
    async def ckan_datastore_search(
        resource_id: str,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Query rows from a DataStore-backed resource (tabular data).

        Args:
            resource_id: UUID of the CKAN resource exposing a DataStore table.
            q: Optional free-text search across all fields.
            limit: Max rows to return.
            offset: Pagination offset.
            filters: Field-level filter dict, e.g. {"country": "IT"}.
            base_url: Portal root URL.
        """
        body: dict[str, Any] = {"resource_id": resource_id, "limit": limit, "offset": offset}
        if q:
            body["q"] = q
        if filters:
            body["filters"] = filters
        async with CkanClient() as c:
            return await c.action("datastore_search", base_url=base_url, json_body=body)

    @mcp.tool()
    async def ckan_datastore_search_sql(
        sql: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Execute a read-only SQL query on the CKAN DataStore.

        Args:
            sql: Read-only SQL (SELECT ...). Table name is the resource UUID.
            base_url: Portal root URL.
        """
        async with CkanClient() as c:
            return await c.action(
                "datastore_search_sql",
                base_url=base_url,
                params={"sql": sql},
            )

    @mcp.tool()
    async def ckan_resource_download(
        resource_url: str,
        format: str | None = None,
    ) -> dict[str, Any]:
        """Download the content of a CKAN resource file and return it as text.

        Use this tool ONLY for resources whose format is one of: CSV, JSON, GeoJSON, TXT.
        For all other formats (PDF, XLSX, XLS, SHP, WMS, KML, ZIP, etc.) do NOT call this
        tool — just provide the URL to the user.

        Args:
            resource_url: Direct download URL of the resource (from the resource metadata).
            format: Resource format hint (e.g. "CSV"). Optional, used only for logging.
        """
        fmt_upper = (format or "").upper()
        if fmt_upper and fmt_upper not in DOWNLOADABLE_FORMATS:
            return {
                "url": resource_url,
                "content": None,
                "note": (
                    f"Format '{format}' is not downloadable. "
                    f"Only {', '.join(sorted(DOWNLOADABLE_FORMATS))} are supported. "
                    "Provide the URL to the user instead."
                ),
            }
        async with CkanClient() as c:
            return await c.download_resource(resource_url)

    @mcp.tool()
    async def ckan_site_read(base_url: str | None = None) -> dict[str, Any]:
        """Confirm public read access and return the portal's authorization flag.

        Args:
            base_url: Portal root URL.
        """
        async with CkanClient() as c:
            result = await c.action("site_read", base_url=base_url)
            return {"base_url": base_url, "site_read": result}
