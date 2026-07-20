# opendata-mcp-server

**Product** MCP server for [`opendata-ai`](../README.md). It exposes the four
product modes — **Esplora · Territorio · Maturità · Qualità** (+ dataset
classification) — as MCP **tools** for an external client or agent harness
(**OpenClaw**, Claude Desktop, Cursor, …), so a third-party agent can *search
datasets*, *analyse a comune*, *assess an entity's maturity* and *check a file's
quality* without reimplementing anything.

> **Where this fits (R13).** The 8 source MCP servers (`ckan-mcp`, `istat-mcp`,
> …) expose *data sources* to the backend's own LLM. **A2A** exposes the *whole
> agent* to another agent. This server is the missing middle: it exposes
> opendata-ai's *product capabilities* as MCP tools — complementary to, not a
> replacement for, the A2A surface.

## How it works — a thin proxy (issue #131, Option A)

Each tool forwards to the `opendata-backend` REST API, so it **reuses** the
backend's orchestration, LLM provider resolution, Redis cache, fail-safe and
API-key auth/billing — no product logic is duplicated here.

| MCP tool | Backend endpoint | Mode |
|---|---|---|
| `esplora_cerca_dataset` | `POST /datasets/search` | Esplora |
| `territorio_analizza_comune` | `POST /territory/report` | Territorio |
| `maturita_scorecard_ente` | `POST /maturity/assess` | Maturità |
| `qualita_diagnosi_dataset` | `POST /quality/profile` | Qualità |
| `classifica_dataset` | `POST /datasets/classify` | (classify) |

If the backend is unreachable or times out, tools return a **clean MCP error**
(`BackendError`), never a crash.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `OPENDATA_API_BASE_URL` | `http://localhost:8000` (`http://opendata-backend:8000` in the image) | Backend base URL. |
| `OPENDATA_API_KEY` | *(unset)* | API key forwarded as `Authorization: Bearer …`. Omit when the backend runs in dev-bypass (`AUTH_ENABLED=false`). |
| `OPENDATA_API_TIMEOUT` | `300` | Per-request timeout (seconds) — report/assessment call LLMs. |
| `TRANSPORT` / `HOST` / `PORT` / `MCP_PATH` | `stdio` / `0.0.0.0` / `8093` / `/mcp` | Transport & HTTP binding. |

## Run

```bash
# stdio (local MCP hosts)
OPENDATA_API_BASE_URL=http://localhost:8000 OPENDATA_API_KEY=od_… \
  TRANSPORT=stdio opendata-mcp-server

# streamable-HTTP (Docker; default in the image)
TRANSPORT=streamable-http PORT=8093 opendata-mcp-server   # → http://localhost:8093/mcp
```

One-shot `tools/list` smoke test over stdio, from the repo root:

```bash
make mcp-stdio-opendata
```

## Use from OpenClaw / Claude Desktop

Add to the MCP client config (e.g. Claude Desktop `claude_desktop_config.json`,
or the equivalent OpenClaw MCP server list):

```jsonc
{
  "mcpServers": {
    "opendata-ai": {
      "command": "opendata-mcp-server",
      "env": {
        "TRANSPORT": "stdio",
        "OPENDATA_API_BASE_URL": "https://your-opendata-backend.example",
        "OPENDATA_API_KEY": "od_your_key_here"
      }
    }
  }
}
```

For a streamable-HTTP deployment, point the client at `http://<host>:8093/mcp`
instead of spawning the command.

## Development

```bash
cd opendata-mcp-server && pip install -e ".[dev]"
ruff check src && pytest -q
```

The Dockerfile's build context is the **repo root** for consistency with the
other MCP images (R1); this server is a pure proxy and does not bundle
`opendata_core`.
