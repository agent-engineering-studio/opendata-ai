# Fase 5 — Consolidamento e industrializzazione

Data: 2026-06-17 · Branch: `feat/capability-layer` · Prereq: Fasi 0–4 · Pilota: Gioia del Colle (072021)

## Decisioni
1. Batch = **console-script idempotente** (`opendata-batch`) via cron esterno.
2. Gap→Impact = **penalità deterministica iniettata** nello scoring core + "domanda di riuso non soddisfatta"
   in scorecard e sito civico.
3. Export = **CSV dal backend** + **PDF lato frontend** (pdfmake, già dep UI).

## Stream L — Anello valore⇄maturità
- `opendata_core.maturity.scoring`: `score_dimensions(..., reuse_demand_penalty=0.0)` riduce l'Impact;
  `assess_entity` la propaga. Core puro/deterministico.
- Backend `maturity/reuse_demand.py`: aggrega i gap dei report Territorio per comune. `run_assessment(istat_code=...)`
  calcola la penalità, la inietta, e mette `unmet_reuse_demand` in details/scorecard. Sito + scorecard la mostrano.

## Stream M — Batch
- `ingest/batch.py` + console-script `opendata-batch`: ri-assessment maturità + snapshot civico + invalidazione
  cache per gli enti/comuni configurati. Idempotente.

## Stream N — Export + pagina pubblica
- `GET /maturity/entities/{id}/scorecard.csv`. Frontend "Stato maturità open data" (ranking + scorecard) + PDF pdfmake.

## Stream O — Hardening
- "Dato insufficiente" sotto soglia dataset (no punteggi falsi); log strutturati; revisione rate-limit/cache TTL.

## Stream P — Docs finali
- README + CLAUDE.md + docs/architettura.md (mermaid).

## Test & DoD
Integrazione anello (gap→Impact), batch idempotente, regressione completa. DoD: ciclo valore⇄maturità chiuso
e dimostrato sul pilota; batch funzionanti; make lint && make test verdi.

## Commit
L1 core penalità · L2 backend reuse_demand+wire · M1 batch · N1 CSV+frontend+PDF · O1 dato-insufficiente · P1 docs.
