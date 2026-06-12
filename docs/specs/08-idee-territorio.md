# Spec 08 — Modalità "Idee per il territorio" (brainstorming evidence-based)

**Pezzo 8.** Aggiunge a `/programma` (Pezzo 4) una seconda modalità: non più solo la
fotografia SWOT del territorio, ma la **generazione di idee nuove** di politica
pubblica per il comune/la zona in esame. "Nuove" in senso preciso: idee che il
territorio non ha ancora attuato, generate dagli **scarti tra ciò che i dati dicono e
ciò che è stato fatto** — mai inventate dal nulla.

## Principio (estende quello del Pezzo 4, non lo deroga)

**Una proposta non è un claim: è un'inferenza da premesse verificabili.** L'idea in
sé non ha bisogno di una fonte; **le premesse sì, tutte**. Il guardrail "ogni
proposta ≥1 evidenza risolvibile" resta identico — le evidenze ancorano le premesse
del ragionamento (il bisogno, il gap, il comparabile, la finestra di finanziamento) e
il FactChecker deterministico verifica quelle. Il modello è libero di combinare, mai
di inventare fatti. Vietato tutto ciò che vieta il Pezzo 4 (slogan, attacchi,
promesse non finanziate).

## I quattro generatori

| `generatore` | Domanda | Fonte delle premesse | Evidenza tipica |
|---|---|---|---|
| `gap_comparativo` | "I comuni simili l'hanno fatto, qui no" | DB locale (Pezzo 3) + anagrafica peer (8A) | URL progetti dei comparabili + query locale vuota/sotto-media |
| `fabbisogno` | "Il dato segnala un problema senza intervento" | ISTAT / ISPRA / OSM (fan-out) + DB locale | URL indicatore critico + query OpenCoesione senza risultati sul tema |
| `incompiuto` | "I soldi c'erano e qualcosa si è inceppato" | DB locale (Pezzo 3) | URL progetto locale con spend ratio basso / asset sottoutilizzato |
| `finestra_finanziamento` | "Cosa è finanziabile adesso" | `opencoesione_territorial_aggregates` (programmato − pagato, ciclo 2021-2027) | URL aggregati con dotazione residua per tema |

Nota: anche "assenza di progetti sul tema X" è un'evidenza citabile — la query
OpenCoesione per comune+tema che ritorna vuoto è riproducibile e ha una URL.

## 8A — Anagrafica comuni per il peer group (backend)

I generatori comparativi richiedono di sapere quali comuni sono "simili". Serve una
tabella leggera, **senza geometria** (R4, pattern `_PK`/`_strip_schema`):

### Tabella `opendata.comuni_anagrafica`

| colonna | tipo | note |
|---|---|---|
| `id` | `_PK` | |
| `cod_comune` | Text, unique | ISTAT |
| `nome` | Text, index | |
| `cod_provincia` | Text, index | |
| `cod_regione` | Text, index | |
| `popolazione` | Integer | residente, ultima rilevazione |
| `ingested_at` | DateTime(tz) | |

- Migrazione canonica nel submodule `vendor/agent-stack` + **stub mirror** nel
  backend (`CREATE SCHEMA IF NOT EXISTS opendata` in testa), come `oc_progetti`.
- **CLI `opendata-comuni-sync`** (pattern `cli.py`/`[project.scripts]`): scarica
  l'elenco comuni ISTAT con popolazione (CSV pubblico — discovery sull'URL corrente
  in fase 0), upsert per `cod_comune`. Run annuale, idempotente.

### Definizione di peer group (deterministica e dichiarata)

