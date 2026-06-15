# Spec 04 — Endpoint "Programma Evidence-Based" (verticale PA)

**Pezzo 4.** Il cuore del verticale per sindaci/amministratori. Dato un comune (e
opzionalmente una zona/tema), produce una **scheda programmatica strutturata**:
SWOT territoriale + proposte concrete, **ogni affermazione ancorata a una fonte
risolvibile**, con stima di fattibilità basata sulla capacità di spesa storica del
comune. Output = **analisi verificabile, non propaganda**.

## Principio (non negoziabile)

Separazione netta dato → evidenza → proposta. Nessun claim senza fonte risolvibile.
**Niente contenuto persuasivo**: il sistema rifiuta slogan, attacchi agli avversari,
toni da campagna. È ciò che distingue "AI per il bene pubblico" da un generatore di
materiale elettorale.

## Architettura: riuso del fan-out con sintesi dedicata

`build_workflow(participants, aggregator)` accetta un aggregatore parametrico
(vedi `run()` che fa lo swap di `build_aggregator` per chiamata). Sfruttiamo questo:
**stesso fan-out di specialisti** (istat + opencoesione [+ altri]), **aggregatore
diverso** che produce la scheda strutturata invece della prosa generica. L'orchestratore
generico **non si tocca**.

```
POST /programma → session.run_programma(req)
   └─ build_workflow(self._participants, programma_aggregator)   # stessi partecipanti
        ├─ fan-out: istat + opencoesione raccolgono evidenze sul comune (in parallelo)
        └─ programma_aggregator:
             1. parse_agent_reply + _capture_tool_resources → evidence bundle
             2. programma_agent (tool-less, Sonnet) + PROGRAMMA_INSTRUCTIONS
                → JSON strutturato (SWOT + proposte)
             3. guardrails: ogni claim/proposta ha ≥1 citazione risolvibile;
                disclaimer presente; nessun linguaggio persuasivo
             4. ProgrammaResponse validato
```

## Punti di modifica

### 1. `orchestrator/programma.py` (nuovo)
- `build_programma_aggregator(programma_agent, req: ProgrammaRequest) -> aggregator`
  sul modello di `build_aggregator` in `synth.py`: per ogni partecipante usa
  `parse_agent_reply` + `_capture_tool_resources` per ottenere narrative + risorse
  taggate per `source`; costruisce un **evidence bundle** (testo per fonte + elenco
  risorse con URL risolvibili); passa il bundle a `programma_agent.run(...)`; fa il
  parse/validazione del JSON strutturato; ritorna un oggetto `.text` = JSON serializzato
  (così `events.get_outputs()` continua a funzionare) **oppure** un wrapper dedicato.

### 2. `orchestrator/guardrails.py` (nuovo) — il "FactChecker" deterministico
- `validate_programma(resp: ProgrammaResponse, evidence_urls: set[str]) -> ProgrammaResponse`:
  - ogni voce SWOT e ogni proposta deve avere ≥1 `evidenze[]` con `url` presente
    nell'insieme delle URL realmente raccolte dagli specialisti → le voci orfane
    vengono **scartate** (non inventate);
  - una proposta senza evidenza di finanziamento → `fattibilita.livello = "da_verificare"`,
    e **non può** dichiarare una linea di finanziamento;
  - `disclaimer` obbligatorio; se assente, iniettato;
  - euristica anti-persuasione: flag/rimozione di claim con marcatori da campagna
    (prima/seconda persona esortativa, superlativi non supportati). Conservativo:
    meglio scartare che lasciar passare.

### 3. `config.py`
- `PROGRAMMA_INSTRUCTIONS` (nuovo): istruisce `programma_agent` a emettere **solo** il
  JSON del contratto sotto, in italiano, sobrio e tecnico; vietati slogan/attacchi/
  promesse non finanziate; ogni voce SWOT e proposta DEVE citare le `evidenze` (con
  `url`) ricevute nel bundle; la fattibilità si fonda sullo spend ratio OpenCoesione.
- `Settings`: `enable_programma: bool = True`, `programma_agent_name: str = "programma"`,
  `programma_model` opzionale (default = `claude_model`, preferibilmente Sonnet).

### 4. `factory.py`
- Costruire `programma_agent` in `__aenter__` **come synth** (tool-less, con
  `PROGRAMMA_INSTRUCTIONS`), conservarlo nella sessione.
- Aggiungere `OrchestratorSession.run_programma(req)`: sotto lo stesso `self._lock`,
  `aggregator = build_programma_aggregator(self._programma_agent, req)`;
  `workflow = build_workflow(self._participants, aggregator)`; `await workflow.run(...)`;
  estrarre e ritornare il `ProgrammaResponse`.

### 5. `routers/programma.py` (nuovo)
- `POST /programma`, `Depends(enforce_rate_limit)` (auth come gli altri), usa
  `session_holder.session`. Input `ProgrammaRequest`, output `ProgrammaResponse`.
- Opzionale `POST /programma/stream` (NDJSON) sul modello di `/datasets/search/stream`.
- **Audit log** (requisito etico): scrivere su `opendata.history` (o nuova tabella
  `opendata.programma_runs`) la query, le fonti citate e un sommario, append-only.
