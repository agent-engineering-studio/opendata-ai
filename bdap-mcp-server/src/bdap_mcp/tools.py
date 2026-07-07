"""BDAP/SIOPE tool implementation registered on the FastMCP server.

Thin wrapper over ``opendata_core.bdap.fetch_bilancio_comune``. Every result
carries ``source_url`` (deterministic citation hook for the orchestrator) and
a ``sources`` block with the licence.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opendata_core.bdap import fetch_bilancio_comune

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all BDAP tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def bdap_bilancio_comune(cod_comune: str, anno: int | None = None) -> dict[str, Any]:
        """Municipal budget (SIOPE cash movements) for an Italian comune, by titolo di bilancio.

        Returns cumulative revenue (entrate) and expense (spese) totals grouped by
        the main budget classification ("titolo"), for the most recent month
        available in the requested year — falls back to earlier years if the
        comune has no SIOPE rows for the requested one (dataset not yet published,
        or non-adherent entity).

        Args:
            cod_comune: ISTAT comune code, 6 digits (provincia+comune), e.g.
                "072021" for Gioia del Colle.
            anno: Budget year (defaults to the current year, retrocedes up to
                3 years if unavailable).
        """
        return await fetch_bilancio_comune(cod_comune, anno=anno)
