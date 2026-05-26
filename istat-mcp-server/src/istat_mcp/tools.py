"""ISTAT SDMX tool implementations registered on the FastMCP server.

All tools accept an optional `base_url` so the same server can target any
SDMX-compatible provider; when omitted, `ISTAT_SDMX_BASE_URL` is used.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .sdmx_client import SdmxClient, df_ref, data_path


# ──────────────────────────── extract helpers ───────────────────────────

def _extract_dataflows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the dataflow list out of an SDMX-JSON structure response."""
    structures = payload.get("data", payload).get("dataflows") or []
    out: list[dict[str, Any]] = []
    for df in structures:
        names = df.get("names") or {}
        name = names.get("it") or names.get("en") or df.get("name")
        out.append(
            {
                "id": df.get("id"),
                "agency": df.get("agencyID"),
                "version": df.get("version"),
                "name": name,
                "name_en": names.get("en"),
                "name_it": names.get("it"),
                "structure_ref": df.get("structure"),
                "annotations": df.get("annotations"),
            }
        )
    return out


def _filter_by_query(items: list[dict[str, Any]], query: str | None) -> list[dict[str, Any]]:
    if not query:
        return items
    q = query.lower()
    keep: list[dict[str, Any]] = []
    for it in items:
        hay = " ".join(
            str(v or "")
            for v in (it.get("id"), it.get("name"), it.get("name_en"), it.get("name_it"))
        ).lower()
        if q in hay:
            keep.append(it)
    return keep


# ──────────────────────────── territorial hierarchy ──────────────────────
#
# Static top-level entries for the ISTAT ITTER107 codelist. For the full tree
# the agent should call istat_get_codelist("IT1", "CL_ITTER107").


_TERRITORIAL_ROOT = [
    {"code": "IT", "label": "Italia", "level": "country"},
    {"code": "ITC", "label": "Nord-ovest", "level": "nuts1"},
    {"code": "ITH", "label": "Nord-est", "level": "nuts1"},
    {"code": "ITI", "label": "Centro", "level": "nuts1"},
    {"code": "ITF", "label": "Sud", "level": "nuts1"},
    {"code": "ITG", "label": "Isole", "level": "nuts1"},
]


# ──────────────────────────── registration ───────────────────────────────


