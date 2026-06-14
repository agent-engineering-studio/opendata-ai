"""Web tool implementations registered on the FastMCP server.

Two tools power the marketing-territoriale fan-out source (Pezzo 10):
  - web_search: find external initiatives / best practices (other comuni, press,
    regional programmes) — returns slim {title, url, snippet, date} hits.
  - web_fetch:  read the body of a promising hit so the agent can quote it.

The backend's WEB_INSTRUCTIONS tell the agent to bias queries toward institutional
sources (site:*.gov.it, regional tourism agencies, local press); that bias lives in
the query, not here, so the same tools work for any provider.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from opendata_core.web import WebClient, WebSearchError


def register_tools(mcp: FastMCP) -> None:
    """Register the web tools on the given FastMCP instance."""

    @mcp.tool()
    async def web_search(query: str, max_results: int = 8) -> dict[str, Any]:
        """Search the web for initiatives, news and best practices by other public bodies.

        Use this to find concrete precedents to take inspiration from (e.g. a similar
        comune that launched a tourism / mobility / safety initiative). Prefer
        institutional sources by adding operators to the query, e.g.
        "comune borgo turismo site:gov.it" or "Regione Puglia mobilità ciclabile".

        Args:
            query: Full-text query; may include operators like site:, intitle:, "...".
            max_results: Max hits to return (default 8, hard-capped at 15).

        Returns a dict ``{query, results: [{title, url, snippet, date, engine}]}``.
        """
        try:
            async with WebClient() as c:
                results = await c.search(query, max_results=max_results)
        except WebSearchError as exc:
            return {"query": query, "results": [], "error": str(exc)}
        return {"query": query, "results": results}

    @mcp.tool()
    async def web_fetch(url: str) -> dict[str, Any]:
        """Fetch a URL and return its text content (truncated) so you can quote it.

        Use after web_search to read a promising hit before citing it. The returned
        URL is the final URL after redirects — cite that one.

        Args:
            url: The URL to fetch (typically a result.url from web_search).

        Returns ``{url, content, truncated, size_bytes, content_type}`` or
        ``{url, content: null, error}`` on failure.
        """
        try:
            async with WebClient() as c:
                return await c.fetch(url)
        except WebSearchError as exc:
            return {"url": url, "content": None, "error": str(exc)}
