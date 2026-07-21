# Copilota Open Data — design tecnico (`dataplan/`, endpoint, UI)

> Design tecnico per l'issue **#176 (D5)**, sotto-fase dell'analisi **#170**.
> Approfondisce la sezione D5 di [`copilota-open-data.md`](copilota-open-data.md):
> layout dei motori, **contratto degli endpoint**, **forma degli artefatti** e
> **backlog implementativo**. Riusa l'esistente, niente riscritture.

## 1. Decisione architetturale (ADR)

**Nuovo motore puro `opendata_core/dataplan/`**, non estensione di `maturity/`.

*Motivazione.* La *pianificazione* (cosa aprire, in che ordine, con quale policy)
è un dominio distinto dalla *valutazione* di maturità (`assess_entity` misura ciò
che esiste). Fonderli inquinerebbe entrambi. `dataplan/` **riusa per iniezione** i
motori esistenti (`maturity/harvest`+`assess_entity`, `value/`, `maturity/hvd`,
Data Quality Lab, convertitori, connettori nazionali, `opendata-monitor`) senza
duplicarli. Coerente con la Capability Layer (motori puri in `opendata_core/`,
orchestrazione + LLM nel backend, UI dedicata).

**Stato di realizzazione:**

| Componente | Stato |
|---|---|
| `dataplan/catalog.py` + `catalog_data.yaml` (D1) | ✅ #172 (in main) |
| `dataplan/prioritize.py` (D2) | ✅ #173 (in main) |
| `dataplan/policy.py` (D3 — struttura policy/piano) | ⏳ #174 |
| `dataplan/privacy.py` (D4 — checklist GDPR) | ⏳ #175 |
| backend `opendata_backend/dataplan/service.py` + router | ⏳ (questo design) |
| UI percorso Copilota | ⏳ (D13 #184) |

## 2. Layout dei moduli

```
opendata_core/dataplan/            # MOTORE PURO (no FastAPI/LLM/rete)
  models.py       # CandidateDataset, GiaAperto            ✅
  catalog.py      # load_catalog(), catalog_by_area()      ✅ (#172)
  prioritize.py   # prioritize() → RankedCandidate          ✅ (#173)
  policy.py       # struttura Politica + Piano (template)   ⏳ #174
  privacy.py      # checklist GDPR per famiglia             ⏳ #175

opendata_backend/
  dataplan/service.py              # orchestrazione: harvest + adempimenti
                                   #   nazionali, iniezione catalogo/pesi/LLM,
                                   #   persistenza warehouse
  routers/dataplan.py              # GET/POST /dataplan/{istat}/...  (auth+ratelimit)
```

L'LLM vive **solo** nel backend (via `opendata_backend.llm.complete` /
`resolve_provider`, R11), mai nei motori puri.

## 3. Contratto degli endpoint

Tutti autenticati (Clerk / dev-bypass) + rate-limited come gli altri. `{istat}` =
codice ISTAT del comune (6 cifre). Tutti **fail-safe**: fonti live non raggiungibili
→ sezione marcata "non disponibile", mai 500.

### `GET /dataplan/{istat}/diagnosi`
Fotografia "quanto sei aperto oggi", a costo zero per l'ente.
- **Riusa:** `maturity.harvest` + `assess_entity` (portale regionale del comune);
  sonda gli adempimenti nazionali già aperti (BDAP/SIOPE, ANAC, OpenCoesione/
  OpenPNRR, ISTAT) via i connettori esistenti.
- **Response:**
```jsonc
{
  "istat": "072021",
  "comune": "Gioia del Colle",
  "pubblicato": {                    // da assess_entity (baseline ODM)
    "n_dataset": 3, "overall": 28.0, "level": "Beginner",
    "dimensioni": { "policy": 20, "portal": 30, "quality": 25, "impact": 15 }
  },
  "gia_aperto_nazionale": [          // adempimenti già coperti (link, non produzione)
    { "id": "bilancio-siope", "fonte": "BDAP/SIOPE", "disponibile": true },
    { "id": "appalti-anac",   "fonte": "ANAC",       "disponibile": true }
  ],
  "sources": [ /* URL citabili */ ]
}
```

### `GET /dataplan/{istat}/inventario`
Il catalogo D1 contestualizzato: candidati con fonte/HVD/privacy/sforzo e flag
"già presente sul portale del comune?" (incrociato con la diagnosi).
- **Riusa:** `dataplan.load_catalog()`; incrocio con l'harvest della diagnosi.
- **Response:** `{ "istat", "candidati": [CandidateDataset + {gia_pubblicato: bool}], ... }`