def register_tools(mcp: FastMCP) -> None:
    """Register all ISTAT SDMX tools on the given FastMCP instance."""

    @mcp.tool()
    async def istat_list_dataflows(
        query: str | None = None,
        limit: int = 50,
        agency: str = "IT1",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """List dataflows (datasets) for an SDMX 2.1 agency, optionally filtered by keyword.

        Despite the legacy name, this tool works against any SDMX 2.1 endpoint —
        pass the right `agency` + `base_url` combination:
          - ISTAT:    agency="IT1",   base_url default (esploradati.istat.it)
          - Eurostat: agency="ESTAT", base_url="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
          - OECD:     agency="all",   base_url="https://sdmx.oecd.org/public/rest"

        The full catalogue is cached — subsequent calls with different queries
        are served from memory.

        Args:
            query: Case-insensitive substring matched against id / name (it+en).
            limit: Max dataflows to return.
            agency: SDMX agency id ("IT1", "ESTAT", "OECD", "all", …). Default "IT1".
            base_url: Root URL of an SDMX 2.1 endpoint. Defaults to ISTAT_SDMX_BASE_URL.
        """
        # ISTAT (and most SDMX 2.1 endpoints) accept the short agency-only form
        # `dataflow/{agency}` to list every dataflow by that agency. The longer
        # `dataflow/{agency}/all/latest` triggers HTTP 406 on esploradati.istat.it,
        # so we use the short form. agency="all" lists across all agencies (OECD).
        path = f"dataflow/{agency}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path)
        items = _extract_dataflows(payload)
        items = _filter_by_query(items, query)
        return {
            "total_in_catalogue": len(_extract_dataflows(payload)),
            "matched": len(items),
            "results": items[: max(1, limit)],
        }

    @mcp.tool()
    async def istat_get_dataflow(
        agency: str,
        flow_id: str,
        version: str = "latest",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve detailed metadata for a single dataflow, with all references resolved.

        Args:
            agency: Agency id (e.g. `IT1` for ISTAT).
            flow_id: Dataflow id (e.g. `101_12`).
            version: Dataflow version (`latest` works on recent ISTAT snapshots).
            base_url: SDMX endpoint root.
        """
        path = f"dataflow/{df_ref(agency, flow_id, version)}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path, params={"references": "all"})
        return payload

    @mcp.tool()
    async def istat_get_structure(
        agency: str,
        structure_id: str,
        version: str = "latest",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a Data Structure Definition (dimensions, attributes, codelists).

        Args:
            agency: Agency id (usually `IT1`).
            structure_id: DSD id (e.g. `DCIS_POPRES1`).
            version: DSD version (`latest` or explicit e.g. `1.0`).
            base_url: SDMX endpoint root.
        """
        path = f"datastructure/{df_ref(agency, structure_id, version)}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path, params={"references": "children"})
        return payload

    @mcp.tool()
    async def istat_get_constraints(
        dataflow_id: str,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """List the values actually available for each dimension of a dataflow.

        Wraps `/availableconstraint/{dataflowId}/all/all?mode=available`.

        Args:
            dataflow_id: Dataflow id (e.g. `101_12`).
            base_url: SDMX endpoint root.
        """
        path = f"availableconstraint/{dataflow_id}/all/all"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path, params={"mode": "available"})
        return payload

    @mcp.tool()
    async def istat_get_codelist(
        agency: str,
        codelist_id: str,
        version: str = "latest",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Resolve an ISTAT codelist with its IT/EN labels.

        Args:
            agency: Agency id (usually `IT1`).
            codelist_id: Codelist id (e.g. `CL_ITTER107`, `CL_SEXISTAT1`).
            version: Codelist version (`latest` or explicit).
            base_url: SDMX endpoint root.
        """
        path = f"codelist/{df_ref(agency, codelist_id, version)}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path)
        return payload

    @mcp.tool()
    async def istat_get_concept(
        agency: str,
        scheme_id: str,
        version: str = "latest",
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a concept scheme describing the semantic concepts behind a DSD.

        Args:
            agency: Agency id.
            scheme_id: Concept scheme id.
            version: Scheme version.
            base_url: SDMX endpoint root.
        """
        path = f"conceptscheme/{df_ref(agency, scheme_id, version)}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path)
        return payload

    @mcp.tool()
    async def istat_get_data(
        dataflow_id: str,
        key: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        last_n: int | None = None,
        first_n: int | None = None,
        detail: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Fetch observations for a dataflow as SDMX-CSV (labels=both).

        The `key` parameter filters by dimension, using the standard SDMX dot
        grammar (`dim1.dim2.dim3…`). Leave empty values for dimensions you
        want to keep wild-card. Examples:
            key = "ITH5..Y_GE65"           (region=ITH5, any sex, age≥65)
            key = ""                       (full cube)

        ⚠️ ISTAT BUG: `end_period=N` returns data up to N+1. To get data up
        to year N, pass `end_period=str(N-1)`. This is a confirmed server bug.
        Use `last_n` instead of `end_period` when possible.

        Args:
            dataflow_id: Dataflow id (e.g. `101_12`).
            key: Dot-separated dimension filter, or None for the full cube.
            start_period: Lower bound period (e.g. `2018`, `2021-Q1`).
            end_period: Upper bound period (⚠️ server returns up to end_period+1 year).
            last_n: Return only the last N observations per series.
            first_n: Return only the first N observations per series.
            detail: Amount of information: `full` (default), `dataonly` (no attributes),
                `serieskeysonly` (series list without observations — very fast),
                `nodata` (metadata only, no observations).
            base_url: SDMX endpoint root.

        Returns:
            Dict with the requested URL and the CSV payload as a string. Large
            cubes should be narrowed with `key` / `start_period` / `last_n`
            to avoid returning megabytes of CSV. Always use `first_n` or
            `last_n` when exploring a new dataset.
        """
        params: dict[str, Any] = {}
        if start_period:
            params["startPeriod"] = start_period
        if end_period:
            params["endPeriod"] = end_period
        if last_n is not None:
            params["lastNObservations"] = last_n
        if first_n is not None:
            params["firstNObservations"] = first_n
        if detail:
            params["detail"] = detail
        path = data_path(dataflow_id, key)
        async with SdmxClient(base_url=base_url) as c:
            csv = await c.get_csv(path, params=params)
        return {"path": path, "params": params, "content_type": "text/csv", "csv": csv}

    @mcp.tool()
    async def istat_territorial_codes(
        resolve_region: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        """Return the Italian territorial hierarchy used by ISTAT dataflows (CL_ITTER107).

        Without arguments this returns the top-level (country + macro-regions).
        Pass `resolve_region` to pull the full CL_ITTER107 codelist (and let
        the caller filter) via `istat_get_codelist` under the hood.

        Args:
            resolve_region: If truthy, returns the full CL_ITTER107 codelist instead of the top-level snapshot.
            base_url: SDMX endpoint root.
        """
        if not resolve_region:
            return {"source": "static", "levels": _TERRITORIAL_ROOT}
        path = f"codelist/{df_ref('IT1', 'CL_ITTER107', 'latest')}"
        async with SdmxClient(base_url=base_url) as c:
            payload = await c.get_json(path)
        return {"source": "CL_ITTER107", "payload": payload}

    @mcp.tool()
    async def istat_cache_stats() -> dict[str, Any]:
        """Diagnostic: inspect the in-memory metadata cache (size, TTL)."""
        return SdmxClient.cache_stats()
