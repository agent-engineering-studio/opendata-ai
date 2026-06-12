# Spec 03 — Ingest bulk OpenCoesione + aggregati locali

**Pezzo 3.** Aggiunge uno **store locale** dei progetti OpenCoesione per le analisi
**aggregate pesanti** che l'API paginata non regge (spesa per tema/comune sull'intero
dataset, top soggetti, capacità attuativa su molti progetti). Due componenti, su due
package, con un confine netto.

## Correzioni rispetto all'idea iniziale

- **Runtime = Postgres** (Postgres locale in dev, **Neon Postgres** in prod),
  schema `opendata`. **Niente PostGIS** in questo pezzo: gli aggregati che servono
  sono per **codice comune ISTAT**, non per geometria, quindi basta una tabella
  Postgres indicizzata — nessun tipo `geometry`. SQLite compare **solo nella suite di
  test** (aiosqlite), grazie ai pattern `_PK` / `_strip_schema` già nel repo; per non
  romperla, l'SQL dell'ingest va scritto portabile.
- **La geometria / intersezione poligono** (caso "disegna la zona industriale") è un
  pezzo a parte: richiede i confini comunali (ISTAT/ISPRA) e l'estensione PostGIS
  (supportata anche da Neon: `CREATE EXTENSION postgis`). In quel pezzo i tipi
  `geometry` andranno protetti con un guard sul path di test SQLite (come già `_PK`).
  **Rimandata** (Pezzo 6+).
- **L'agente legge via MCP, non dal DB** (R13). Quindi gli aggregati locali sono un
  **tool MCP read-only**, attivato solo quando è configurato un DB.

## Componente A — Ingest (backend, possiede il DB)

Il backend possiede session/modelli/migrazioni: l'ingest vive lì.

### Tabella `opendata.oc_progetti`
Modello ORM sul pattern di `db/models.py` (`Base`, `_PK`, `__table_args__ =
({"schema": "opendata"},)`; tipi standard Postgres, nessuna geometria). Campi minimi
(adattare alla discovery del Pezzo 1):

| colonna | tipo | note |
|---|---|---|
| `id` | `_PK` | PK surrogata |
| `clp` | Text, unique | codice locale progetto |
| `cod_comune` | Text, index | codice ISTAT comune |
| `cod_provincia` | Text, index | |
| `cod_regione` | Text, index | |
| `tema` | Text, index | obiettivo tematico |
| `ciclo` | Text, index | 2007-2013 / 2014-2020 / 2021-2027 |
| `natura` | Text | |
| `stato` | Text | stato attuazione |
| `finanziamento_totale` | Numeric | € |
| `pagamenti` | Numeric | € |
| `titolo` | Text | |
| `soggetto_attuatore` | Text | |
| `raw` | JSON | record grezzo per audit |
| `ingested_at` | DateTime(tz) | |

Indice composito `(cod_comune, tema, ciclo)` per gli aggregati tipici.

> ⚠️ **Ownership schema.** Lo schema canonico è il submodule `vendor/agent-stack`
> (vedi `db/models.py` e CLAUDE.md). La migrazione canonica di `oc_progetti` va aggiunta
> **lì**; il backend mantiene il consueto **stub mirror** in
> `migrations/versions/000X_oc_progetti.py` (con `CREATE SCHEMA IF NOT EXISTS opendata`,
> R4) così `alembic upgrade head` funziona anche senza submodule inizializzato.

### CLI di sync
Nuovo entry point `opendata-opencoesione-sync` (sul pattern di `cli.py` /
`[project.scripts]`), one-shot o cron:
1. scarica il **dataset bulk CSV** OpenCoesione (CC BY 4.0) per il ciclo richiesto
   (`--ciclo 2021-2027`, default tutti);
