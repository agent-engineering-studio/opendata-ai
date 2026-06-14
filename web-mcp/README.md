# web-mcp

MCP server exposing **web search + fetch** to the opendata-ai fan-out, powering the
**marketing-territoriale** source (Pezzo 10 — `docs/specs/10-marketing-territorio.md`).

Default backend is a **self-hosted [SearXNG](https://docs.searxng.org/)** meta-search
instance (free, no third-party API key). The provider is abstracted via
`WEB_SEARCH_PROVIDER` in `opendata_core.web` so a hosted API (Tavily / Brave) can be
slotted in later without touching this server or the backend.

## Tools

| Tool | Purpose |
|---|---|
| `web_search(query, max_results=8)` | Find external initiatives / best practices by other public bodies. Returns slim `{title, url, snippet, date, engine}` hits. Bias the query toward institutional sources (`site:gov.it`, regional agencies, local press). |
| `web_fetch(url)` | Fetch a hit's body (truncated) so the agent can quote it. Returns the final URL after redirects. |

## Configuration

| Env | Default | Notes |
|---|---|---|
| `TRANSPORT` | `stdio` | `streamable-http` in Docker |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` | streamable-http wiring |
| `WEB_SEARCH_PROVIDER` | `searxng` | only `searxng` implemented (Tavily/Brave hooks pending) |
| `SEARXNG_BASE_URL` | `http://localhost:8080` | `http://searxng:8080` inside compose |
| `WEB_SEARCH_MAX_RESULTS` | `8` | hard-capped at 15 |

> SearXNG must have the `json` format enabled (`search.formats: [html, json]` in
> its `settings.yml`) — the default config serves HTML only. The infra repo ships
> a ready `searxng/settings.yml`.

## Run

```bash
cd web-mcp && pip install -e ".[dev]"
TRANSPORT=stdio SEARXNG_BASE_URL=http://localhost:8080 web-mcp-server   # local
# one-shot tools/list over stdio: make mcp-stdio-web (from repo root)
```

Build context is the **repo root** (copies `opendata_core/` alongside) — see the
Dockerfile and `docker-publish.yml`.
