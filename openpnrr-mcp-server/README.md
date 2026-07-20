# openpnrr-mcp-server

MCP server that exposes **OpenPNRR** — the open data on Italy's *Piano Nazionale
di Ripresa e Resilienza* (NRRP) published by **[openpolis](https://www.openpolis.it/)**
at [openpnrr.it](https://openpnrr.it) — as structured tools for an LLM.

It follows the same shape as `opencoesione-mcp-server/`: a thin FastMCP wrapper
over an async client in the shared `opendata_core.openpnrr` package. OpenPNRR is
**not** a dataset catalogue but a structured REST API (missions → components →
measures → deadlines, territories, organisations, funded projects and payments),
so it is **not** part of the CKAN/ISTAT dataset fan-out.

> **Data licence: ODbL 1.0** — Open Data Commons Open Database License.
> Attribution is **required**: *openpolis, openpnrr.it*. Every tool result
> carries a `sources` block (resolvable `url` + extraction date + `licenza`) and
> a `source_url`, so downstream outputs can cite the source correctly.

## Source

- REST API root: `https://openpnrr.it/api/v1` — **no trailing slash** on
  endpoints (`/progetti` works; `/progetti/` returns a 404 HTML page). Public,
  no authentication on the list resources. DRF pagination
  (`{count, next, previous, results}`, `page` / `page_size`).
- OpenAPI (Swagger 2.0) schema: `https://openpnrr.it/api/v1/schema/`.
- `territori.istat_id` maps 1:1 onto the ISTAT codes used across the platform,
  e.g. `GET /territori?istat_id=072021` → Gioia del Colle (`territori/475`).
- `progetti` is large (~280k records) — always filter server-side.

## Tools

| Tool | Resource | Purpose |
|---|---|---|
| `openpnrr_resolve_territorio` | `GET /territori` | **Call first** — resolve a place name or ISTAT code to the OpenPNRR territory `id` used by the other filters. |
| `openpnrr_search_progetti` | `GET /progetti` | PNRR-funded projects, filterable by territory (`istat_id`/`territori`), measure/component/mission code, organisation, theme, validation. Slim records + pagination. |
| `openpnrr_get_progetto` | `GET /progetti/{id}` | Full detail: financing breakdown (PNRR/PNC/stato/regione/comune/UE/privato…), payments list with `pagamenti_totale`, CUP, timeline, iter phase. |
| `openpnrr_search_misure` | `GET /misure` | Measures (investments/reforms) by code, component, type, status, territory. |
| `openpnrr_search_scadenze` | `GET /scadenze` | Deadlines/milestones (ITA/UE) by measure, status, target year/quarter. |
| `openpnrr_reference_struttura` | `GET /missioni`, `/componenti`, `/temi`, `/priorita` | Static PNRR structure to resolve the codes used as filters above. |

Programmed funding (`finanziamento_*` on the project) and actual payments (the
project's payments list) mirror the programmed-vs-paid comparison already done
for OpenCoesione, but on a **distinct funding stream** (PNRR) — complementary,
not overlapping.

## Run

```bash
# stdio (local MCP hosts like Claude Desktop)
TRANSPORT=stdio openpnrr-mcp-server

# streamable-HTTP (Docker deployment; default in the image)
TRANSPORT=streamable-http PORT=8091 openpnrr-mcp-server   # → http://localhost:8091/mcp
```

From the repo root, a one-shot `tools/list` smoke test over stdio:

```bash
make mcp-stdio-openpnrr
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `OPENPNRR_BASE_URL` | `https://openpnrr.it/api/v1` | API root (no trailing slash). |
| `OPENPNRR_HTTP_TIMEOUT` | `60` | Per-request timeout (seconds). |
| `OPENPNRR_CACHE_TTL_SECONDS` | `3600` | In-process response cache TTL. |
| `TRANSPORT` / `HOST` / `PORT` / `MCP_PATH` | `stdio` / `0.0.0.0` / `8091` / `/mcp` | Transport & HTTP binding. |

## Development

```bash
cd openpnrr-mcp-server && pip install -e ".[dev]"
ruff check src && pytest -q
```

The Dockerfile's build context is the **repo root** (so the shared
`opendata_core` package is copied alongside this service's source) — CI builds
and the compose service set it that way; do not change it to the per-package
directory.