- Registrare il router in `main.py`.

### 6. Contratto dati (Pydantic)

```python
class Evidenza(BaseModel):
    fonte: Literal["istat", "opencoesione", "ckan", "osm", ...]
    url: str            # risolvibile
    dettaglio: str      # cosa dice il dato (no interpretazione)

class VoceSwot(BaseModel):
    testo: str
    evidenze: list[Evidenza]   # ≥1 obbligatoria

class Fattibilita(BaseModel):
    livello: Literal["alta", "media", "bassa", "da_verificare"]
    motivazione: str
    spend_ratio_storico: float | None = None   # da OpenCoesione

class Proposta(BaseModel):
    titolo: str
    descrizione: str
    evidenze: list[Evidenza]                    # ≥1 obbligatoria
    finanziamento: dict | None = None           # {linea, fonte_url, stato} o None
    fattibilita: Fattibilita

class ProgrammaRequest(BaseModel):
    cod_comune: str                # ISTAT
    zona: str | None = None        # descrizione zona testuale (fallback)
    zona_tipo: str | None = None   # tassonomia ZonaTipo (Pezzo 6); None = livello comune
    zona_osm_id: str | None = None # entità OSM selezionata, es. "way/123" (Pezzo 6)
    tema: str | None = None
    cicli: list[str] | None = None

class ProgrammaResponse(BaseModel):
    comune: str
    zona: str | None
    swot: dict[str, list[VoceSwot]]   # forze/debolezze/opportunita/minacce
    proposte: list[Proposta]
    citazioni: list[Resource]         # tutte le fonti risolvibili usate
    disclaimer: str                   # obbligatorio
    generato_il: datetime
```

## Esiti implementazione (2026-06-12)

- Contratto definito in `orchestrator/programma.py` (il router lo importa da
  lì — unica fonte, niente duplicazione): `finanziamento` è un modello tipizzato
  (`linea`/`fonte_url`/`stato`), non un dict libero; l'LLM emette solo
  `swot+proposte+disclaimer`, il resto (comune, citazioni, generato_il) lo
  assembla l'aggregatore. `comune` nella risposta è il codice ISTAT richiesto.
- Guardrail aggiuntivo oltre la spec: un `finanziamento` con `fonte_url` non
  raccolta viene rimosso (e la proposta degrada a `da_verificare`) — vietato
  dichiarare linee inventate, non solo assenti.
- `build_programma_aggregator` accetta `instructions_hint` parametrico: è il
  gancio per la modalità `idee` del Pezzo 8 senza refactoring.
- Audit: `opendata.history` append-only via il repository esistente; se il
  database non è configurato (solo dev) l'endpoint resta usabile e il salto è
  loggato come warning.
- `/programma/stream` (opzionale) rimandato.
- `programma_model` ha effetto solo col provider claude (client dedicato);
  con ollama/foundry riusa il client di sessione.
- Smoke con Ollama qwen2.5:32k (istat+opencoesione): scheda su Barletta con
  voci ancorate a URL opencoesione reali, proposta senza finanziamento →
  `da_verificare`, disclaimer presente; lo specialista ISTAT che allucina un
  dataflow fallisce con grazia senza rompere la scheda.

## Fuori scope

- Frontend (pagina `/territorio` con scheda, citazioni cliccabili + export PDF) =
  **Pezzo 5**.
- Selezione della zona tramite **entità OSM riconosciute** (valorizzazione di
  `zona_tipo`/`zona_osm_id` e iniezione di nome/centroide/bbox nel task del
  fan-out) = **Pezzo 6** (`06-zone-osm.md`). Finché non è attivo, i due campi
  restano `None`, `zona` è testuale e la selezione è a livello comune.
- Modalità brainstorming (`modalita: "idee"`, quattro generatori) = **Pezzo 8**
  (`08-idee-territorio.md`). Questo pezzo implementa la sola modalità scheda;
  progettare `build_programma_aggregator` già parametrico sulle INSTRUCTIONS
  rende il Pezzo 8 un'estensione e non un refactoring.

## Definition of Done

- [ ] `orchestrator/programma.py` + `guardrails.py`; `run_programma` in `factory.py`;
      `programma_agent` costruito in `__aenter__` come synth.
- [ ] `PROGRAMMA_INSTRUCTIONS` + campi `Settings`; router registrato in `main.py`.
- [ ] Contratto Pydantic completo; **validazione**: voci/proposte senza citazione
      risolvibile scartate; disclaimer garantito; fattibilità senza finanziamento →
      `da_verificare`.
- [ ] Audit append-only su `opendata.*`.
- [ ] Test: (a) request finta con evidence bundle noto → struttura corretta;
      (b) claim orfano → scartato; (c) proposta senza finanziamento → `da_verificare`;
      (d) tentativo di linguaggio persuasivo → flaggato/rimosso.
- [ ] `make lint && make test` verdi.
- [ ] Smoke: `POST /programma` con un comune pugliese reale → SWOT e proposte con
      citazioni ISTAT/OpenCoesione risolvibili e indicatore di fattibilità coerente.
