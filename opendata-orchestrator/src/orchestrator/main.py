"""Interactive CLI for the orchestrator (debug companion of the FastAPI service)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .config import Settings, get_settings, resolve_provider
from .factory import OrchestratorSession

console = Console()


def _active_model(settings: Settings) -> str:
    provider = resolve_provider(settings)
    if provider == "ollama":
        return settings.ollama_llm_model
    if provider == "azure_foundry":
        return settings.azure_ai_model_deployment_name or "(not set)"
    if provider == "claude":
        return settings.claude_model
    return "(unknown)"


async def _interactive(settings: Settings) -> int:
    async with OrchestratorSession(settings) as session:
        console.print(
            Panel.fit(
                f"[bold]opendata-orchestrator[/] ready\n"
                f"Provider:  [cyan]{settings.llm_provider}[/]  "
                f"Model: [cyan]{_active_model(settings)}[/]\n"
                f"CKAN MCP:  [cyan]{settings.ckan_mcp_url}[/]\n"
                f"ISTAT MCP: [cyan]{settings.istat_mcp_url}[/]\n"
                "Type your question, or /quit to exit.",
                title="opendata-orchestrator",
            )
        )
        while True:
            try:
                query = console.input("[bold green]>[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print()
                return 0
            if not query:
                continue
            if query in {"/quit", "/exit", ":q"}:
                return 0
            try:
                reply = await session.run(query)
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]Error:[/] {exc}")
                continue
            console.print(Markdown(reply))


async def _one_shot(settings: Settings, query: str) -> int:
    async with OrchestratorSession(settings) as session:
        reply = await session.run(query)
    console.print(Markdown(reply))
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="opendata-agent",
        description="Fan-out orchestrator over the CKAN + ISTAT MCP specialists",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Run a single question and exit (non-interactive).",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "ollama", "azure_foundry", "claude"],
        default=None,
    )
    parser.add_argument("--ckan-mcp-url", default=None)
    parser.add_argument("--istat-mcp-url", default=None)
    args = parser.parse_args()

    settings = get_settings()
    overrides: dict[str, object] = {}
    if args.provider:
        overrides["llm_provider"] = args.provider
    if args.ckan_mcp_url:
        overrides["ckan_mcp_url"] = args.ckan_mcp_url
    if args.istat_mcp_url:
        overrides["istat_mcp_url"] = args.istat_mcp_url
    if overrides:
        settings = settings.model_copy(update=overrides)

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    coro = _one_shot(settings, args.query) if args.query else _interactive(settings)
    sys.exit(asyncio.run(coro))


if __name__ == "__main__":
    cli()
