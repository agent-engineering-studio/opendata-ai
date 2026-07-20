"""Entry point for the opendata-ai **product** MCP server (issue #131).

Exposes the four product modes — Esplora / Territorio / Maturità / Qualità
(+ classify) — as MCP tools for an external client/harness (OpenClaw, Claude
Desktop, Cursor). It is a thin proxy over the backend REST API (see
``client.py``): configure the target with ``OPENDATA_API_BASE_URL`` and, if the
backend enforces auth, ``OPENDATA_API_KEY`` (forwarded as a Bearer token).

Transports (TRANSPORT env): stdio (default) or streamable-http.
"""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

from .client import DEFAULT_BASE_URL
from .tools import register_tools

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TRANSPORT = os.getenv("TRANSPORT", "stdio").lower()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8093"))
MCP_PATH = os.getenv("MCP_PATH", "/mcp")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("opendata-mcp")


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="opendata-mcp-server",
        instructions=(
            "Product tools for opendata-ai — Italian + European open data. Four modes: "
            "`esplora_cerca_dataset` (conversational multi-source dataset search), "
            "`territorio_analizza_comune` (evidence-based report for a comune by ISTAT "
            "code), `maturita_scorecard_ente` (ODM 2025 open-data maturity scorecard of "
            "an entity), `qualita_diagnosi_dataset` (deterministic quality diagnosis of a "
            "CSV/GeoJSON), plus `classifica_dataset` (taxonomy scoring). These proxy the "
            "opendata-ai backend, which owns orchestration, LLM synthesis, cache and "
            f"fail-safe (target: {DEFAULT_BASE_URL}). Territorial inputs use ISTAT codes."
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
        log.info("Starting opendata-ai product MCP server over stdio (backend=%s)", DEFAULT_BASE_URL)
        mcp.run(transport="stdio")
    elif TRANSPORT in ("http", "streamable-http", "streamable_http"):
        log.info("Starting opendata-ai product MCP server on http://%s:%s%s", HOST, PORT, MCP_PATH)
        mcp.run(transport="streamable-http")
    elif TRANSPORT == "sse":
        log.info("Starting opendata-ai product MCP server (SSE) on http://%s:%s", HOST, PORT)
        mcp.run(transport="sse")
    else:
        raise SystemExit(f"Unknown TRANSPORT={TRANSPORT!r}. Use stdio|streamable-http|sse.")


if __name__ == "__main__":
    main()
