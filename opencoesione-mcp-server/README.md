# opencoesione-mcp-server

MCP server exposing **OpenCoesione** (Italian cohesion-policy funded projects,
<https://opencoesione.gov.it>) as tools for LLM agents. Twin of
`istat-mcp-server`: thin FastMCP wrapper over the shared async client in
`opendata_core/opencoesione/`.

## Tools

| tool | purpose |
|---|---|
| `opencoesione_search_projects` | funded projects filterable by ISTAT comune/provincia/regione, theme, cycle, nature, state; paginated (`limit`/`offset`, `total`/`has_more`/`next_offset`) |
| `opencoesione_get_project` | full detail by CLP (codice locale progetto) |
| `opencoesione_territorial_aggregates` | programmed/paid resources per territory (+ per state/theme/year breakdowns, population) |
| `opencoesione_search_soggetti` | involved bodies by territory/role/theme/nature |
| `opencoesione_funding_capacity` | **workflow tool**: spend ratio (payments/public cost) + completed/total projects → historical delivery capacity |
| `opencoesione_reference_values` | valid filter slugs (themes, natures, states, cycles) discovered on the live API |

All tools are read-only/idempotent; every result includes `source_url` (the
resolvable API URL of that exact response) and a `sources` block with the
extraction date and licence.

## Run

```bash
pip install -e ".[dev]"          # plus opendata_core installed alongside
opencoesione-mcp-server          # stdio (default)
TRANSPORT=streamable-http PORT=8080 opencoesione-mcp-server   # HTTP at /mcp
```

Env vars: `TRANSPORT` (stdio | streamable-http | sse), `HOST`, `PORT`,
`MCP_PATH`, `LOG_LEVEL`, plus the client's `OPENCOESIONE_BASE_URL`,
`OPENCOESIONE_HTTP_TIMEOUT`, `OPENCOESIONE_CACHE_TTL_SECONDS`.

## API Notes (discovery 2026-06-12, verified live)

Everything below was probed against the real API — see
`opendata_core/opencoesione/mapping.py` for the full annotated list.

- API root `/it/api/` is plain JSON listing resources: `progetti`, `soggetti`,
  `aggregati`, `temi`, `nature`, `territori`, `programmi` + `data_aggiornamento`.
- **Unknown query params are silently ignored** (e.g. `cod_comune=…` on
  `/progetti` returns the full unfiltered count). The client whitelists every
  filter it sends; invalid slugs raise client-side with the valid values.
- Territorial filtering uses **slugs** (`territorio=bari-comune`), never ISTAT
  codes. `/territori` resolves codes → slugs (`cod_com=72006`, `tipo=C`); codes
  are stored as integers (ISTAT `"072006"` → `72006`).
- `/progetti` filters: `territorio`, `tema`, `natura`, `stato`,
  `ciclo_programmazione` (`2000_2006|2007_2013|2014_2020|2021_2027` — four
  cycles, one more than the spec assumed), `fonte`, `focus`.
- `/soggetti` filters: `territorio`, `tema`, `natura`, `ruolo`. **No free-text
  name search** (`denominazione` is ignored on this resource).
- Pagination: `page`/`page_size`, `page_size` capped server-side at **500**.
- `/aggregati/territori/{slug}.json` includes context (population!), totals and
  per-state/theme/nature/year breakdowns, and **accepts
  `ciclo_programmazione`** — so `funding_capacity` costs ONE request instead of
  paginating projects.
- Detail at `/progetti/{clp-lowercase}.json`. Amounts are Italian-formatted
  strings (`"421465927,95"`), dates `YYYYMMDD`, percentages `"100%"`.
- **Throttling**: HTTP 429 after a couple of rapid requests, body
  `{"detail": "… Expected available in N second(s)."}` — the client honours the
  suggested wait (capped at 15s, max 4 attempts) and caches responses (TTL 1h).

## Licence of the data

API data: **CC BY-SA 3.0** (bulk datasets: CC BY 4.0). Every tool output cites
the source URL and licence — keep the attribution in downstream outputs.