`peers(cod_comune)` = comuni con **stessa regione** e **popolazione tra 0.5× e 2×**
quella del comune in esame (escluso il comune stesso). Niente magia: i criteri sono
fissi, calcolati in SQL e **dichiarati in ogni output** che li usa ("confronto con N
comuni della stessa regione tra X e Y abitanti"). Parametri della fascia
configurabili in `Settings` ma con questi default.

## 8B — Nuovi `kind` in `opencoesione_query_local` (estende il Pezzo 3)

Stesso tool, stesso env-gating su `OPENCOESIONE_DB_URL`, niente SQL libero. I tre
`kind` comparativi richiedono **anche** `opendata.comuni_anagrafica` popolata: se
manca, errore actionable ("esegui `make comuni-sync`"), gli altri `kind` restano
disponibili.

| `kind` | input | output |
|---|---|---|
| `similar_projects` | `cod_comune`, `tema?`, `ciclo?`, `limit?` | progetti dei comuni peer sul tema, ordinati per spend ratio decrescente; per ognuno: titolo, comune, importi, ratio, CLP, URL portale |
| `gap_by_tema` | `cod_comune`, `ciclo?`, `min_peers?` (default 3) | temi dove ≥`min_peers` peer hanno finanziato e il comune è a zero (o sotto il 25° percentile dei peer); per tema: n. peer attivi, mediana importi, esempi |
| `stalled_projects` | `cod_comune`, `soglia_ratio?` (default 0.2), `ciclo?` | progetti locali non conclusi con pagamenti/finanziato < soglia; per ognuno: titolo, importi, ratio, stato, CLP, URL |

Ogni output: criteri del peer group dichiarati + blocco `sources` (dataset bulk +
`ingested_at` + CC BY 4.0). SQL portabile per la suite SQLite come gli altri `kind`.

## 8C — Backend: modalità `idee` su `/programma`

Riusa integralmente l'impianto del Pezzo 4 (stesso fan-out, stesso aggregatore
parametrico, stessi guardrail). Modifiche:

1. **Contratto**:
   - `ProgrammaRequest.modalita: Literal["scheda", "idee"] = "scheda"`;
   - `Proposta.generatore: Literal["gap_comparativo", "fabbisogno", "incompiuto",
     "finestra_finanziamento"] | None = None` (obbligatorio quando
     `modalita="idee"`, assente in modalità scheda).

2. **`config.py`** — `IDEE_INSTRUCTIONS` (nuovo, accanto a `PROGRAMMA_INSTRUCTIONS`):
   stesso contratto JSON di output, ma le proposte vanno generate **incrociando i
   quattro generatori**; per ogni proposta dichiarare `generatore` e citare nelle
   `evidenze` le premesse (comparabile, indicatore, progetto fermo, dotazione
   residua); la `fattibilita` si fonda su spend ratio locale + vincoli ISPRA;
   includere nel prompt la descrizione dei 4 generatori e un esempio di proposta
   valida per ciascuno. La SWOT in modalità idee è facoltativa/ridotta (il focus è
   `proposte[]`).

3. **`orchestrator/programma.py`** — `build_programma_aggregator(programma_agent,
   req)` sceglie le INSTRUCTIONS in base a `req.modalita`. In modalità idee il task
   per i partecipanti chiede esplicitamente anche: `gap_by_tema` + `stalled_projects`
   + `similar_projects` (specialista opencoesione), aggregati con dotazione residua,
   indicatori critici (istat/ispra), accessibilità zona (osm).

4. **`orchestrator/guardrails.py`** — `validate_programma` esteso con requisiti
   minimi **per generatore** (deterministici):
   - `gap_comparativo` → ≥1 evidenza con URL di progetto comparabile (dominio
     OpenCoesione, comune ≠ quello in esame);
   - `fabbisogno` → ≥1 evidenza indicatore (istat/ispra/osm) **e** ≥1 evidenza della
     ricerca locale sul tema;
   - `incompiuto` → ≥1 evidenza con URL di progetto del comune in esame;
   - `finestra_finanziamento` → ≥1 evidenza verso gli aggregati/programmazione.
   Proposta che non soddisfa il suo requisito → **scartata** (non degradata): in
   modalità idee la premessa mancante invalida l'inferenza.
   `generatore` mancante con `modalita="idee"` → scartata.

5. **Router**: nessun endpoint nuovo — `POST /programma` legge `modalita` dal body.
   Audit append-only invariato (registra anche `modalita`).

## 8D — Frontend: tab "Idee" sulla pagina `/territorio`

- Toggle in testa ai risultati: **Scheda** | **Idee** (due chiamate distinte a
  `POST /programma` con `modalita` diversa; cache locale dell'ultima risposta per
  tab).
- `IdeaCard.tsx` = variante di `ProposalCard` con **badge del generatore**
  (etichette UI: `gap_comparativo` → "Fatto altrove", `fabbisogno` → "Bisogno
  scoperto", `incompiuto` → "Da completare", `finestra_finanziamento` →
  "Finanziabile ora") + evidenze raggruppate come "Premesse".
