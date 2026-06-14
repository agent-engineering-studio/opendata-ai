"""Entry point for the Web MCP server.

Supports two transports, selected via TRANSPORT env var:
  - stdio               (default — for local MCP hosts like Claude Desktop)
  - streamable-http     (for Docker / production deployment)

The search backend is configured in opendata_core.web (WEB_SEARCH_PROVIDER,
SEARXNG_BASE_URL, WEB_SEARCH_MAX_RESULTS) — this server only wires transport.
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
log = logging.getLogger("web-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="web-mcp",
        instructions=(
            "Web search + fetch over external initiatives and territorial best "
            "practices. Use web_search to find precedents by other public bodies, "
            "then web_fetch to read and quote a promising hit."
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
        log.info("Starting Web MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting Web MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting Web MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