### `GET /dataplan/{istat}/piano`
Il cuore: candidati **prioritizzati** (D2) + lotto quick-win + piano di pubblicazione.
- **Riusa:** `dataplan.prioritize(catalogo, reuse_boost=…)` dove `reuse_boost`
  deriva dalla *domanda di riuso non soddisfatta* del report Territorio (anello
  Fase 5); `policy.build_piano()` (#174) per cadenze/ruoli/metadati DCAT.
- **Response:**
```jsonc
{
  "istat": "072021",
  "ranking": [ { "candidate": {…}, "valore": 75, "sforzo": 1,
                 "quadrante": "quick_win", "motivazione": "…" }, … ],
  "quick_win": [ /* sottoinsieme quadrante=quick_win */ ],
  "piano": { "voci": [ { "id", "cadenza", "licenza", "ufficio",
                         "metadati_dcat": {…} } ] }
}
```

### `POST /dataplan/{istat}/politica`
Bozza della **Politica Open Data** dell'ente (atto di indirizzo).
- **LLM (R11) + fallback offline deterministico** (template compilato).
- **Body:** `{ "ente_nome"?, "licenza_preferita"? }`. **Response:**
  `{ "titolo", "sezioni": [{ "titolo", "testo" }], "licenza", "generato_con": "llm|offline" }`

### `POST /dataplan/{istat}/brief`
"Export brief" operativo per UN dataset (D9 #180): istruzione per l'ufficio su
come estrarre/de-identificare/pubblicare quel dato.
- **Body:** `{ "candidate_id": "rifiuti-differenziata" }`.
- **Riusa:** `privacy.checklist()` (#175), `quality/dcat.generate_dcat`,
  convertitori (#101/#157). **LLM** per la prosa, fallback offline.
- **Response:** `{ "candidate_id", "passi": [str], "privacy": {regola, soglia},
  "metadati_dcat": {…}, "ufficio": "…", "generato_con": "llm|offline" }`

## 4. Forma degli artefatti

- **Diagnosi / Inventario / Piano**: JSON (sopra), consumati dalla UI e
  ri-esportabili (CSV/PDF) come le scorecard di maturità.
- **Politica**: documento a sezioni (Markdown/PDF) — bozza di delibera.
- **Brief**: scheda operativa per-dataset (passi + privacy + metadati + ufficio).
- **Persistenza (warehouse `opendata.*`, DDL dialect-aware R4):** baseline in
  `maturity_assessments` (riuso); piano/politica in una nuova
  `dataplan_plans` (istat, generato_il, ranking_jsonb, piano_jsonb) —
  append-only, storicizza l'avanzamento (come gli snapshot civici).

## 5. Punti di iniezione LLM (R11)

Sempre via `resolve_provider`, con **fallback offline deterministico**:
- redazione **Politica** e **Piano** in linguaggio amministrativo;
- **export brief** per dataset (prosa dei passi + caveat privacy);
- (opz.) classificazione semantica dei candidati non ovvi.

**Mai LLM:** scoring maturità/valore, prioritizzazione (D2), stima HVD, qualità
ISO 25012 — restano nei motori puri, spiegabili e riproducibili.

## 6. Percorso UI (accompagnamento attivo, D13 #184)

Nuova sezione/percorso guidato (macchina a stati zero→maturo):
1. **Diagnosi** — inserisci il comune → "quanto sei aperto oggi".
2. **Inventario + Piano** — matrice valore×sforzo, lotto quick-win evidenziato.
3. **Politica** — genera la bozza di delibera.
4. **Produzione** — per un dataset: carica l'estratto → Data Quality Lab +
   convertitori + check privacy → dataset pronto (il dato **non** è custodito
   dalla piattaforma: si pubblica sul portale ufficiale).
5. **Valore & Mantenimento** — mostra l'analisi sbloccata + attiva i watch di
   `opendata-monitor`.

R14: alla realizzazione, README + copy pagina + diagramma del percorso.

## 7. Backlog implementativo derivato

| Ordine | Issue | Deliverable |
|---|---|---|
| ✅ | #172 | catalogo D1 |
| ✅ | #173 | prioritizzazione D2 |
| 1 | #174 | `dataplan/policy.py` — Politica + Piano + template DCAT |
| 2 | #175 | `dataplan/privacy.py` — checklist GDPR per famiglia |
| 3 | (nuova) | backend `dataplan/service.py` + router + migrazione `dataplan_plans` |
| 4 | #180 | endpoint/artefatto **brief** per dataset |
| 5 | #181 | routing dataset → ufficio → ruolo (arricchisce piano/brief) |
| 6 | #184 | percorso UI (accompagnamento attivo) |
| 7 | #179 / #187 | validazione + KPI sul pilota Gioia del Colle |
| — | #186 | (scope) pubblicazione su CKAN via write API, con gate umano |

## 8. Vincoli / pivot

- **Pivot:** gli open data sono l'unica fonte ufficiale; il Copilota **non**
  custodisce copie (niente upload/KG surrogato) — assiste la produzione, il dato
  vive sul portale. I dataset mancanti = *domanda di riuso non soddisfatta* resa
  azionabile.
- **Regole:** R1 (build context), R4 (schema `opendata`, DDL dialect-aware),
  R7 (auth), R11 (LLM via resolve_provider + fallback), R14 (docs con la feature).

## Riferimenti

- Analisi madre: [`copilota-open-data.md`](copilota-open-data.md) (#170).
- Motori realizzati: `opendata_core/dataplan/{catalog,prioritize}.py` (#172/#173).
- Riuso: `opendata_core/{maturity,value}/`, `maturity/{harvest,hvd}.py`,
  `opendata_core/quality/` (Data Quality Lab + convertitori), `opencoesione/`,
  connettori MCP (bdap/openpnrr/istat/ckan-ANAC). Docs: `architettura.md`,
  `data-model.md`.
