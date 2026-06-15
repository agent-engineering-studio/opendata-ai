# Prompt Claude Code — P08: modalità "Idee per il territorio"

> Eseguire dalla root di `opendata-ai`, **dopo** i Pezzi 1–5 (il 3 con DB popolato;
> 6–7 migliorano ma non bloccano). Leggi `CLAUDE.md` (R3, R4, R5, R12, R13) e
> `docs/specs/08-idee-territorio.md`. Tocchi `opendata-backend/`,
> `opencoesione-mcp-server/` e `opendata-ai-ui/`.

---

Aggiungi a `POST /programma` la modalità **brainstorming evidence-based**
(`modalita: "idee"`): proposte **nuove per il territorio**, generate dagli scarti tra
ciò che i dati dicono e ciò che è stato fatto, mai dal nulla. Principio: **una
proposta è un'inferenza da premesse verificabili** — l'idea non ha bisogno di fonte,
le premesse sì, tutte. I guardrail del Pezzo 4 restano identici e si estendono.

I **quattro generatori** (tabella completa nella spec §"I quattro generatori"):
`gap_comparativo` (i peer l'hanno fatto, qui no), `fabbisogno` (indicatore critico +
nessun intervento), `incompiuto` (spend ratio basso, asset fermi),
`finestra_finanziamento` (dotazione residua 2021-2027). Anche "assenza di progetti
sul tema" è un'evidenza citabile (query riproducibile con URL).

Studia prima: `orchestrator/programma.py` + `guardrails.py` + `PROGRAMMA_INSTRUCTIONS`
(Pezzo 4), il tool `opencoesione_query_local` e l'ingest (Pezzo 3), `db/models.py` +
`cli.py` + migrazioni (pattern `_PK`/schema), `components/programma o territorio/`
nella UI (Pezzo 5).

## Parte A — Anagrafica comuni (backend)

1. Modello `ComuneAnagrafica` → tabella `opendata.comuni_anagrafica` (`cod_comune`
   unique, `nome`, `cod_provincia`, `cod_regione`, `popolazione` Integer,
   `ingested_at`; **niente geometria**, R4). Migrazione canonica nel submodule +
   stub mirror.
2. CLI `opendata-comuni-sync`: discovery dell'URL CSV ISTAT corrente (elenco comuni +
   popolazione residente), download streaming, upsert idempotente per `cod_comune`.
   `make comuni-sync`.
3. Peer group **deterministico e dichiarato**: stessa regione + popolazione tra
   0.5× e 2× (escluso il comune stesso); fascia configurabile in `Settings` con
   questi default. Va dichiarato in ogni output che lo usa.

## Parte B — Nuovi `kind` in `opencoesione_query_local` (MCP server)

Stesso tool del Pezzo 3, stesso env-gating `OPENCOESIONE_DB_URL`, niente SQL libero.
I tre `kind` richiedono anche `comuni_anagrafica` popolata: se manca → errore
actionable ("esegui `make comuni-sync`"), gli altri `kind` restano disponibili.
- `similar_projects(cod_comune, tema?, ciclo?, limit?)` → progetti dei peer ordinati
  per spend ratio; per ognuno titolo, comune, importi, ratio, CLP, URL portale;
- `gap_by_tema(cod_comune, ciclo?, min_peers?=3)` → temi dove ≥min_peers peer hanno
  finanziato e il comune è a zero o sotto il 25° percentile dei peer;
- `stalled_projects(cod_comune, soglia_ratio?=0.2, ciclo?)` → progetti locali non
  conclusi con pagamenti/finanziato < soglia.
SQL portabile (SQLAlchemy core) per la suite SQLite; output con criteri peer
dichiarati + blocco `sources` (bulk + `ingested_at` + CC BY 4.0).

## Parte C — Backend: modalità `idee`

1. Contratto: `ProgrammaRequest.modalita: Literal["scheda","idee"] = "scheda"`;
   `Proposta.generatore: Literal["gap_comparativo","fabbisogno","incompiuto",
   "finestra_finanziamento"] | None` (obbligatorio se `modalita="idee"`).
2. `config.py`: `IDEE_INSTRUCTIONS` accanto a `PROGRAMMA_INSTRUCTIONS` — stesso
   contratto JSON; proposte = incroci dei 4 generatori; ogni proposta dichiara
   `generatore` e cita le premesse nelle `evidenze`; fattibilità da spend ratio +
   vincoli ISPRA; includi la descrizione dei generatori e un esempio di proposta
   valida per ciascuno. SWOT facoltativa/ridotta in modalità idee.
3. `programma.py`: `build_programma_aggregator` sceglie le INSTRUCTIONS da
   `req.modalita`; in modalità idee il task ai partecipanti chiede esplicitamente
   `gap_by_tema`/`stalled_projects`/`similar_projects` (opencoesione), aggregati con
   dotazione residua, indicatori critici (istat/ispra), accessibilità (osm).
4. `guardrails.py`: requisiti minimi **per generatore** (vedi spec §8C.4 —
   gap_comparativo → URL progetto di un comune ≠ quello in esame; fabbisogno →
   indicatore + ricerca locale; incompiuto → URL progetto locale; finestra → URL
   aggregati). Proposta non conforme → **scartata** (non degradata); `generatore`
   mancante in modalità idee → scartata.
5. Router: nessun endpoint nuovo, `POST /programma` legge `modalita`; audit
   append-only registra anche `modalita`.

## Parte D — UI: tab "Idee" su `/territorio`

Toggle **Scheda | Idee** sui risultati (due chiamate distinte, cache locale per tab);
`IdeaCard.tsx` = variante di `ProposalCard` con badge generatore (etichette: "Fatto
altrove" / "Bisogno scoperto" / "Da completare" / "Finanziabile ora") + evidenze
raggruppate come "Premesse". Badge non solo-colore; disclaimer sempre visibile;
`@media print` esteso. R6: niente `app/api/*`.

## Vincoli

- Non toccare la modalità scheda (regressione zero) né l'orchestratore generico.
- R5: se tocchi il contratto, aggiorna insieme INSTRUCTIONS + parser + test.
- R12 `make lint && make test`; R3 via `/tmp/oda-venv`.

## Test

- Anagrafica: ingest CSV piccolo su SQLite, upsert idempotente.
- `kind` nuovi su seed SQLite (peer group calcolato, gap rilevato, stalled trovato);
  anagrafica assente → errore actionable.
- Guardrail: proposta `gap_comparativo` senza URL comparabile → scartata;
  `fabbisogno` senza indicatore → scartata; `generatore` mancante → scartata;
  modalità scheda invariata.
- UI: build export verde, toggle funzionante.

## Output atteso

Anagrafica + CLI + 3 `kind` + `IDEE_INSTRUCTIONS` + aggregatore parametrico +
guardrail per generatore + tab Idee. Test verdi. Smoke: comune pugliese reale con DB
popolato → modalità idee con ≥1 proposta per ≥2 generatori diversi, premesse
risolvibili, fattibilità coerente. Riepiloga per aggiornare la spec.
