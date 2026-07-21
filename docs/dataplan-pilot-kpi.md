# KPI del pilota Gioia del Colle + lotto quick win

> Deliverable dell'issue **#187 (D16)**, sotto-fase di **#170**. Definisce i **KPI
> misurabili** del pilota (con baseline t0 e target) e il **lotto quick win**
> iniziale su fonti realmente disponibili. Complementare al piano dimostrativo
> [`dataplan-pilot-gioia-del-colle.md`](dataplan-pilot-gioia-del-colle.md) (#179).

## Target del pilota

> **≥ 10 dataset conformi DCAT-AP_IT in ≤ 8 settimane, senza un data team.**

Costanti in `opendata_core.dataplan.kpi` (`TARGET_DATASET_CONFORMI=10`,
`TARGET_SETTIMANE=8`).

## Set KPI

I KPI si dividono in **plannabili** (derivabili dal piano, calcolati da
`plan_kpi` ed esposti in `GET /dataplan/072021/piano → kpi`) e **di runtime**
(misurati a valle su pubblicazione/uso; definiti qui col metodo, **mai inventati**).

| # | KPI | Tipo | Fonte / metodo | Baseline t0 | Target |
|---|---|---|---|---|---|
| 1 | N. dataset pubblicati e conformi DCAT-AP_IT | runtime | harvest portale + `validate_dcat` | 0 | ≥ 10 |
| 2 | % dataset con aggiornamento automatico | plannabile/runtime | `plan_kpi.pct_aggiornamento_automatico` (watch `opendata-monitor`) | 0% | ≥ 80% |
| 3 | Tempo medio "fonte individuata → pubblicata" | runtime | timestamp brief → pubblicazione | — | ≤ 2 settimane |
| 4 | Ore-uomo risparmiate vs processo manuale | runtime (stima) | n. artefatti generati × stima ore/artefatto | 0 | — |
| 5 | Download/accessi a 3 mesi (riuso) | runtime | log del portale a T+3m | 0 | crescente |
| 6 | N. dataset HVD coperti | plannabile | `plan_kpi.hvd_coperti_nel_lotto` | 0 | ≥ 3 categorie |
| 7 | Item "domanda di riuso non soddisfatta" chiusi | runtime | anello Fase 5 (`unmet_reuse_demand`) | tutti aperti | decrescente |

**Baseline t0 (Gioia del Colle):** ente a `zero_dati` (nessun dataset conforme
pubblicato, 0% aggiornamento automatico, tutti gli item di domanda di riuso
aperti). Il Copilota parte da qui.

### KPI plannabili — output reale di `plan_kpi` sul catalogo attuale

- `dataset_nel_piano`: 14
- `quick_win`: 7 (di cui **gia_aperti_nazionali** 5 = solo link, **da_produrre** 2)
- `hvd_coperti_nel_lotto`: categorie distinte tra `earth_observation_environment`,
  `statistics`, `geospatial` → **≥ 3** (target #6 raggiunto già dal lotto)
- `target_raggiungibile_dal_lotto`: **false** (7 quick win < 10): il lotto iniziale
  va completato con i dataset `strategico` (mobilità, PUG) per centrare il target #1.

## Lotto quick win iniziale (rischio privacy ~nullo, alto valore)

Coerente con la matrice §6.4 e con l'output del motore (vedi #179):

1. **Link** agli adempimenti già aperti (zero produzione): Bilancio (BDAP/SIOPE),
   Appalti (ANAC), Progetti PNRR (OpenPNRR), Popolazione (ISTAT), Ambiente/rischio
   (ISPRA).
2. **Produzione locale facile**: Raccolta differenziata (HVD ambiente),
   Patrimonio/illuminazione (HVD geospaziale).

Tutti a privacy `nullo`/aggregato e sforzo minimo → pubblicabili subito, senza
gate DPO (a differenza di edilizia/esercizi/atti, rimandati e con validazione
umana).

## Come si misura, in pratica

- **t0**: `GET /dataplan/072021/diagnosi` (+ `assess_entity` per la baseline di
  maturità) → stato `zero_dati`.
- **avanzamento**: dopo ogni pubblicazione, ri-`assess` + watch `opendata-monitor`;
  `plan_kpi.pct_aggiornamento_automatico` cresce col numero di dataset monitorati.
- **a T+8 settimane**: n. dataset conformi (KPI #1) vs target 10; a T+3 mesi:
  download (KPI #5) e item di riuso chiusi (KPI #7).

## Criteri di accettazione

- [x] Set KPI misurabili definito + baseline t0.
- [x] Lotto quick win iniziale individuato su fonti disponibili nel pilota.

## Riferimenti

Parent #170 · dipende da D6 (#177), D8 (#179). Motore: `opendata_core.dataplan.kpi`
(`plan_kpi`), esposto in `GET /dataplan/{istat}/piano`.
