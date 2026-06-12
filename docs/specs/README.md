# Verticale PA "Studio del territorio" — indice spec

Pagina UI: **`/territorio`** (label nav "Territorio", titolo "Studio del
territorio"). Due modalità sull'endpoint `POST /programma`: `scheda` (SWOT +
proposte evidence-based, Pezzo 4) e `idee` (brainstorming a quattro generatori,
Pezzo 8). Ogni spec ha il prompt operativo gemello in
`docs/prompts/claude-code/P0X-*.md`.

## Ordine di esecuzione consigliato

| # | Spec | Cosa sblocca | Dipende da |
|---|---|---|---|
| 1 | `01-opencoesione-mcp.md` | fonte OpenCoesione (client + MCP) | — |
| 2 | `02-opencoesione-orchestrator.md` | OpenCoesione nel fan-out | 1 |
| 3 | `03-opencoesione-bulk-ingest.md` | DB locale → aggregati pesanti, base dei generatori comparativi | 1, 2 |
| 4 | `04-programma-endpoint.md` | `POST /programma` modalità scheda | 2 |
| 5 | `05-frontend-programma.md` | pagina `/territorio` | 4 |
| 6 | `06-zone-osm.md` | selezione zona via tag OSM (niente PostGIS) | 5 |
| 7 | `07-arricchimento-osm-ispra.md` | accessibilità OSM + vincoli ISPRA nella SWOT | 2 (7a), 1-pattern (7b) |
| 8 | `08-idee-territorio.md` | modalità brainstorming (4 generatori) | 3, 4, 5; meglio con 6, 7 |

Verticale minimo dimostrabile: **1 → 2 → 4 → 5**. Il 3 può girare in parallelo al
4–5; il 6 e il 7 sono indipendenti tra loro; l'8 chiude.

## Decisioni prese (non riaprire senza motivo)

- **Selezione zona = entità OSM riconosciute via tag** (`ref:ISTAT` +
  Overpass), non poligoni disegnati. PostGIS/confini archiviato in
  `deferred/06-confini-postgis.md` — serve solo per intersezioni sotto-comunali
  future.
- **Brainstorming = inferenza da premesse verificabili**: i quattro generatori
  (`gap_comparativo`, `fabbisogno`, `incompiuto`, `finestra_finanziamento`)
  derivano le idee dagli scarti dati↔attuato; i guardrail del Pezzo 4 restano e
  si estendono per generatore. Niente idee senza premesse citabili.
- **Peer group deterministico**: stessa regione + popolazione 0.5×–2×, sempre
  dichiarato negli output.
- **Nomi**: route `/territorio` (NON "esplora", già occupato), endpoint unico
  `/programma` con campo `modalita`.
