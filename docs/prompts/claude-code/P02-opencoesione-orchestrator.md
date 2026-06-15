# Prompt Claude Code — P02: aggancio OpenCoesione all'orchestratore

> Eseguire dalla root di `opendata-ai`, **dopo** aver completato il Pezzo 1
> (`opencoesione-mcp-server` funzionante). Leggi `CLAUDE.md` (in particolare **R5**,
> R3, R12) e `docs/specs/02-opencoesione-orchestrator.md`. Lavori dentro
> `opendata-backend/`.

---

Promuovi **OpenCoesione** a specialista di prima classe nel fan-out
`ConcurrentBuilder` del backend, accanto a ckan/istat/eurostat/oecd. OpenCoesione
**non** è SDMX né una fonte di file: è una fonte finanziaria/fattibilità i cui tool
ritornano JSON; le sue risorse sono **citazioni** verso URL dell'API OpenCoesione
(formato `JSON`), non file da scaricare. Agganciala come **specialista autonomo sul
modello del blocco CKAN**, non dentro il loop `sdmx_specs`.

Studia prima questi file e ricalcane lo stile (sono le fonti di verità del contratto):
`orchestrator/parsing.py`, `config.py` (`CKAN_INSTRUCTIONS`, `SYNTH_INSTRUCTIONS`,
`Settings`), `factory.py` (blocco CKAN in `__aenter__`),
`orchestrator/synth.py` (`_normalise_source_tag`, `_SYNTH_SOURCE_ORDER`,
`_capture_tool_resources`, `build_aggregator`), `orchestrator/geo_filter.py`.

## Pre-requisito sul Pezzo 1 (contratto)

Verifica che i tool di `opencoesione-mcp-server` includano in **ogni risultato JSON**
un campo `source_url` (URL API risolvibile della risposta) ed eventualmente
`source_label`. È l'equivalente di `csv`/`path` (istat) e `url`/`content` (ckan), e
serve a `synth._capture_tool_resources` per catturare le citazioni deterministicamente.
Se manca, **aggiungilo nel Pezzo 1** prima di procedere.

## Modifiche (applicarle tutte insieme — R5)

1. **`orchestrator/parsing.py`** — estendi:
   `SourceTag = Literal["ckan", "istat", "eurostat", "oecd", "opencoesione"]`.

2. **`config.py`**
   - Crea `OPENCOESIONE_INSTRUCTIONS` **copiando `CKAN_INSTRUCTIONS` come template** e
     adattandolo: l'agente parte da `opencoesione_search_projects` sul comune ISTAT,
     usa `opencoesione_funding_capacity` per la fattibilità, e nel blocco
     `<!--RESOURCES_JSON-->` emette risorse `{"name","url","format":"JSON","source":"opencoesione"}`
     che citano l'API. Stessa identica struttura di marker/JSON di CKAN.
   - In `Settings` aggiungi `enable_opencoesione: bool`, `opencoesione_mcp_url: str`,
     `opencoesione_agent_name: str = "opencoesione"`, sul modello dei campi `ckan_*`.
   - Aggiorna `SYNTH_INSTRUCTIONS`: il synth deve sapere che la sezione
     `=== OPENCOESIONE ===` porta evidenze di finanziamento/capacità di spesa da
     integrare nella narrativa **senza inventare numeri**.

3. **`factory.py`**
   - Importa `OPENCOESIONE_INSTRUCTIONS`.
   - Aggiungi `("opencoesione", s.enable_opencoesione)` alla lista `enabled`.
   - Aggiungi un blocco partecipante dedicato (come CKAN, **fuori** dal loop
     `sdmx_specs`):
     ```python
     if s.enable_opencoesione:
         oc_mcp = await self._enter_mcp_tool(
             s.opencoesione_agent_name, s.opencoesione_mcp_url,
             "Tools to query OpenCoesione (Italian cohesion-policy funded projects).",
         )
         oc_agent = await self._enter_agent(
             chat_client, OPENCOESIONE_INSTRUCTIONS, s.opencoesione_agent_name,
             [oc_mcp], default_options,
         )
         participants.append(oc_agent)
     ```

4. **`orchestrator/synth.py`**
   - `_normalise_source_tag`: aggiungi `"opencoesione"` ai tag riconosciuti.
   - `_SYNTH_SOURCE_ORDER`: aggiungi `"opencoesione"`.
   - `_capture_tool_resources`: aggiungi un branch `if source == "opencoesione":` che
     legge `source_url`/`source_label` dai payload `function_result` e costruisce
     `Resource(name=..., url=source_url, format="JSON", source="opencoesione")`.
     **Niente download di contenuto** (sono citazioni API).

5. **`orchestrator/geo_filter.py`** — verifica `filter_resources`: assicurati che le
   risorse `opencoesione` (URL con codice ISTAT) non vengano scartate quando l'utente
   nomina un comune. Se serve, riconosci il codice ISTAT nelle URL o esenta
   `source == "opencoesione"`.

6. **`.env.local.example` / `.env.production.example`** — aggiungi
   `ENABLE_OPENCOESIONE`, `OPENCOESIONE_MCP_URL`
   (`http://opencoesione-mcp:8080/mcp` interno / `http://localhost:<port>/mcp` host),
   `OPENCOESIONE_AGENT_NAME` (R9).

7. **Test (R5)**
   - `tests/test_config.py`: copri i nuovi campi `Settings` e l'esistenza di
     `OPENCOESIONE_INSTRUCTIONS`.
   - `tests/test_synth_merge.py`: aggiungi un partecipante `opencoesione` finto che
     emette narrativa + blocco risorse e ha un `function_result` con `source_url`;
     verifica: tag sorgente corretto, presenza della sezione `=== OPENCOESIONE ===`
     nel prompt synth, e cattura deterministica della citazione anche se assente dal
     blocco JSON.

## Vincoli

- Non introdurre nuovi pattern: ricalca CKAN. R3 test via
  `/tmp/oda-venv/bin/python -m pytest -q opendata-backend`. R12 `make lint && make
  test` prima del commit.
- **Non** costruire qui l'endpoint "programma/SWOT": è il Pezzo 4.

## Output atteso

Tutte le modifiche dei 7 punti applicate coerentemente, `make lint && make test`
verdi, e uno smoke test (con `ENABLE_OPENCOESIONE=true` e l'MCP raggiungibile) della
query "zona industriale a <comune pugliese>": la narrativa unificata deve citare
progetti reali e l'indicatore di fattibilità, con risorse `opencoesione` nel blocco
`<!--RESOURCES_JSON-->`. Riepiloga le modifiche per aggiornare la spec.
