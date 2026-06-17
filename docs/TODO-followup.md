# TODO / follow-up — dopo il merge del capability layer (Fasi 0–5)

Stato: PR #14 (Fasi 0–5) **mergiata** su `main` (commit `02b5e68`). Questo file
raccoglie ciò che resta da fare. Pilota: Comune di Gioia del Colle (ISTAT 072021).

## 1. Da chiudere a breve (merge & deploy)
- [ ] **PR #13** — fix Windows/CRLF (`migrate.sh` LF, `.gitattributes`) + buffer header
      nginx per i cookie Clerk. Aperta su `fix/windows-crlf-and-clerk-nginx-buffers`.
      Mergiare per build pulite su checkout Windows e per evitare il 400 nginx con Clerk.
- [ ] **Verifica CI `docker-build` su `main`**: al merge i job `lint-and-test` erano tutti
      verdi, i `docker-build` ancora pending. Controllare che le 7 immagini buildino
      (incl. la nuova `maturity-mcp-server`). Actions del repo.
- [ ] **Deploy ambiente target** (in ordine):
  1. `git pull` su `main`.
  2. Switch Postgres → **`postgis/postgis:16-3.4`** (riusa il volume) e
     `alembic upgrade head` (applica migrazioni **0007 → 0009**).
  3. `make build` (o almeno `opendata-backend`, `maturity-mcp`, `opendata-ai-ui`) e `up -d`.
  4. `.env`: confermare `ANTHROPIC_API_KEY` (semantico/narrazioni), eventuale
     `MATURITY_MCP_PORT` (18087); le nuove dep (`geoalchemy2`, `pyyaml`, `jinja2`)
     sono in `pyproject` → entrano col rebuild.
- [ ] **Cron** per `opendata-batch --snapshot-id <periodo>` (es. 2026-H2) off-peak
      (aggiorna maturità + snapshot civici, idempotente). Vedi `config_data/batch_targets.yaml`.
- [ ] **Pulizia branch** mergiato: `git branch -d feat/capability-layer` (+ `--delete` remoto).

## 2. Completamenti funzionali (quando ci sono i dati / il tempo)
- [ ] **Ingest GTFS reale**: il connettore (`opendata_core.gtfs` + `etl/mobility.py`) è
      pronto ma nessun feed è stato ingerito per il pilota (→ `distance_to_nearest_stop`
      e mobilità PugliaTrip parziali). Serve un URL feed GTFS regionale → `ingest_gtfs_url`.
- [ ] **Feature data-scarce**: `age_25_44_share`, `hiring_variation`, `fragility_index`
      restano `null` + gap documentato (servono microdati ISTAT/INPS). Integrare le fonti.
- [ ] **Permanenza turistica**: oggi proxy dai POI OSM; sostituire con dato presenze ufficiale.
- [ ] **Wikidata enrichment**: client pronto (`opendata_core.wikidata`) ma non ancora
      cablato nel profilo `place` (popolazione/area/sito). Agganciarlo in `territory.build_profile`.
- [ ] **Link ente↔comune** nell'anello valore⇄maturità: oggi è euristico (match per nome).
      Valutare un mapping esplicito (es. `entities.istat_code` o tabella di raccordo).

## 3. Hardening / qualità (consolidamento)
- [ ] **Osservabilità**: i log sono strutturati (campi chiave) ma non c'è un endpoint
      `/metrics` (Prometheus) né tracce. Valutare metriche su assess/report/site.
- [ ] **Revisione rate-limit / cache TTL**: TTL attuali (classify 24h, fetch 6h, maturity 24h,
      ecc.) e `RATE_LIMIT_PER_MINUTE` da tarare sul carico reale di produzione.
- [ ] **Pagina pubblica maturità realmente anonima**: oggi `/maturita` è dietro auth (R7: niente
      endpoint anonimi). Per una pubblicazione open, esportare come parte del sito civico statico.
- [ ] **Renormalizzazione CRLF** dei file pre-esistenti (`.py`/`.json`/`.j2`): dopo che il
      `.gitattributes` della PR #13 è in `main`, fare un commit di `git add --renormalize .`.
- [ ] **Dev frontend**: `node_modules` locale è incompleto (typecheck mostra solo errori di
      risoluzione `recharts`/`pdfmake`/`@clerk`); `npm ci` per uno sviluppo locale pulito.
      Le 7 pagine nuove (scorecard/valore/territorio-report/usecases/sito-civico/maturita)
      buildano in CI.

## 4. Allineamento submodule (debito noto, pre-esistente)
- [ ] Le migrazioni 0007–0009 sono **stub** che rispecchiano il submodule read-only
      `vendor/agent-stack` (non materializzato). Quando il submodule sarà presente,
      aggiungere i gemelli canonici e tenere gli stub in sync.

## 5. Idee/estensioni (non bloccanti)
- [ ] `value-mcp` separato (oggi il valore è solo backend — scelta di scope di Fase 2).
- [ ] Overpass self-hosted (`--profile overpass`) per conteggi/landmark stabili (i mirror
      pubblici a volte throttlano: 504 → fail-safe già gestito).
- [ ] Showcase aggiuntivi (`showcases_data/*.yaml`) oltre ai 3 di esempio.
