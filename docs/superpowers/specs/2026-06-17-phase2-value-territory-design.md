# Fase 2 — Valore + modalità Territorio

Data: 2026-06-17 · Branch: `feat/capability-layer` · Prereq: Fasi 0–1 · Pilota: Gioia del Colle (072021)

## Decisioni
1. **/territory/report strutturato dal modello canonico** (place/investment/signal/feature_store)
   + narrazione Sonnet standalone, persistito in `territory_reports`. Distinto da `/programma`
   (fan-out conversazionale, invariato) — niente duplicazione dell'orchestratore.
2. **Client REST OpenCoesione in `opendata_core.opencoesione`** (live per comune) → tabella `investment`.
3. **Value solo backend** (no value-mcp). Engine puro in `opendata_core.value`.
4. **value_card** = campo OPZIONALE su `Resource` (additivo, retro-compatibile).
5. Semantico/narrativa LLM iniettati/standalone; scoring puro deterministico (test offline).

## Stream A — Valore
- `opendata_core/value/`: `estimate_value(ds, *, reuse_score=None) -> ValueScore` — 4 criteri art. 14
  Dir. (UE) 2019/1024 (socio-economico, platea/PMI, proventi, combinabilità) 0–100 + overall +
  hvd_category; `combinability(ds)` (chiavi spaziali/temporali). Riusa `DatasetInput`.
- Backend `value/`: `impact_metrics` (reuse da favorites/history/classifications), `value_card` builder,
  POST `/value/narrative` (Sonnet), GET `/value/portfolio`. value_card additivo in `/datasets/search`.
- Frontend `app/valore/`: dashboard portfolio.

## Stream B — Territorio
- `opendata_core/opencoesione/`: client REST `projects_for_comune(istat, anno_da, anno_a)`.
- `opendata_core/territory/`: `resolve_place` (riusa geocode_boundary), `build_profile` (population da
  ComuneAnagrafica iniettata; business/tourism/work da POI OSM) → popola i signal.
- Backend `territory/`: POST `/territory/report` (profilo+investimenti+servizi+segnali+idee placeholder+gap,
  narrazione Sonnet, persist territory_reports), GET `/territory/{istat}/profile` (feature_store cache).
- Frontend `app/territorio-report/`.

## Test & DoD
Unit value scoring + territory profile + opencoesione client (mock); endpoint con mock; retro-compat
`/datasets/search`; report reale Gioia del Colle end-to-end. DoD: value card su ogni dataset, report
città generato, `make lint && make test` verdi.

## Commit
A1 value engine+test · A2 backend value+search · A3 frontend dashboard ·
B1 opencoesione client+test · B2 territory resolve/profile+test · B3 backend /territory+persist+test ·
B4 frontend report · B5 docs + pilota end-to-end
