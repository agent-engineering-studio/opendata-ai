# Prompt Claude Code — P03: ingest bulk OpenCoesione + aggregati locali

> Eseguire dalla root di `opendata-ai`, **dopo** i Pezzi 1 e 2. Leggi `CLAUDE.md`
> (R1, R3, R4, R12, R13 e "Quick reference" sullo schema/submodule) e
> `docs/specs/03-opencoesione-bulk-ingest.md`. Tocchi due package: `opendata-backend/`
> (ingest + tabella) e `opencoesione-mcp-server/` (tool di lettura).

---

Aggiungi uno **store locale** dei progetti OpenCoesione per gli aggregati pesanti.
Runtime = **Postgres** (Postgres locale in dev, **Neon Postgres** in prod), schema
`opendata`. **Niente PostGIS** in questo pezzo: tabella Postgres indicizzata per
codice comune ISTAT, nessun tipo `geometry`. **La geometria/poligono è fuori scope.**
SQLite compare **solo nei test** (aiosqlite): scrivi l'SQL dell'ingest portabile per
non rompere la suite. L'agente legge via MCP (R13): gli aggregati sono un tool MCP
read-only, l'ingest vive nel backend.

Studia prima: `opendata-backend/src/opendata_backend/db/models.py` (`Base`, `_PK`,
pattern schema), `db/session.py`, `db/repositories/`, `cli.py` + `[project.scripts]`,
`migrations/versions/0001_initial.py`; e il core client `opendata_core/.../opencoesione/`
(Pezzo 1, per riusare `mapping.py`).

## Parte A — Backend: tabella + ingest

1. **Modello** `OcProgetto` in `db/models.py` (o un nuovo `db/models_opencoesione.py`
   importato da `db/models.py`), schema `opendata`, `_PK`, `__table_args__` con
   `{"schema": "opendata"}` + indice composito `(cod_comune, tema, ciclo)`. Campi
   secondo la spec (clp unique, cod_comune/provincia/regione, tema, ciclo, natura,
   stato, finanziamento_totale, pagamenti, titolo, soggetto_attuatore, raw JSON,
   ingested_at). Tipi standard Postgres, nessuna geometria; resta compatibile con la
   suite di test su SQLite (pattern `_PK`).

2. **Migrazione**: aggiungi la migrazione canonica nel submodule
   `vendor/agent-stack/db/migrations/opendata/` **e** lo **stub mirror**
   `opendata-backend/migrations/versions/000X_oc_progetti.py` (preceduto da
   `op.execute("CREATE SCHEMA IF NOT EXISTS opendata")`, R4). Verifica
   `alembic upgrade head` su Postgres e su SQLite.

3. **CLI** `opendata-opencoesione-sync` (sul modello di `cli.py` e
   `[project.scripts]`):
   - argomenti: `--ciclo` (default: tutti), `--territorio`/`--regione` opzionale per
     ingest parziale;
   - scarica il **dataset bulk CSV** OpenCoesione (CC BY 4.0) in **streaming** (no
     full-load in RAM);
   - normalizza riusando `mapping.py` del core client;
   - **upsert idempotente** per `clp`; setta `ingested_at`;
   - SQL **portabile** (SQLAlchemy core), niente costrutti Postgres-only — il dato
     vive su Postgres (Neon in prod), la portabilità serve solo a far passare i test
     su SQLite.
   - Riusa `db/session.py` e `DATABASE_URL`.

4. **Repository** read di servizio in `db/repositories/` se utile al backend
   (facoltativo in questo pezzo).

## Parte B — MCP server: tool di lettura `opencoesione_query_local`

Nel package `opencoesione-mcp-server`:

1. Aggiungi una dipendenza/utility di **lettura DB read-only**, attivata **solo se**
   l'env `OPENCOESIONE_DB_URL` è presente. Senza, il server resta il wrapper live-API
   puro (non registrare il tool). Niente import degli ORM del backend: usa SQLAlchemy
   core / query parametrizzate read-only sulla tabella `opendata.oc_progetti`.

2. Registra **un solo** tool `opencoesione_query_local` con un parametro `kind` enum
   (Pydantic), **nessun SQL libero**:
   - `spend_by_tema` (input `cod_comune`, `ciclo?`)
   - `capacity` (input `cod_comune`, `ciclo?`) — spend ratio + conclusi/totali su tutto
     il dataset locale
   - `top_soggetti` (input `territorio`, `limit?`)
   - `compare_comuni` (input `cod_comuni: list[str]`, `tema?`, `ciclo?`)
   Output formattato (markdown/json) con blocco `sources` che cita il dataset bulk +
   `ingested_at` + licenza CC BY 4.0. Annotations read-only/idempotent.
   Tieni il dispatch sui `kind` facilmente estendibile: il Pezzo 8 ne aggiunge tre
   (`similar_projects`/`gap_by_tema`/`stalled_projects`) — **non** implementarli qui.

3. Aggiorna le `instructions` del server e il README (sezione "Local aggregates").

## Integrazione

- `.env.local.example` / `.env.production.example`: `OPENCOESIONE_DB_URL` per il
  servizio `opencoesione-mcp`; opzionale `OPENCOESIONE_BULK_URL`. L'ingest usa
  `DATABASE_URL`.
- `docker-compose.yml`: passa `OPENCOESIONE_DB_URL` a `opencoesione-mcp`; opzionale
  profile/job per il sync schedulato.
- `Makefile`: `make oc-sync` (esegue la CLI nel container backend).
- (Coordinamento Pezzo 2) Nota nel resoconto che, con la tabella popolata,
  `OPENCOESIONE_INSTRUCTIONS` può preferire `opencoesione_query_local` per le domande
  aggregate e tenere i tool live per il dettaglio puntuale — **non** modificarlo qui se
  non necessario.

## Test (R3 via /tmp/oda-venv)

- Backend: ingest di un CSV di esempio **piccolo** su SQLite → conta righe, verifica
  upsert idempotente (due run = stesso numero di righe).
- MCP server: seed di poche righe su SQLite, poi i 4 `kind`; e il caso
  **`OPENCOESIONE_DB_URL` assente → tool non registrato**.

## Vincoli

- R1 build context repo root (se tocchi Dockerfile/compose). R4 schema `opendata` +
  SQL portabile per la suite SQLite. R13 dati all'agente solo via MCP. R12 `make lint
  && make test` prima del commit. Niente PostGIS, niente geometria.

## Output atteso

Tabella + migrazione (canonica nel submodule + stub) + CLI di sync nel backend; tool
`opencoesione_query_local` env-gated nell'MCP server; env/compose/Makefile aggiornati;
test verdi. Smoke: sync di un ciclo per una provincia pugliese, poi `capacity` e
`spend_by_tema` su un comune con numeri controllabili contro il portale. Riepiloga per
aggiornare la spec.
