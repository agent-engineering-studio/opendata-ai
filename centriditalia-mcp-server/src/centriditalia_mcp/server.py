"""Entry point for the Centri d'Italia MCP server.

Supports two transports, selected via the TRANSPORT env var:
  - stdio            (default — for local MCP hosts like Claude Desktop)
  - streamable-http  (for Docker deployment)

The data source is a bulk-CSV mirror built on first use (see
``opendata_core.centriditalia``); the first tool call downloads ~20 MB and
builds a local SQLite mirror, subsequent calls query it. Set
``CENTRIDITALIA_DB_PATH`` to a mounted volume to persist the mirror.
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from .tools import register_tools

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TRANSPORT = os.getenv("TRANSPORT", "stdio").lower()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8092"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("centriditalia-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="centriditalia-mcp-server",
        instructions=(
            "Tools to query Centri d'Italia (openpolis — Italy's migrant-reception "
            "system, https://centriditalia.it): CAS/CPA/hotspot centres and SAI "
            "projects/structures, with capacity, presences, daily cost per guest and "
            "managing body. Territorial filters accept ISTAT codes "
            "(comune_codice_istat='072021', provincia_cm_codice_istat='072', "
            "regione_codice_istat='16'). Typical flow: `centriditalia_territorio_"
            "aggregate` for a territory profile (total capacity/presences, avg daily "
            "cost, using the latest observation per centre); `centriditalia_search_"
            "centri` to list centres; `centriditalia_get_centro` for one centre's time "
            "series; `centriditalia_search_sai` for SAI projects/structures; "
            "`centriditalia_reference_values` for valid filter values. The data is "
            "AGGREGATED per centre (never individual). Licence: CC-BY 4.0 (openpolis) — "
            "every result carries a `source_url` to the original CSV and a refresh date."
        ),
        host=HOST,
        port=PORT,
        streamable_http_path=MCP_PATH,
    )
    register_tools(mcp)

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(request):  # noqa: ARG001
        from starlette.responses import JSONResponse

        return JSONResponse({"status": "ok"})

    return mcp


def main() -> None:
    mcp = build_server()

    if TRANSPORT == "stdio":
        log.info("Starting Centri d'Italia MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting Centri d'Italia MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting Centri d'Italia MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
