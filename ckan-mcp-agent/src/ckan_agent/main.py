"""Interactive CLI for the CKAN agent."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .config import Settings, get_settings
from .factory import AgentSession

console = Console()


async def _interactive(settings: Settings) -> int:
    async with AgentSession(settings) as session:
        console.print(
            Panel.fit(
                f"[bold]CKAN Agent[/] ready\n"
                f"Provider: [cyan]{settings.llm_provider}[/]  "
                f"Model: [cyan]{settings.ollama_llm_model if settings.llm_provider == 'ollama' else settings.claude_model if settings.llm_provider == 'claude' else settings.azure_ai_model_deployment_name}[/]\n"
                f"MCP: [cyan]{settings.mcp_server_url}[/]\n"
                f"Default portal: [cyan]{settings.ckan_default_base_url}[/]\n"
                "Type your question, or /quit to exit.",
                title="ckan-mcp-agent",
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
    async with AgentSession(settings) as session:
        reply = await session.run(query)
    console.print(Markdown(reply))
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="ckan-agent",
        description="Microsoft Agent Framework CLI on top of the CKAN MCP server",
    )
    parser.add_argument("query", nargs="?", help="Run a single question and exit (non-interactive).")
    parser.add_argument("--provider", choices=["ollama", "azure_foundry", "claude"], default=None)
    parser.add_argument("--mcp-url", default=None)
    args = parser.parse_args()

    settings = get_settings()
    if args.provider:
        settings = settings.model_copy(update={"llm_provider": args.provider})
    if args.mcp_url:
        settings = settings.model_copy(update={"mcp_server_url": args.mcp_url})

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    coro = _one_shot(settings, args.query) if args.query else _interactive(settings)
    sys.exit(asyncio.run(coro))


if __name__ == "__main__":
    cli()
