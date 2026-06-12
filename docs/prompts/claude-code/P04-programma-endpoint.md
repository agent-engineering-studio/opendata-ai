# Prompt Claude Code — P04: endpoint "Programma Evidence-Based"

> Eseguire dalla root di `opendata-ai`, **dopo** i Pezzi 1–3. Leggi `CLAUDE.md` (R5,
> R7 auth, R12) e `docs/specs/04-programma-endpoint.md`. Lavori in `opendata-backend/`.

---

Costruisci un endpoint che, dato un comune (+ zona/tema opzionali), produce una
**scheda programmatica strutturata** (SWOT + proposte) per sindaci/amministratori,
con **ogni affermazione ancorata a una fonte risolvibile** e fattibilità basata sulla
capacità di spesa storica (OpenCoesione). **Output = analisi verificabile, non
propaganda.** Vietati slogan, attacchi agli avversari, promesse non finanziate.

Studia prima: `orchestrator/synth.py` (`build_aggregator`, `parse_agent_reply`,
`_capture_tool_resources`, forma dell'output), `orchestrator/workflow.py`
(`build_workflow(participants, aggregator)`), `factory.py` (`OrchestratorSession`,
costruzione di `synth_agent` in `__aenter__`, `run()` con lo swap dell'aggregatore),
`routers/datasets.py` (pattern endpoint: `enforce_rate_limit`, `session_holder`,
`/datasets/search/stream`), `config.py` (`SYNTH_INSTRUCTIONS`, `Settings`),
`db/models.py` + `routers/me.py` (audit/history).

## Principio architetturale

**Riusa il fan-out esistente con un aggregatore dedicato.** Non toccare
l'orchestratore generico: come `run()` fa lo swap di `build_aggregator`, crea un
`build_programma_aggregator` e una `run_programma` che fanno
`build_workflow(self._participants, programma_aggregator)`.

## Modifiche

1. **`orchestrator/programma.py`** (nuovo) — `build_programma_aggregator(programma_agent,
   req)` sul modello di `build_aggregator`:
   - per ogni partecipante: `parse_agent_reply` + `_capture_tool_resources` →
     narrative per fonte + risorse taggate (URL risolvibili);
   - costruisci un **evidence bundle** (testo per fonte + risorse) e l'insieme
     `evidence_urls`;
   - `await programma_agent.run(<bundle + richiesta>)` → JSON strutturato;
   - parse + `validate_programma(...)` (vedi sotto) → `ProgrammaResponse`;
   - ritorna un wrapper con `.text` = JSON serializzato (così `events.get_outputs()`
     resta compatibile) e/o l'oggetto tipizzato.

2. **`orchestrator/guardrails.py`** (nuovo) — il FactChecker deterministico:
   `validate_programma(resp, evidence_urls)`:
   - scarta voci SWOT/proposte le cui `evidenze[].url` non sono in `evidence_urls`
     (niente claim orfani o inventati);
   - proposta senza evidenza di finanziamento → `fattibilita.livello="da_verificare"`
     e `finanziamento=None`;
   - garantisci `disclaimer` (inietta se assente);
   - euristica anti-persuasione conservativa (esortazioni, superlativi non supportati)
     → flag/rimozione.

3. **`config.py`**:
   - `PROGRAMMA_INSTRUCTIONS`: l'agente emette **solo** il JSON del contratto, in
     italiano, sobrio/tecnico; ogni voce SWOT e proposta DEVE citare le `evidenze`
     (con `url`) del bundle; fattibilità fondata sullo spend ratio OpenCoesione;
     vietati slogan/attacchi/promesse non finanziate. Includi un esempio di JSON valido.
   - `Settings`: `enable_programma: bool = True`, `programma_agent_name="programma"`,
     `programma_model` opzionale (default `claude_model`, Sonnet preferito).

4. **`factory.py`**:
   - costruisci `programma_agent` in `__aenter__` **come synth** (tool-less, con
     `PROGRAMMA_INSTRUCTIONS`), salvalo come `self._programma_agent`;
   - aggiungi `async def run_programma(self, req) -> ProgrammaResponse`: sotto
     `self._lock`, `aggregator = build_programma_aggregator(self._programma_agent, req)`,
     `workflow = build_workflow(self._participants, aggregator)`,
     `events = await workflow.run(<query derivata da req>)`, estrai e ritorna il
     `ProgrammaResponse`.

5. **`routers/programma.py`** (nuovo):
   - modelli Pydantic del contratto (`Evidenza`, `VoceSwot`, `Fattibilita`, `Proposta`,
     `ProgrammaRequest`, `ProgrammaResponse`) — vedi spec §6;
   - `POST /programma`, `Depends(enforce_rate_limit)`, via `session_holder.session` →
     `run_programma`;
   - opzionale `POST /programma/stream` (NDJSON) sul modello di
     `/datasets/search/stream`;
   - **audit append-only** su `opendata.*` (riusa `history` o aggiungi
     `programma_runs`): query, fonti citate, sommario;
   - registra il router in `main.py`.

## Vincoli

- Non toccare l'orchestratore generico né il `synth` esistente: aggiungi accanto.
- R7: l'endpoint passa da `Depends(enforce_rate_limit)`/`require_user`, mai anonimo.
- Niente selezione zona qui: i campi `zona_tipo`/`zona_osm_id` del contratto restano
  `None` finché il Pezzo 6 (`06-zone-osm.md`) non li valorizza; `zona` è testuale e
  la selezione a livello comune.
- Progetta `build_programma_aggregator` con le **INSTRUCTIONS parametriche** (non
  hard-coded): il Pezzo 8 aggiunge `modalita: "idee"` con `IDEE_INSTRUCTIONS` e deve
  essere un'estensione, non un refactoring.
- Frontend escluso (Pezzo 5).
- R12 `make lint && make test` prima del commit; R3 test via `/tmp/oda-venv`.

## Test

- evidence bundle finto noto → `ProgrammaResponse` ben formato;
- claim con `url` non in `evidence_urls` → scartato;
- proposta senza finanziamento → `fattibilita.livello="da_verificare"`, `finanziamento=None`;
- input con linguaggio persuasivo → flaggato/rimosso;
- disclaimer sempre presente.

## Output atteso

`programma.py` + `guardrails.py` + `run_programma` + router registrato + contratto
Pydantic + `PROGRAMMA_INSTRUCTIONS` + audit; test verdi. Smoke: `POST /programma` su un
comune pugliese reale → SWOT e proposte con citazioni ISTAT/OpenCoesione risolvibili e
fattibilità coerente con lo spend ratio. Riepiloga per aggiornare la spec.
