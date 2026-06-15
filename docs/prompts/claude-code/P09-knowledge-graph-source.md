# Prompt Claude Code — P09: Knowledge Graph come fonte del fan-out

> Eseguire dalla root di `opendata-ai`, dopo i Pezzi 1–5. Leggi `CLAUDE.md` (R5, R13)
> e `docs/specs/09-knowledge-graph-source.md`. Tocchi `opendata-backend/` e un piccolo
> ritocco al frontend `opendata-ai-ui/`. Il KG è un **deployment esterno**: lo monti
> via MCP, non lo costruisci.

---

Aggancia il **Knowledge Graph** (`knowledge-graph-mcp`, esterno) come specialista del
fan-out, per coprire i documenti PA non pubblicati come open data (delibere, PUG,
bilanci, verbali). Introduci nel programma il **tier "evidenza documentale"**, distinto
dal dato certificato. Usa il pattern del Pezzo 2 (aggancio OpenCoesione).

Contesto verificato: `kg_query` ritorna `answer` + `sources` (`SourceReference` con
`doc_id`, `document_name`, `page_number`, `total_pages`) → provenienza documento+pagina,
RAG retrieval-only. Esponi all'agente **solo i tool read** (`kg_query`, `kg_search_nodes`,
`kg_traverse`, `kg_cypher`, `kg_health`), **mai** `kg_ingest`/`kg_delete_document`.

Studia: `factory.py` (blocco opencoesione, `_enter_mcp_tool` con `MCPStreamableHTTPTool`),
`config.py` (`OPENCOESIONE_INSTRUCTIONS`, `Settings`), `orchestrator/synth.py`
(`_normalise_source_tag`, `_SYNTH_SOURCE_ORDER`, `_capture_tool_resources`),
`orchestrator/parsing.py`, `orchestrator/programma.py` + `guardrails.py` (Pezzo 4),
`routers/programma.py` (contratto), `opendata-ai-ui/lib/types.ts` +
`components/programma/`.

## Backend

1. `parsing.py`: `SourceTag` += `"kg"`.
2. `config.py`:
   - `KG_INSTRUCTIONS`: per il comune in esame, interroga `kg_query` sul namespace
     `comune-{cod_comune}`; riporta i fatti **solo** se presenti nei chunk; emetti come
     risorse le `sources` con provenienza (`source:"kg"`). Vietato inventare.
   - `Settings`: `enable_kg: bool`, `kg_mcp_url: str`, `kg_agent_name="kg"`,
     `kg_namespace_prefix="comune-"`, `kg_ui_url: str | None = None`.
   - aggiorna `SYNTH_INSTRUCTIONS` per la sezione `=== KG ===` (evidenza documentale).
3. `factory.py`: importa `KG_INSTRUCTIONS`; `("kg", s.enable_kg)` in `enabled`; blocco
   partecipante KG come opencoesione (fuori da `sdmx_specs`), `_enter_mcp_tool(
   s.kg_agent_name, s.kg_mcp_url, "Read-only Knowledge Graph tools over ingested PA documents.")`.
4. `synth.py`:
   - `_normalise_source_tag` += `"kg"`; `_SYNTH_SOURCE_ORDER` += `"kg"`.
   - branch `source=="kg"` in `_capture_tool_resources`: per ogni `SourceReference` del
     risultato `kg_query`, costruisci
     `Resource(name=document_name or doc_id, url=<locator>, format="DOC", source="kg",
     description=f"p.{(page_number or 0)+1}/{total_pages or '?'}")`.
     Locator: se `kg_ui_url` settato → `f"{kg_ui_url}/documents/{doc_id}"`; altrimenti
     `f"kg://comune-{cod_comune}/{doc_id}#p={page_number}"`.
5. **Programma (Pezzo 4)**:
   - `Evidenza` (in `routers/programma.py`): aggiungi `tier: Literal["certificato",
     "documentale"]`. Deriva: `fonte=="kg"` → `documentale`, altrimenti `certificato`.
   - `PROGRAMMA_INSTRUCTIONS`: i fatti KG sono **evidenza documentale**, etichettali
     come tali, mai come dato aperto certificato; `fattibilita.livello` non può essere
     `"alta"` solo su base documentale (usa `media`/`da_verificare`).
   - `guardrails.py`: ammetti l'evidenza `kg` (il `doc_id`/pagina è la fonte
     risolvibile) ma marcala `documentale`; invariante citazione invariato.

## Frontend (ritocco Pezzo 5)

- `lib/types.ts`: `ResourceSource` += `"kg"`; aggiorna i tipi `Evidenza` con `tier`.
- `components/programma/CitationLink.tsx` e `FeasibilityBadge.tsx`: mostra il tier
  (chip "documento comunale" per `documentale` vs "dato certificato"); per `kg` il link
  apre il locator del documento.

## Coordinamento repo KG (annota, non implementare qui)

Il `knowledge-graph-mcp` va eseguito in **streamable-http** su `/mcp` per essere montato
da `opendata-ai` (oggi usa SSE in Docker). Nota nel resoconto la piccola modifica
necessaria lato repo KG (opzione transport), senza applicarla in questo repo.

## Vincoli / test

- R5: aggiorna insieme le fonti di verità (parsing/config/factory/synth + contratto
  programma). R13: solo tool read del KG all'agente. R12 `make lint && make test`.
- Test: partecipante `kg` finto con `kg_query` mockato (sources con doc/pagina) → tag
  `kg`, citazioni catturate con provenienza, `tier="documentale"` nel `ProgrammaResponse`;
  fattibilità non `"alta"` su sola base documentale.

## Output atteso

Wiring KG completo (backend) + tier documentale nel programma + ritocco citazioni nel
frontend; test verdi. Smoke: comune con una delibera ingerita nel KG (namespace
`comune-{cod}`) → la scheda mostra una proposta con evidenza documentale citata a
"documento, pagina", etichettata come tier documentale. Riepiloga (incl. la modifica
transport lato repo KG) per aggiornare la spec.
