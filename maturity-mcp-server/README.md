# maturity-mcp-server

MCP server (FastMCP) per la **maturità open-data** di un ente (ODM 2025 + AgID)
su qualsiasi portale CKAN. La logica deterministica vive in
`opendata_core.maturity`; qui è esposta come tool e arricchita da un giudizio
semantico opzionale via Claude Haiku.

## Tool
- `maturity_harvest_entity(entity, base_url?, max_datasets?)` — dataset dell'ente via CKAN.
- `maturity_assess_quality(dataset)` — qualità di un singolo dataset (5-star/FAIR/DCAT-AP_IT/ISO25012/HVD).
- `maturity_score_overall(entity, …)` — assessment completo: 4 dimensioni, livello ODM, raccomandazioni.
- `maturity_score_dimension(entity, dimension, …)` — singola dimensione (policy|portal|quality|impact).
- `maturity_compare_entities(entities[], …)` — benchmark tra enti.

## Transport
`TRANSPORT=stdio` (default, Claude Desktop) oppure `streamable-http` (Docker, porta 8080, path `/mcp`).

## Semantico (Haiku)
Usato SOLO per la comprensibilità delle descrizioni. Senza `ANTHROPIC_API_KEY` viene
saltato (scoring deterministico invariato). Modello: `CLAUDE_CLASSIFY_MODEL`.
