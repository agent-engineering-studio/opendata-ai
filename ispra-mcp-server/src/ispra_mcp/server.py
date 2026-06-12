"""Entry point for the ISPRA IdroGEO MCP server.

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
log = logging.getLogger("ispra-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="ispra-mcp-server",
        instructions=(
            "Tools to query ISPRA IdroGEO (Italian landslide and flood hazard "
            "platform, idrogeo.isprambiente.it). Call `ispra_risk_indicators` with "
            "an ISTAT comune code (e.g. cod_comune='072006') to get the share of "
            "municipal area in each hazard class (landslide P4..AA + the P3+P4 "
            "aggregate; hydraulic P3/P2/P1) and the exposed population/buildings. "
            "These are PLANNING CONSTRAINTS for territorial analyses. Data licence "
            "CC BY-SA 3.0 IT — every result carries a `sources` block to cite. "
            "Soil-consumption data has NO usable API (yearly XLSX tables only) and "
            "is not exposed here."
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
        log.info("Starting ISPRA MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting ISPRA MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting ISPRA MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
