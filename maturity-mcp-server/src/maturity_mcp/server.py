"""Entry point del Maturity MCP server.

Transport via TRANSPORT env var:
  - stdio               (default — host MCP locali tipo Claude Desktop)
  - streamable-http     (Docker / deployment)
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
log = logging.getLogger("maturity-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="maturity-mcp-server",
        instructions=(
            "Tools to assess the open-data maturity of a public entity (ODM 2025 + AgID) "
            "over any CKAN portal: harvest its datasets, score quality (5-star, FAIR, "
            "DCAT-AP_IT, ISO 25012, HVD), aggregate into 4 dimensions and an ODM level, "
            "and benchmark entities. Each tool accepts an optional base_url (default: the "
            "configured CKAN portal)."
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
        log.info("Starting Maturity MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting Maturity MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting Maturity MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
