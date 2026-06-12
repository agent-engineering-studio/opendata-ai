# ispra-mcp-server

MCP server exposing **ISPRA IdroGEO** (Italian landslide and flood hazard
platform, <https://idrogeo.isprambiente.it>) for LLM agents. Twin of the other
MCP servers in this repo: thin FastMCP wrapper over the shared async client in
`opendata_core/ispra/`.

## Tools

| tool | purpose |
|---|---|
| `ispra_risk_indicators` | per-comune hazard indicators: landslide classes P4…AA (+ P3+P4 aggregate) and hydraulic P3/P2/P1, with municipal-area shares and exposed population — the environmental-constraint evidence for territorial analyses |

Read-only/idempotent; every result includes `source_url` and a `sources` block
(CC BY-SA 3.0 IT).

## Run

```bash
pip install -e ".[dev]"          # plus opendata_core installed alongside
ispra-mcp-server                 # stdio (default)
TRANSPORT=streamable-http PORT=8083 ispra-mcp-server
```

Env vars: `TRANSPORT`, `HOST`, `PORT`, `MCP_PATH`, `LOG_LEVEL`, plus the
client's `ISPRA_IDROGEO_BASE_URL`, `ISPRA_HTTP_TIMEOUT`, `ISPRA_CACHE_TTL_SECONDS`.

## API Notes (discovery 2026-06-12, verified live)

- Endpoint: `GET https://idrogeo.isprambiente.it/api/pir/comuni/{uid}` — `uid`
  is the ISTAT comune code, accepted both zero-padded ("072006") and as an
  integer (72006). Single flat JSON with 134 keys.
- Landslide (IFFI/PAI): area km² + % per class (`ar_fr_p4`…`ar_fr_aa`,
  `ar_frp4_p`…, aggregate `ar_fr_p3p4`/`ar_frp3p4p`) and exposed population /
  families / buildings / firms / cultural heritage.
- Hydraulic (D.Lgs. 49/2010): `ar_id_p3/p2/p1` + `arid*_p`, `pop_idr_*`.
- Context: `nome`, `ar_kmq`, `pop_res021`, `extent` (bbox). Data is stable →
  client caches 24h.
- **Divergenza dalla spec 07**: il consumo di suolo ISPRA NON espone API REST
  (solo tabelle comunali XLSX annuali e servizi cartografici) → non
  implementato qui; parte dei dataset è raggiungibile via CKAN (dati.gov.it).

## Licence of the data

**CC BY-SA 3.0 IT** — cite ISPRA in downstream outputs (the `sources` block
carries the attribution).
