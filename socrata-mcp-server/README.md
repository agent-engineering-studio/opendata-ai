# socrata-mcp-server

FastMCP server exposing **Socrata's open-data APIs** (Discovery, Views, SODA) as
MCP tools, so an LLM can query any Socrata-hosted portal (many US city/state/federal
open-data portals, plus a handful of Italian/European ones, run on Socrata). One
image works against any portal: every tool takes an optional `base_url`, falling
back to `SOCRATA_DEFAULT_BASE_URL`.

Same shape as `ckan-mcp-server/` and `ods-mcp-server/` — the async client lives in
`opendata_core/socrata/`, this package is the thin FastMCP wrapper.

## Tools

| Tool | Purpose |
|---|---|
| `socrata_search_datasets` | Search the dataset catalog (Discovery API, `/api/catalog/v1`) → slim dataset list |
| `socrata_dataset_show` | Full metadata + column schema for one dataset (Views API, `/api/views/{id}.json`) |
| `socrata_dataset_records` | Query rows of a dataset via SoQL (SODA API, `/resource/{id}.json`) |

`socrata_search_datasets` scopes results to the target portal's own domain by
default (derived from `base_url`); pass `domains` explicitly to search other/
additional Socrata domains too.

Row filters use **SoQL** (the Socrata Query Language): `where`/`select`/`order_by`/
`q` map to `$where`/`$select`/`$order`/`$q`. A `where` clause looks like
`altezza>10 AND specie="Quercia"`.

## Run

```bash
# stdio (Claude Desktop / local MCP host)
pip install -e ".[dev]"
socrata-mcp-server

# streamable-HTTP (Docker / deployment)
TRANSPORT=streamable-http PORT=8080 socrata-mcp-server
```

## Environment

| Var | Default | Meaning |
|---|---|---|
| `SOCRATA_DEFAULT_BASE_URL` | `https://opendata.socrata.com` | Portal used when a tool omits `base_url` |
| `SOCRATA_HTTP_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `TRANSPORT` | `stdio` | `stdio` \| `streamable-http` \| `sse` |
| `HOST` / `PORT` / `MCP_PATH` | `0.0.0.0` / `8080` / `/mcp` | HTTP transport binding |

## Test

```bash
pip install -e ".[dev]"
pytest -q
```
