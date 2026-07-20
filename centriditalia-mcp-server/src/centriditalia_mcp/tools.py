"""Centri d'Italia tool implementations registered on the FastMCP server.

Thin wrappers over ``opendata_core.centriditalia.CentriDItaliaClient`` (a local
bulk-CSV mirror). Every result carries ``source_url`` (the original CSV),
``licenza`` (CC-BY 4.0) and ``refreshed_at`` (mirror refresh date), plus a
standard ``sources`` block.

The data is **aggregated per centre**, never individual — safe to surface in a
civic-analysis context (same caution as the Welfare lens).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opendata_core.centriditalia import LICENZA, CentriDItaliaClient

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

_MAX_RESULTS = 50


def _scalar(v: Any) -> Any:
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _with_sources(payload: dict[str, Any]) -> dict[str, Any]:
    url = payload.get("source_url")
    payload["sources"] = (
        [{"url": url, "estratto_il": date.today().isoformat(), "licenza": LICENZA}]
        if url else []
    )
    return payload


def register_tools(mcp: FastMCP) -> None:
    """Register all Centri d'Italia tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def centriditalia_search_centri(
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
        tipologia_centro: str | None = None,
        tipologia_ospiti: str | None = None,
        operativita: str | None = None,
        rilevazione_da: str | None = None,
        rilevazione_a: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search reception centres (CAS/CPA/hotspot) by territory, type and period.

        Returns one row per observation (the dataset is a time series), most
        recent first, with capacity, daily presences, daily cost per guest,
        managing body and convention dates.

        Args:
            comune_codice_istat: ISTAT comune code (e.g. "072021").
            provincia_cm_codice_istat: ISTAT province code (e.g. "072").
            regione_codice_istat: ISTAT region code (e.g. "16" for Puglia).
            tipologia_centro: Centre type (see centriditalia_reference_values).
            tipologia_ospiti: Guest type (see reference values).
            operativita: Operational state (e.g. "ATTIVO").
            rilevazione_da: Keep observations on/after this date (YYYY-MM-DD).
            rilevazione_a: Keep observations on/before this date (YYYY-MM-DD).
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with CentriDItaliaClient() as c:
            out = await c.search_centri(
                comune_codice_istat=_scalar(comune_codice_istat),
                provincia_cm_codice_istat=_scalar(provincia_cm_codice_istat),
                regione_codice_istat=_scalar(regione_codice_istat),
                tipologia_centro=_scalar(tipologia_centro),
                tipologia_ospiti=_scalar(tipologia_ospiti),
                operativita=_scalar(operativita),
                rilevazione_da=rilevazione_da,
                rilevazione_a=rilevazione_a,
                limit=limit,
                offset=offset,
            )
        return _with_sources(out)

    @mcp.tool(annotations=_READ_ONLY)
    async def centriditalia_get_centro(centro_id: str | int) -> dict[str, Any]:
        """Time series of one reception centre by its centro_id.

        Capacity / daily presences / daily cost over time, managing body and
        convention (stipula/scadenza/proroga) dates.

        Args:
            centro_id: The centre id as returned by centriditalia_search_centri.
        """
        async with CentriDItaliaClient() as c:
            out = await c.get_centro(centro_id)
        return _with_sources(out)

    @mcp.tool(annotations=_READ_ONLY)
    async def centriditalia_territorio_aggregate(
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
    ) -> dict[str, Any]:
        """Reception profile of a territory: total capacity/presences, avg daily cost.

        Uses the MOST RECENT observation per centre (so history is not summed).
        Ideal as a "reception on the territory" profile for the Territory report.
        Pass exactly one ISTAT code.

        Args:
            comune_codice_istat: ISTAT comune code (e.g. "072021").
            provincia_cm_codice_istat: ISTAT province code (e.g. "072").
            regione_codice_istat: ISTAT region code (e.g. "16").
        """
        async with CentriDItaliaClient() as c:
            out = await c.territorio_aggregate(
                comune_codice_istat=_scalar(comune_codice_istat),
                provincia_cm_codice_istat=_scalar(provincia_cm_codice_istat),
                regione_codice_istat=_scalar(regione_codice_istat),
            )
        return _with_sources(out)

    @mcp.tool(annotations=_READ_ONLY)
    async def centriditalia_search_sai(
        kind: Literal["progetti", "strutture"] = "progetti",
        comune_codice_istat: str | None = None,
        provincia_cm_codice_istat: str | None = None,
        regione_codice_istat: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search SAI (protection system) projects or structures by territory.

        Args:
            kind: "progetti" (SAI projects) or "strutture" (SAI structures).
            comune_codice_istat: ISTAT comune code.
            provincia_cm_codice_istat: ISTAT province code.
            regione_codice_istat: ISTAT region code.
            limit: Max results per page (default 20, hard-capped at 50).
            offset: Pagination offset.
        """
        limit = max(1, min(int(limit), _MAX_RESULTS))
        async with CentriDItaliaClient() as c:
            out = await c.search_sai(
                kind=kind,
                comune_codice_istat=_scalar(comune_codice_istat),
                provincia_cm_codice_istat=_scalar(provincia_cm_codice_istat),
                regione_codice_istat=_scalar(regione_codice_istat),
                limit=limit,
                offset=offset,
            )
        return _with_sources(out)

    @mcp.tool(annotations=_READ_ONLY)
    async def centriditalia_reference_values() -> dict[str, Any]:
        """Valid filter values found in the mirror (centre/guest type, state, procedure).

        Plus the data licence and the mirror's last refresh date.
        """
        async with CentriDItaliaClient() as c:
            return await c.reference_values()
