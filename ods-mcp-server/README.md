# ods-mcp-server

FastMCP server exposing the **OpenDataSoft Explore API v2.1** as MCP tools, so an
LLM can query any OpenDataSoft open-data portal (many Italian and European
regional/city portals run on ODS). One image works against any portal: every tool
takes an optional `base_url`, falling back to `ODS_DEFAULT_BASE_URL`.

Same shape as `ckan-mcp-server/` — the async client lives in
`opendata_core/opendatasoft/`, this package is the thin FastMCP wrapper.

## Tools

| Tool | Purpose |
|---|---|
| `ods_search_datasets` | Search the dataset catalog (free-text `q` or raw ODSQL `where`) → slim dataset list |
| `ods_dataset_show` | Full metadata + field schema for one dataset |
| `ods_dataset_records` | Query rows of a dataset via ODSQL (`where`/`select`/`order_by`) |

Filters use **ODSQL** (the OpenDataSoft query language). A bare string does a
full-text search; structured clauses look like `publisher:"Comune di X"` or
`anno=2023 AND popolazione>1000`.

## Run

```bash
# stdio (Claude Desktop / local MCP host)
pip install -e ".[dev]"
ods-mcp-server

# streamable-HTTP (Docker / deployment)
TRANSPORT=streamable-http PORT=8080 ods-mcp-server
```

## Environment

| Var | Default | Meaning |
|---|---|---|
| `ODS_DEFAULT_BASE_URL` | `https://public.opendatasoft.com` | Portal used when a tool omits `base_url` |
| `ODS_HTTP_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` | HTTP transport binding |

## Test

```bash
pip install -e ".[dev]"
pytest -q
```
