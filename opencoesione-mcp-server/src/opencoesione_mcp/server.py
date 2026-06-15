"""Entry point for the OpenCoesione MCP server.

Supports two transports, selected via the TRANSPORT env var:
  - stdio            (default — for local MCP hosts like Claude Desktop)
  - streamable-http  (for Docker deployment)
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
PORT = int(os.getenv("PORT", "8080"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("opencoesione-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="opencoesione-mcp-server",
        instructions=(
            "Tools to query OpenCoesione (Italian cohesion-policy funded projects, "
            "https://opencoesione.gov.it). Typical flow: start from "
            "`opencoesione_search_projects` scoped to an ISTAT comune code (e.g. "
            "cod_comune='072006') to list funded projects; drill into one with "
            "`opencoesione_get_project` (by CLP); get territory-wide totals with "
            "`opencoesione_territorial_aggregates`; assess the territory's historical "
            "delivery capacity (spend ratio, completed/total projects) with "
            "`opencoesione_funding_capacity`; find implementing bodies with "
            "`opencoesione_search_soggetti`. Territorial filters accept ISTAT codes "
            "(resolved internally to OpenCoesione slugs). Data licence: CC BY-SA 3.0 — "
            "every result carries a `sources` block with resolvable URLs to cite."
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
        log.info("Starting OpenCoesione MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting OpenCoesione MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting OpenCoesione MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
