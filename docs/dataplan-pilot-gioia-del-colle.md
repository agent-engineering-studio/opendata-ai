# Piano dati dimostrativo — Gioia del Colle (ISTAT 072021)

> Deliverable dell'issue **#179 (D8)**, sotto-fase di **#170**. Applica end-to-end
> il Copilota Open Data (motori #172–#175, backend #222, accompagnamento #184) al
> **pilota Gioia del Colle** per verificare che il percorso regga. Gli output di
> ranking/quick-win/checklist sono **generati dai motori reali** (non a mano).

## 0. Come riprodurlo

```bash
# baseline + adempimenti già aperti + stato di accompagnamento
GET /dataplan/072021/diagnosi
# inventario del potenziale (catalogo D1)
GET /dataplan/072021/inventario
# piano prioritizzato valore×sforzo (quick win in testa)
GET /dataplan/072021/piano
# bozza di Politica Open Data (LLM o fallback offline), storicizzata
POST /dataplan/072021/politica
# export brief operativo per un dataset
POST /dataplan/072021/brief   {"candidate_id": "rifiuti-differenziata"}
```

## 1. Diagnosi a costo zero

- **Portale di riferimento**: `dati.puglia.it` (org `comune-di-gioia-del-colle`).
- **Baseline maturità**: dal `assess_entity` (se già eseguito). Senza un assessment
  salvato, il Copilota è onesto: `pubblicato = null` + *"esegui /maturity/assess"*.
- **Stato di accompagnamento** (#184): con zero/pochi dataset pubblicati →
  **`zero_dati`**, percorso di onboarding `diagnosi → politica → inventario →
  piano → brief`.
- **Già aperto a livello nazionale** (basta linkarlo, zero produzione): Bilancio
  (BDAP/SIOPE), Appalti (ANAC), Progetti PNRR/coesione (OpenPNRR/OpenCoesione),
  Popolazione di benchmark (ISTAT), Ambiente/rischio (ISPRA).

## 2–3. Inventario + prioritizzazione (output reale del motore)

`prioritize(load_catalog())` — quadrante | valore/sforzo | dataset:

| Quadrante | V/S | Dataset |
|---|---|---|
| quick_win | 75/1 | ambiente-qualita-aria *(ISPRA, link)* |
| quick_win | 75/1 | popolazione-anpr *(ISTAT, link)* |
| quick_win | 75/1 | progetti-pnrr-coesione *(OpenPNRR, link)* |
| quick_win | 60/1 | bilancio-siope *(BDAP, link)* |
| quick_win | 30/1 | appalti-anac *(ANAC, link)* |
| quick_win | 70/1 | rifiuti-differenziata *(locale)* |
| quick_win | 55/1 | illuminazione-patrimonio *(locale)* |
| strategico | 70/2 | mobilita-tpl-ztl |
| strategico | 70/2 | pug-zonizzazione *(sblocca la riconciliazione suolo #129)* |
| strategico | 55/4 | esercizi-commerciali-suap *(dati personali)* |
| riempitivo | 40/1 | cultura-turismo-poi |
| basso_valore | 40/2 | tributi-tari |
| basso_valore | 40/4 | edilizia-pratiche-sue *(dati personali)* |
| basso_valore | 10/4 | atti-albo-pretorio *(dati personali)* |

### Lotto quick-win iniziale (coordinato con D16 #187)

7 dataset, tutti a sforzo minimo:
1. **Link** agli adempimenti già aperti: ambiente (ISPRA), popolazione (ISTAT),
   PNRR (OpenPNRR), bilancio (BDAP), appalti (ANAC) → trasparenza immediata, zero
   produzione.
2. **Produzione locale facile**: raccolta differenziata, patrimonio/illuminazione
   (HVD ambiente/geospaziale, nessun dato personale).

## 4. Politica + Piano (D3)

`POST /dataplan/072021/politica` genera la bozza (6 sezioni: finalità, principi
open-by-default, licenza **CC-BY-4.0 / IODL 2.0**, ruoli RACI con gate DPO,
qualità/aggiornamento, riferimenti — CAD, LG AGID Det. 183/2023, HVD Reg. UE
2023/138, GDPR). `GET /piano` produce, per ogni voce, cadenza + ufficio titolare +
**metadati DCAT-AP_IT precompilati** (validati da `validate_dcat`).

## 5. Export brief — due casi reali (output del motore privacy)

### 5a. `rifiuti-differenziata` → **dataset pronto da pubblicare**

Famiglia `generico`, privacy `nullo` → **nessun gate DPO**. Passi:
- Verifica che non restino quasi-identificatori incrociabili.
- Dato non personale: pubblicabile senza gate DPO.

*Dataset simulato pronto* (`CC-BY-4.0`, cadenza trimestrale, Ufficio Ambiente):

```csv
anno,zona,rifiuti_totali_kg,differenziata_kg,percentuale_differenziata
2025,centro,182000,124000,68.1
2025,periferia,240500,151500,63.0
```

Scheda DCAT-AP_IT (estratto, da `generate_dcat`): `dct:title` "Raccolta
differenziata (% per anno/zona)", `dct:publisher` "Comune di Gioia del Colle",
`dct:license` "CC-BY-4.0", `dcat:theme` ENVI, `dct:accrualPeriodicity` trimestrale;
`campi_mancanti` traccia gli editoriali non deducibili (identifier, keyword).

### 5b. `esercizi-commerciali-suap` → **richiede DPO**

Famiglia `commercio_suap`, privacy `personale` → **gate umano obbligatorio**,
k-anonimato **5**. Passi: rimuovere titolare/CF/contatti, aggregare per via/
categoria quando il puntuale identifica una persona, sopprimere celle < 5,
**validazione DPO prima della pubblicazione**. Dimostra il vincolo §7: nessun dato
personale pubblicato senza validazione umana.

## 6. Valore sbloccato (anello Fase 5)

- Pubblicare **PUG** (#129) → alza la confidenza della riconciliazione OSM↔suolo
  nel report Territorio.
- **Differenziata** → popola la lente Ambiente.
- **Popolazione/ISTAT** → sezione popolazione del report Territorio.

Ogni pubblicazione chiude un item di *domanda di riuso non soddisfatta*.

## 7. Verifica pivot + regole

- **Pivot rispettato**: i dataset "già aperti" si **linkano** (non si copiano);
  il Copilota non conserva i dati; i mancanti sono *domanda di riuso* resa
  azionabile. ✅
- **R11**: la prosa di policy/brief usa l'LLM se configurato, altrimenti fallback
  offline deterministico. ✅
- **R4**: persistenza `opendata.dataplan_plans` dialect-aware. ✅
- **#191**: `072021` è in Puglia → passa l'`enforce_region_scope` (un comune fuori
  `REGION` sarebbe respinto con 422). ✅

## Esito

Il percorso end-to-end **regge**: da un comune a zero dati si ottiene una diagnosi
onesta, un lotto quick-win azionabile (5 link + 2 dataset locali), una bozza di
Politica conforme e un export brief con dataset pronto da pubblicare — senza
violare il pivot né R1–R14. KPI del pilota: vedi #187.

## Riferimenti

- Analisi: [`copilota-open-data.md`](copilota-open-data.md) (#170) · design tecnico:
  [`dataplan-tech-design.md`](dataplan-tech-design.md) (#176).
- Motori: `opendata_core/dataplan/*` (#172–#175, #184) · backend `/dataplan/*` (#222).
