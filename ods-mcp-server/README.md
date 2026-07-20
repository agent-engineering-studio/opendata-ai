# ods-mcp-server

> One MCP server, any OpenDataSoft open-data portal in the world.

`ods-mcp-server` is a [FastMCP](https://github.com/modelcontextprotocol/python-sdk)
wrapper that exposes the **[OpenDataSoft Explore API v2.1](https://help.opendatasoft.com/apis/ods-explore-v2/)**
as MCP tools, so any MCP client (Claude Desktop, Cursor, VS Code, an agent) can
search and read datasets on any OpenDataSoft portal. Many Italian and European
regional/city open-data portals run on OpenDataSoft.

The reusable part: **every tool takes an optional `base_url` per call**, so a
single running instance (or Docker image) queries `public.opendatasoft.com`,
`data.issy.com`, or any other ODS portal — no redeploy. When `base_url` is
omitted, `ODS_DEFAULT_BASE_URL` is used.

It ships as one component of the **opendata-ai** project, but runs perfectly
standalone: the async client lives in `opendata_core/opendatasoft/`, this package
is only the thin FastMCP wrapper. Read-only, no credentials required.

## What it does

OpenDataSoft is a hosted open-data platform. This server turns its Explore API
into typed, LLM-ready MCP tools: search a portal's catalog, read a dataset's full
metadata and field schema, and query the actual rows via **ODSQL** (the
OpenDataSoft query language). Dataset payloads are slimmed (essential fields) to
stay within an LLM's context budget.

## Tools

| Tool | Purpose | Key arguments |
|---|---|---|
| `ods_search_datasets` | Search the catalog (free-text `q` or raw ODSQL `where`) → slim dataset list | `q`, `where`, `limit`, `offset`, `base_url` |
| `ods_dataset_show` | Full metadata + field schema for one dataset | `dataset_id`, `base_url` |
| `ods_dataset_records` | Query rows of a dataset via ODSQL | `dataset_id`, `where`, `select`, `order_by`, `limit`, `offset`, `base_url` |

Filters use **ODSQL**: a bare string does a full-text search; structured clauses
look like `publisher:"Comune di X"` or `anno=2023 AND popolazione>1000`.

Every tool accepts the optional `base_url` (portal root URL, e.g.
`https://data.issy.com`) — that's what makes one instance work against any ODS
catalog.

## Quick start

### stdio (local MCP hosts like Claude Desktop)

```bash
pip install -e .
TRANSPORT=stdio ods-mcp-server
```

### Streamable HTTP (Docker / container)

```bash
docker build -f ods-mcp-server/Dockerfile -t ods-mcp-server .   # build context = repo root
docker run --rm -p 8089:8080 \
  -e TRANSPORT=streamable-http \
  -e ODS_DEFAULT_BASE_URL=https://public.opendatasoft.com \
  ods-mcp-server
```

MCP endpoint: `http://localhost:8089/mcp` (internal port `8080`). Healthcheck on
`GET /healthz`.

## Environment variables

| Var | Default | Meaning |
|---|---|---|
| `ODS_DEFAULT_BASE_URL` | `https://public.opendatasoft.com` | Portal used when a tool omits `base_url` |
| `ODS_HTTP_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` | HTTP transport binding |
| `LOG_LEVEL` | `INFO` | Python logging level |

## Use it with an MCP client

### Claude Desktop (stdio)

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ods": {
      "command": "ods-mcp-server",
      "env": { "ODS_DEFAULT_BASE_URL": "https://public.opendatasoft.com" }
    }
  }
}
```

For HTTP clients, start the server with `TRANSPORT=streamable-http` and point the
client at `http://localhost:8089/mcp`.

## Example workflow

1. **Search** a portal for a topic:

```json
{
  "tool": "ods_search_datasets",
  "arguments": { "q": "arbres", "limit": 3, "base_url": "https://data.issy.com" }
}
```

Response (slimmed for the LLM):

```json
{
  "total_count": 5,
  "results": [
    { "dataset_id": "les-arbres", "title": "Les arbres d'Issy", "records_count": 4213 }
  ]
}
```

2. **Inspect** the field schema with `ods_dataset_show` (`dataset_id="les-arbres"`).
3. **Query rows** with ODSQL:

```json
{
  "tool": "ods_dataset_records",
  "arguments": {
    "dataset_id": "les-arbres",
    "where": "hauteur > 10",
    "select": "espece, count(*) as tot",
    "base_url": "https://data.issy.com"
  }
}
```

## Limitations

- **Read-only.** Only the public Explore v2.1 read endpoints are exposed — no
  writes, no dataset management, no push API.
- **One portal per call.** Cross-portal federated search is not supported; pass a
  single `base_url` (or rely on the default) per tool call.
- **ODSQL, not SQL.** `ods_dataset_records` uses ODSQL clauses, not full SQL joins.
- **Result caps for LLM context.** `limit` is capped server-side and dataset
  metadata is slimmed; for full exports use the portal's own export endpoints.
- **Public data only.** Portals requiring an API key for private datasets are out
  of scope; this server targets public catalogs.

## License & notes

Server code is **MIT**. Returned datasets remain subject to the **source
portal's licence** — always check the ODS catalog's terms before reusing data.
Part of the [opendata-ai](../README.md) project (see the root README for the full
architecture).

## Development

```bash
pip install -e ".[dev]"
ruff check src && pytest -q
```
