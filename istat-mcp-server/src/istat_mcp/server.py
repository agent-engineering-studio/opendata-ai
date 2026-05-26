"""Entry point for the ISTAT MCP server.

Supports two transports, selected via the TRANSPORT env var:
  - stdio            (default — for local MCP hosts like Claude Desktop)
  - streamable-http  (for Docker / Azure deployment)
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
log = logging.getLogger("istat-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="istat-mcp-server",
        instructions=(
            "Tools to query ISTAT (Italian National Institute of Statistics) via the "
            "SDMX 2.1 REST API. Start from `istat_list_dataflows` to discover datasets, "
            "inspect a dataflow with `istat_get_dataflow` / `istat_get_structure` / "
            "`istat_get_constraints`, resolve codes with `istat_get_codelist`, and "
            "finally fetch observations as CSV with `istat_get_data`. All tools accept "
            "an optional `base_url` to point at alternative SDMX 2.1 endpoints."
        ),
        host=HOST,
        port=PORT,
        streamable_http_path=MCP_PATH,
    )
    register_tools(mcp)
    return mcp


def main() -> None:
    mcp = build_server()

    if TRANSPORT == "stdio":
        log.info("Starting ISTAT MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting ISTAT MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting ISTAT MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
