"""Entry point for the OpenPNRR MCP server.

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
PORT = int(os.getenv("PORT", "8091"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("openpnrr-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="openpnrr-mcp-server",
        instructions=(
            "Tools to query OpenPNRR (openpolis — Italian NRRP / PNRR open data, "
            "https://openpnrr.it). Typical flow: call `openpnrr_resolve_territorio` "
            "FIRST to turn a place name or ISTAT code (e.g. istat_id='072021') into an "
            "OpenPNRR territory id, then `openpnrr_search_progetti` (scoped by that id "
            "or directly by istat_id) to list PNRR-funded projects; drill into one with "
            "`openpnrr_get_progetto` (by numeric id) for the full financial breakdown "
            "and payments; browse measures with `openpnrr_search_misure`, deadlines/"
            "milestones with `openpnrr_search_scadenze`, and the mission/component/theme "
            "structure with `openpnrr_reference_struttura` (to resolve the codes used as "
            "filters). The `progetti` dataset is huge (~280k) — always filter server-side. "
            "Data licence: ODbL 1.0 (attribution to openpolis) — every result carries a "
            "`sources` block with resolvable URLs to cite."
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
        log.info("Starting OpenPNRR MCP server over stdio")
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting OpenPNRR MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting OpenPNRR MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