- Badge non solo-colore (accessibilità), disclaimer sempre visibile, stesso
  `@media print`.

## Esiti implementazione (2026-06-12)

- **Fonte anagrafica (discovery)**: nessun CSV ISTAT unico porta codici E
  popolazione; l'elenco completo di IdroGEO non ha la popolazione. Adottato
  `comuni-json` (github.com/matteocontrini/comuni-json, dati ISTAT,
  popolazione censimento 2011): 7.904 comuni, codici zero-padded, un solo
  JSON. Per il banding 0.5×–2× la stalenza è irrilevante; URL sovrascrivibile
  via `COMUNI_ANAGRAFICA_URL`.
- **Semplificazioni dichiarate**: `gap_by_tema` = zero progetti del comune
  sul tema (il 25° percentile della spec è rimandato — il segnale "zero" è il
  più difendibile e il SQL resta portabile); i requisiti per generatore nei
  guardrail sono **domain-based** sulle evidenze (host opencoesione /
  indicatori; per `finestra_finanziamento` serve un URL `aggregati`) — il
  controllo "comune ≠ in esame" via URL sarebbe fragile.
- **Due agenti tool-less** (`programma` e `programma-idee`, stesso client):
  con agent-framework le instructions sono fisse per Agent, quindi la scelta
  per `modalita` avviene in `run_programma` — niente hint runtime.
- `Proposta.generatore` è `str` normalizzato, non Literal (lezione del campo
  `fonte`): un typo non rompe il parse, il guardrail scarta i non validi.
  Il normalizzatore di `fonte` ora strippa anche la decorazione
  ("[opencoesione]" visto in smoke).
- IdeaCard non è un componente separato: `ProposalCard` mostra il badge
  generatore ("Fatto altrove" / "Bisogno scoperto" / "Da completare" /
  "Finanziabile ora") e l'header "Premesse verificabili" quando `generatore`
  è presente.
- **Smoke con dati reali** (mirror PUG 2021-2027 + anagrafica reale, Ollama):
  5 idee su Barletta — 4 `gap_comparativo` dai gap veri del mirror
  (capacità amministrativa, ambiente, energia, cultura/turismo) e 1
  `fabbisogno` con doppia premessa (ISPRA 17,6% area a rischio idraulico +
  ricerca OpenCoesione senza progetti sul tema), tutte `da_verificare`
  (nessuna evidenza di finanziamento → degradazione corretta).

## Ordine e dipendenze

Richiede: Pezzo 3 (DB locale) per i generatori 1 e 3; Pezzo 4 (programma); Pezzo 5
(pagina). Beneficia di: Pezzo 6 (zona OSM), Pezzo 7 (ISPRA/OSM per il generatore 2).
Può essere implementato subito dopo il 4-5 con i soli generatori 2 e 4 attivi, ma la
versione completa vuole il Pezzo 3 popolato.

## Fuori scope

- Fonte "bandi aperti" regionali/PNRR (completamento naturale del generatore 4):
  pezzo futuro, discovery tutta da fare.
- Similarità di comuni più sofisticata (profilo economico, cluster): i criteri
  popolazione+regione bastano e sono spiegabili; non complicare.

## Definition of Done

- [ ] Tabella `comuni_anagrafica` + migrazione (canonica + stub) + CLI
      `opendata-comuni-sync` idempotente; `make comuni-sync`.
- [ ] 3 nuovi `kind` in `opencoesione_query_local` con criteri peer dichiarati,
      `sources`, errore actionable senza anagrafica; test su seed SQLite.
- [ ] `modalita` + `generatore` nel contratto; `IDEE_INSTRUCTIONS`;
      aggregatore che seleziona le INSTRUCTIONS; guardrail per generatore.
- [ ] Test: proposta `gap_comparativo` senza URL comparabile → scartata; `fabbisogno`
      senza indicatore → scartata; `generatore` mancante in modalità idee → scartata;
      modalità scheda invariata (regressione).
- [ ] UI: toggle Scheda/Idee + `IdeaCard` con badge generatore e premesse;
      `next build` verde.
- [ ] `make lint && make test` verdi (R12).
- [ ] Smoke: comune pugliese reale con DB popolato → modalità idee produce ≥1
      proposta per ≥2 generatori diversi, ognuna con premesse risolvibili e
      fattibilità coerente.