2. normalizza i campi riusando `mapping.py` del core client (Pezzo 1);
3. **upsert** per `clp` (insert/update idempotente); registra `ingested_at`.
Il dato vive su **Postgres** (Neon in prod). L'SQL è scritto **portabile** (SQLAlchemy
core, niente costrutti Postgres-only) al solo scopo di far passare anche i test su
SQLite. Streaming del CSV (no full-load in RAM).

## Componente B — Tool MCP `opencoesione_query_local` (read-only, env-gated)

Nel package `opencoesione-mcp-server` (Pezzo 1). Registrato **solo se** è configurato
`OPENCOESIONE_DB_URL`; senza, il server resta il wrapper live-API puro (uso Claude
Desktop). Connessione **read-only** (no ORM ownership: la tabella è creata dalle
migrazioni del backend/submodule), query parametrizzate.

Tool: `opencoesione_query_local` con `kind` enum (no SQL libero dall'LLM):
- `spend_by_tema(cod_comune, ciclo?)` → somma finanziamento/pagamenti per tema;
- `capacity(cod_comune, ciclo?)` → spend ratio + conclusi/totali sull'intero dataset
  locale (versione "completa" del `funding_capacity` live);
- `top_soggetti(territorio, limit?)` → attuatori più ricorrenti;
- `compare_comuni(cod_comuni[], tema?, ciclo?)` → confronto tra comuni.

> Il **Pezzo 8** (`08-idee-territorio.md`) estende questo stesso tool con i `kind`
> comparativi `similar_projects` / `gap_by_tema` / `stalled_projects`, che richiedono
> in più l'anagrafica comuni (`opendata.comuni_anagrafica`). Qui non implementarli;
> tenere il dispatch sui `kind` facilmente estendibile.

Output con blocco `sources` (cita il dataset bulk + data di `ingested_at` + licenza
CC BY 4.0). Annotations read-only/idempotent. Mai SQL arbitrario: solo i `kind`
predefiniti con parametri validati Pydantic.

## Confine tra i due componenti

- Il **backend** scrive la tabella (ingest, possiede DB/migrazioni).
- L'**MCP server** la legge (read-only) e la espone all'agente.
- Stessa tabella `opendata.oc_progetti`, due connessioni distinte. Nessuna duplicazione
  di modelli: l'MCP usa SQL core read-only, non importa gli ORM del backend.

## Integrazione

- `.env.*.example`: `OPENCOESIONE_DB_URL` (per l'MCP server) + eventuale
  `OPENCOESIONE_BULK_URL` / cron per l'ingest. Riusa `DATABASE_URL` del backend per la CLI.
- `Makefile`: `make oc-sync` (lancia la CLI nel container backend).
- `docker-compose.yml`: passare `OPENCOESIONE_DB_URL` al servizio `opencoesione-mcp`;
  opzionale job/profile per l'ingest schedulato.
- Una volta popolata la tabella, l'`OPENCOESIONE_INSTRUCTIONS` (Pezzo 2) può preferire
  `opencoesione_query_local` per le domande aggregate e tenere i tool live per il
  dettaglio puntuale.

## Definition of Done

- [ ] Modello `OcProgetto` + indice composito; migrazione canonica (submodule) + stub
      mirror nel backend; `alembic upgrade head` ok su Postgres (dev/Neon) e nella
      suite di test su SQLite.
- [ ] CLI `opendata-opencoesione-sync`: download bulk, normalize, upsert idempotente;
      streaming; SQL portabile.
- [ ] Tool `opencoesione_query_local` env-gated su `OPENCOESIONE_DB_URL`, 4 `kind`
      validati, blocco `sources`, read-only.
- [ ] Test: ingest su SQLite con un CSV di esempio piccolo; query dei 4 `kind` su dati
      seed; assenza di `OPENCOESIONE_DB_URL` → il tool non è registrato.
- [ ] `make lint && make test` verdi; `make oc-sync` documentato nel README.
- [ ] Smoke: sync di un ciclo per una provincia pugliese, poi `capacity` e
      `spend_by_tema` su un comune con numeri verificabili contro il portale.
