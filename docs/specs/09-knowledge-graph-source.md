# Spec 09 — Knowledge Graph come fonte (tier "evidenza documentale")

**Pezzo 9.** Aggancia il **Knowledge Graph** (repo `knowledge-graph`) come fonte del
fan-out di `opendata-ai`, per coprire il buco "la PA non pubblica i dati": delibere,
PUG/piani urbanistici, bilanci, verbali, relazioni — documenti ingeriti nel KG e
interrogabili con provenienza. Introduce nel programma un **tier di evidenza
documentale**, distinto dal dato aperto certificato.

## Perché è fattibile con poco

Il `knowledge-graph` ha la stessa architettura di `opendata-ai` ed **espone già un
MCP** (`knowledge-graph-mcp`) sopra la sua API. Quindi NON si costruisce un KG: si
**monta l'MCP esistente** come specialista del fan-out, col pattern del Pezzo 2.

**Provenienza verificata**: `RAGResponse.sources` è una lista di `SourceReference` con
`doc_id`, `document_name`, `page_number`, `total_pages`, `text_preview`. Il RAG è
**retrieval-only (nessuna generazione LLM)**: restituisce chunk + triple del grafo con
fonte; l'interpretazione la fa il `programma_agent`. Questo soddisfa il guardrail delle
citazioni e tiene basso il rischio di allucinazione.

## Tool KG rilevanti (già esistenti)

`kg_query` (RAG ibrido vector+graph, ritorna `answer` + `sources` con provenienza),
`kg_search_nodes`, `kg_traverse`, `kg_cypher` (read-only con guardrail), `kg_health`.
Per il programma il principale è **`kg_query`**; `kg_traverse`/`kg_search_nodes` per
esplorazioni mirate. `kg_ingest`/`kg_delete_document` **non** vanno esposti all'agente
del programma (sono write/operativi).

## Integrazione cross-repo

`knowledge-graph` è un deployment separato. `opendata-ai` lo consuma via MCP su HTTP.

- **Transport**: l'orchestratore monta gli MCP via `MCPStreamableHTTPTool`
  (streamable-http, `/mcp`). Il `knowledge-graph-mcp` oggi gira stdio (locale) e SSE
  (Docker, :8080). Va eseguito in **streamable-http** (FastMCP lo supporta) esponendo
  `/mcp`, così l'`_enter_mcp_tool(KG_MCP_URL)` esistente funziona senza modifiche.
  (Piccola aggiunta lato repo KG: opzione transport streamable-http nel server.)
- **Namespace per comune**: i tool KG usano `thread_id`/namespace. Convenzione
  `comune-{cod_comune}` (stessa usata in `kg_ingest`), così i documenti non si
  mescolano tra amministrazioni. Le `KG_INSTRUCTIONS` impongono all'agente di passare
  il namespace del comune in analisi.

## Wiring nel fan-out (pattern Pezzo 2)

1. `orchestrator/parsing.py`: `SourceTag` += `"kg"`.
2. `config.py`: `KG_INSTRUCTIONS` (per il comune in esame interroga `kg_query` sul
   namespace `comune-{cod_comune}`; emetti come risorse le `sources` con provenienza,
   `source:"kg"`; **non** inventare contenuti non presenti nei chunk); `Settings`:
   `enable_kg`, `kg_mcp_url`, `kg_agent_name="kg"`, `kg_namespace_prefix="comune-"`,
   opzionale `kg_ui_url` per i link citazione; aggiorna `SYNTH_INSTRUCTIONS` per la
   sezione `=== KG ===`.
3. `factory.py`: blocco partecipante KG (come opencoesione, fuori da `sdmx_specs`),
   montando solo i tool read di `kg-mcp`.
4. `synth.py`: `_normalise_source_tag` += `kg`; `_SYNTH_SOURCE_ORDER` += `kg`; branch
   di cattura `source=="kg"` che mappa ogni `SourceReference` in
   `Resource(name=document_name, url=<locator>, format="DOC", source="kg",
   description=f"p.{page_number+1}/{total_pages}")`. **Locator**: se `kg_ui_url` è
   configurato, `"{kg_ui_url}/documents/{doc_id}"`; altrimenti un riferimento
   sintetico `kg://{namespace}/{doc_id}#p={page_number}` (citazione comunque
   tracciabile a documento+pagina).

## Tier di evidenza nel programma (evoluzione Pezzo 4)

- **Contratto**: `Evidenza` acquisisce `tier: Literal["certificato","documentale"]`.
  `fonte in {istat, opencoesione, osm}` → `certificato`; `fonte=="kg"` → `documentale`.
- **`PROGRAMMA_INSTRUCTIONS`**: i fatti dal KG sono **evidenza documentale**, non dato
  ufficiale; vanno etichettati come tali e mai presentati come dato aperto certificato.
  Una voce SWOT o una proposta può poggiare su evidenza documentale, ma deve risultare
  chiaramente di quel tier; la `fattibilita.livello` non può essere `"alta"` solo su
  base documentale senza riscontro certificato (resta `media`/`da_verificare`).
- **`guardrails.py`**: l'evidenza `kg` è ammessa ma marcata `documentale`; resta valido
  l'invariante "ogni claim ha una fonte risolvibile" (il `doc_id`/pagina lo è).
- **Frontend (tocco al Pezzo 5)**: `ResourceSource` += `"kg"`; `CitationLink` e
  `FeasibilityBadge` mostrano il tier (chip "documento comunale" vs "dato certificato").

## Prerequisito operativo (non codice)

I documenti del comune entrano nel KG tramite la sua pipeline (`kg_ingest`) sotto il
namespace `comune-{cod_comune}`. Governance: caricare solo documenti pubblici/leciti;
attenzione GDPR (atti con dati personali) — definire chi carica e cosa. Fuori dallo
scope implementativo di questo pezzo, ma da presidiare prima dell'uso reale.

## Fuori scope

- UI di ingestion (esiste nel prodotto KG). `opendata-ai` qui **consuma**, non ingerisce.
- Estrazione/qualità del grafo: responsabilità del repo `knowledge-graph`.

## Definition of Done

- [ ] `knowledge-graph-mcp` avviabile in streamable-http su `/mcp` (opzione transport).
- [ ] `SourceTag` += kg; `KG_INSTRUCTIONS` + Settings (`enable_kg`, `kg_mcp_url`,
      `kg_namespace_prefix`, `kg_ui_url?`); blocco partecipante in `factory.py`.
- [ ] `synth.py`: tag/ordine/cattura `kg` con mapping `SourceReference`→`Resource`
      (provenienza documento+pagina).
- [ ] `Evidenza.tier`; `PROGRAMMA_INSTRUCTIONS`/`guardrails.py` gestiscono il tier
      documentale; fattibilità conservativa su sola base documentale.
- [ ] Frontend: `ResourceSource` += kg; citazioni e badge mostrano il tier.
- [ ] Test: partecipante `kg` finto con `kg_query` mockato (sources con doc/pagina) →
      tag corretto, citazioni catturate con provenienza, tier `documentale` nel programma.
- [ ] `make lint && make test` verdi (opendata-ai); test KG-side invariati.
- [ ] Smoke: comune con un documento ingerito (es. una delibera) → la scheda mostra una
      voce/ proposta con evidenza documentale citata a "documento, pagina", etichettata
      come tier documentale.
