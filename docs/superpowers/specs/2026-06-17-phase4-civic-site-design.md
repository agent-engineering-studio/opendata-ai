# Fase 4 — Sito civico + accountability di community

Data: 2026-06-17 · Branch: `feat/capability-layer` · Prereq: Fasi 0–3 · Pilota: Gioia del Colle (072021)

## Decisioni
1. Community = **micro-servizio `/community/*`** FastAPI + Postgres + ruoli via Clerk.
2. Generatore sito = **backend Jinja2** → bundle statico self-contained (no build Node per comune).
3. Viz statica = **grafici SVG inline** + mappa **Leaflet da CDN**.
4. Snapshot **non sovrascritti** (versioning pubblico). Ogni numero linkato a dataset+licenza; ogni pagina
   riporta snapshot_id/data/sources_version/kpi_version (riproducibilità, linguaggio non politico).

## Stream H — Snapshot & accountability
- Migrazione **0009**: `civic_snapshots(istat_code, snapshot_id, created_at, sources_version, payload_jsonb,
  kpi_jsonb)` UNIQUE(istat_code, snapshot_id) + tabelle community.
- `config_data/civic_kpi.yaml`: KPI civici versionati (id, label, definizione, fonte, direzione).
- `civic/snapshot.py`: crea snapshot dal report Territorio + KPI; `civic/diff.py`: diff "fatto vs non fatto"
  + KPI migliorati/peggiorati; check-in → thread community.

## Stream I — Generatore sito civico
- `civic/site.py` (Jinja2): pagine Stato dell'arte/Investimenti/Opportunità/Rischi/Avanzamento/Community +
  scorecard maturità; SVG inline + Leaflet CDN; footer riproducibilità + link fonte/licenza.
- `POST /territory/{istat}/site/export` (zip), `GET /territory/{istat}/site/preview` (HTML).

## Stream J — Community micro-servizio
- Tabelle: `community_members(clerk_user_id, istat_code, role)`, `community_threads(istat_code, topic_type,
  topic_ref, title, created_by, status)`, `community_posts(thread_id, author, body, status)`.
- `/community/*`: thread (list/create), post (list/create), moderazione (hide) per moderatore/amministratore.
  Identità Clerk, dati minimi, note GDPR.

## Stream K — Frontend + pilota
- Bottone "Sito civico" (preview/export) in Report comune. Pilota: Gioia del Colle con 2 snapshot (2026-H1/H2)
  → diff + preview.

## Test & DoD
Generatore (fixture→HTML valido), diff fra 2 snapshot, endpoint community. DoD: sito esportabile per il pilota
con ≥2 snapshot confrontabili + community attiva; make lint && make test verdi.

## Commit
H1 mig 0009+modelli+test · H2 civic_kpi+snapshot+test · H3 diff+test · I1 generatore+test · I2 export/preview+test ·
J1 community+test · J2 check-in→thread+test · K1 frontend+pilota+docs.
