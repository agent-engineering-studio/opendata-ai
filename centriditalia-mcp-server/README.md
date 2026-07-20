# centriditalia-mcp-server

MCP server that exposes **Centri d'Italia** — the open data on Italy's
migrant-reception system published by **[openpolis](https://www.openpolis.it/)**
at [centriditalia.it](https://centriditalia.it) — as structured tools for an LLM:
CAS/CPA/hotspot centres and SAI projects/structures, with capacity, presences,
daily cost per guest and managing body.

> **Data licence: CC-BY 4.0.** Attribution is **required**: *openpolis / Centri
> d'Italia*. Every tool result carries a `source_url` to the original CSV, the
> `licenza` string and the mirror's `refreshed_at` date.
>
> The data is **aggregated per centre** — never individual — so it is safe to
> surface in a civic-analysis context (same caution as the Welfare lens).

## Source — bulk CSV, not a REST API

Unlike the API-based connectors, Centri d'Italia publishes **bulk CSV files on
S3** (listed at [centriditalia.it/pages/open-data](https://centriditalia.it/pages/open-data)).
They are too large (~11 MB + ~8.5 MB) to fetch on every tool call, so this
server builds a **local read-only SQLite mirror** on first use and queries it;
the mirror is rebuilt when the dataset version changes or the refresh TTL
expires (files are versioned per year, e.g. `_v2026`).

| Dataset | File | Loaded into |
|---|---|---|
| Reception centres (CAS/CPA/hotspot) — historical series, one row per observation | `centri_cas_cpa_hotspot_v2026.csv` | `centri` |
| SAI projects | `sai_progetti_v2026.csv` | `sai_progetti` |
| SAI structures | `sai_struttura_v2026.csv` | `sai_strutture` |

Column meanings come from the official data dictionary
`metadati_centri_v2026.xlsx` (do not invent them). The
`bandi_ANAC_accoglienza_v2026.csv` file listed on the page is **excluded**: it
currently returns `AccessDenied` (HTTP 403) on S3 (verified).

`comune_codice_istat` / `provincia_cm_codice_istat` / `regione_codice_istat` map
1:1 onto the ISTAT codes used across the platform (same pattern as OpenPNRR /
OpenCoesione).

## Tools

| Tool | Purpose |
|---|---|
| `centriditalia_territorio_aggregate` | Territory profile: total capacity/presences and average daily cost, using the **latest observation per centre** (history not summed). |
| `centriditalia_search_centri` | Reception centres filterable by ISTAT territory, `tipologia_centro`, `tipologia_ospiti`, `operativita`, `rilevazione_data` range. |
| `centriditalia_get_centro` | Time series of one centre (`centro_id`): capacity/presences/cost over time, managing body, convention dates. |
| `centriditalia_search_sai` | SAI projects or structures (`kind`) by territory. |
| `centriditalia_reference_values` | Valid values of `tipologia_centro`/`tipologia_ospiti`/`operativita`/`procedura_affidamento` + licence + refresh date. |

## Run

```bash
# stdio (local MCP hosts like Claude Desktop)
TRANSPORT=stdio centriditalia-mcp-server

# streamable-HTTP (Docker deployment; default in the image)
TRANSPORT=streamable-http PORT=8092 centriditalia-mcp-server   # → http://localhost:8092/mcp
```

From the repo root, a one-shot `tools/list` smoke test over stdio:

```bash
make mcp-stdio-centriditalia
```

The **first** tool call downloads the CSVs and builds the mirror (~20 MB, a few
seconds); later calls are instant. Mount a volume at `CENTRIDITALIA_DB_PATH` to
persist the mirror across restarts.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `CENTRIDITALIA_BASE_URL` | `https://migrantidb.s3.eu-central-1.amazonaws.com/opendata` | S3 base of the CSV files. |
| `CENTRIDITALIA_DATASET_VERSION` | `v2026` | Version tag in the file names. |
| `CENTRIDITALIA_DB_PATH` | `<tmp>/centriditalia_mirror.sqlite` (`/data/…` in the image) | Local mirror path. |
| `CENTRIDITALIA_REFRESH_TTL_SECONDS` | `604800` (7 days) | Rebuild the mirror when older than this or on a version change. |
| `CENTRIDITALIA_HTTP_TIMEOUT` | `120` | Download timeout (seconds). |
| `TRANSPORT` / `HOST` / `PORT` / `MCP_PATH` | `stdio` / `0.0.0.0` / `8092` / `/mcp` | Transport & HTTP binding. |

## Development

```bash
cd centriditalia-mcp-server && pip install -e ".[dev]"
ruff check src && pytest -q
```

The Dockerfile's build context is the **repo root** (so the shared
`opendata_core` package is copied alongside this service's source) — CI builds
and the compose service set it that way; do not change it to the per-package
directory.
