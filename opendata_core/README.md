# opendata-core

Shared async building blocks consumed by both the MCP servers and the unified
`opendata-backend` FastAPI service. Single source of truth for:

- `opendata_core.ckan.client.CkanClient` — async wrapper over the CKAN
  Action API (`/api/3/action/*`). Per-call `base_url` so one client can serve
  any portal (`dati.gov.it`, `data.gov.uk`, `data.gov`, ...).
- `opendata_core.sdmx.client.SdmxClient` — async wrapper over the SDMX 2.1
  REST protocol (ISTAT, Eurostat, OECD). Per-instance `base_url`, content
  negotiation (SDMX-JSON for metadata, SDMX-CSV for data), in-memory TTL
  cache of metadata lookups.
- `opendata_core.osm` — pure-Python GeoJSON validation + Leaflet+OSM HTML
  renderer + OpenStreetMap HTTP clients (Nominatim / Overpass / OSRM).

This package contains no FastMCP, no FastAPI and no LLM code. It is
deliberately framework-agnostic so it can be reused by:

- the MCP servers (`ckan-mcp-server`, `istat-mcp-server`, `osm-mcp`) — they
  wrap the same async functions as MCP tools;
- the future `opendata-backend` — it will call the same async functions
  directly from REST handlers.

## Install (editable, for local development)

```bash
cd opendata_core
pip install -e ".[dev]"
```

Each consumer declares `opendata-core` as a regular dependency in its
`pyproject.toml`; in Docker builds the package is installed from a path
copied into the build context.
