"""ISPRA IdroGEO tool implementations registered on the FastMCP server.

Thin wrapper over ``opendata_core.ispra.IspraClient``. Every result carries
``source_url`` (deterministic citation hook for the orchestrator) and a
``sources`` block with the CC BY-SA 3.0 IT licence.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from opendata_core.ispra import IspraClient
from opendata_core.ispra.mapping import LICENZA

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all ISPRA tools on the given FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY)
    async def ispra_risk_indicators(cod_comune: str) -> dict[str, Any]:
        """Landslide + flood hazard indicators for an Italian comune (IdroGEO).

        Returns, per hazard class, the municipal area share and the exposed
        population: landslide classes P4 (very high) … AA plus the P3+P4
        aggregate — the figure that matters for expansion constraints — and
        hydraulic (flood) classes P3/P2/P1. Use it to ground the environmental
        feasibility of territorial proposals.

        Args:
            cod_comune: ISTAT comune code, e.g. "072006" for Bari
                (zero-padded or not — both accepted).
        """
        async with IspraClient() as c:
            ind = await c.risk_indicators(cod_comune)
        out = ind.model_dump()
        out["sources"] = [
            {
                "url": ind.source_url,
                "estratto_il": date.today().isoformat(),
                "licenza": LICENZA,
            }
        ]
        return out
