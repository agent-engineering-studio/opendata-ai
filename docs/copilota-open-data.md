# Copilota Open Data per l'ente (Data Officer AI) — analisi e design

> Documento di analisi/design per l'issue **#170**. Deliverable: design + decisione
> architetturale, **non** codice di feature. Le fasi realizzative sono le issue
> figlie **#172–#187** (backlog in fondo, §D7).

## 1. Problema

Il collo di bottiglia degli open data comunali **non è tecnologico**: quasi ogni
comune ha già un portale CKAN regionale e strumenti di pubblicazione. Mancano
competenze interne (RTD in condivisione, senza formazione sul dato), una
**politica open data**, la consapevolezza di *quali* dati aprire (molti **esistono
già** nei gestionali o negli adempimenti nazionali) e la percezione del valore.
Ne nasce il circolo vizioso **nessuna politica → nessun dato → nessun riuso →
nessun valore percepito → nessuna politica**.

Il progetto ha già i motori per *valutare e riusare* il dato esistente
(`maturity/`, `value/`, `landuse/`, Territorio, anello valore⇄maturità, Data
Quality Lab, convertitori, `opendata-monitor`). Manca il passo **a monte**:
aiutare un ente che parte da zero a **pianificare, produrre e mantenere** open
data di valore, usando l'AI per sostituire tempo e competenze mancanti — **senza
violare il pivot**: gli open data sono l'**unica fonte ufficiale**; niente
upload/override, niente KG come surrogato della fonte.

Le quattro domande a cui l'AI risponde per l'ente:

1. **Cosa** posso/devo aprire? (inventario del potenziale)
2. **In che ordine**, per massimizzare valore col minimo sforzo? (prioritizzazione)
3. **Come** lo produco conforme? (DCAT-AP_IT, HVD, licenza, privacy, qualità)
4. **Perché** conviene? (dimostrazione di valore per il territorio)

Pilota naturale: **Gioia del Colle (ISTAT 072021)**.

---

## D1 — Mappa "applicativi comunali → dataset candidati"

Intuizione centrale: **la maggior parte dei dati aperti di valore è già prodotta**
dai sistemi del comune e dagli adempimenti nazionali. Il comune non "crea" dati,
deve **estrarre, de-identificare e pubblicare** ciò che ha. La colonna
*già-aperto-altrove* è decisiva: dove il dato è già nazionale (BDAP, ANAC,
OpenCoesione/OpenPNRR) il comune **linka**, non riproduce.

| # | Sistema / adempimento | Dataset candidato | Categoria HVD | Già aperto altrove? | Privacy | Sforzo |
|---|---|---|---|---|---|---|
| 1 | Bilancio / contabilità | Entrate/uscite per capitolo | Statistica | ✅ BDAP/SIOPE → **linka** | Nessuna | Basso |
| 2 | Appalti / contratti (L.190) | Bandi, affidamenti, fornitori | — | ✅ ANAC → **linka** | Nessuna | Basso |
| 3 | PNRR / fondi | Progetti, avanzamento, importi | Statistica | ✅ OpenCoesione/OpenPNRR → **linka** | Nessuna | Basso |
| 4 | Anagrafe / ANPR | Popolazione per età/quartiere | Statistica | ⚠️ ISTAT come benchmark | **Solo aggregati** | Medio |
| 5 | Tributi (IMU/TARI) | Aggregati TARI per zona, tariffe | Statistica | ❌ | **Mai per contribuente** | Medio |
| 6 | SIT / cartografia (**PUG/PRG** #129) | Zonizzazione, toponomastica, civici | **Geospaziale** | ❌ (locale) | Bassa | Medio |
| 7 | Illuminazione / patrimonio | Punti luce, edifici pubblici, aree verdi | Geospaziale | ❌ | Nessuna | Basso |
| 8 | Rifiuti | % differenziata, calendario, isole ecologiche | Ambiente | ❌ | Nessuna | Basso |
| 9 | Mobilità / ZTL / sosta / TPL | Varchi ZTL, stalli, orari (**GTFS**) | **Mobilità** | ⚠️ (TPL a volte regionale) | Nessuna | Medio |
| 10 | Cultura / turismo | Eventi, POI, orari musei/biblioteche | — | ❌ | Nessuna | Basso |
| 11 | SUAP / SUE (edilizia, commercio) | Pratiche edilizie, esercizi, dehors | Geospaziale | ❌ | **De-identificare** | Alto |
| 12 | Ambiente | Qualità aria, meteo locale, aree a rischio | Ambiente/Meteo | ⚠️ ISPRA/meteo (connettori esistenti) | Nessuna | Medio |
| 13 | Protocollo / albo pretorio | Delibere/determine **come dati** (metadati) | — | ❌ | **Contenuto con cautela** | Alto |

Griglia di priorità: le 6 categorie **HVD (Reg. UE 2023/138)** — geospaziale,
mobilità, meteo, statistica, società/proprietà, osservazione della Terra/ambiente.
Il motore `maturity/hvd.py` già stima l'appartenenza HVD → riusabile per il ranking.

**Artefatto (D1, issue #172):** consolidare questa mappa come **YAML in-package**
(`opendata_backend/config_data/dataplan_catalog.yaml`, stile `config_data/`), una
voce per dataset candidato con: `fonte_interna`, `hvd`, `gia_aperto` (fonte
nazionale + connettore), `privacy` (famiglia + regola §D4), `sforzo`,
`sblocca` (analisi/lente/use-case che il dato abilita → §D2). Bozza dello schema:

```yaml
candidati:
  - id: rifiuti-differenziata
    nome: "Raccolta differenziata (% per anno/zona)"
    fonte_interna: "gestionale rifiuti / igiene urbana"
    hvd: ambiente
    gia_aperto: null            # non nazionale → il comune deve aprirlo
    privacy: nessuna
    sforzo: basso
    sblocca: ["lente ambiente", "report Territorio §ambiente"]
  - id: bilancio
    nome: "Bilancio (entrate/uscite per capitolo)"
    fonte_interna: "contabilità"
    hvd: statistica
    gia_aperto: { fonte: "BDAP/SIOPE", connettore: "bdap-mcp-server" }  # → linka
    privacy: nessuna
    sforzo: basso
    sblocca: []
```

---

## D2 — Modello di prioritizzazione valore×sforzo

Ordina i candidati su una **matrice valore×sforzo**; "alto valore, basso sforzo"
prima. Riusa i motori esistenti (no nuovi modelli di scoring):

- **Valore** = combinazione di:
  - `value/` (art. 14 Dir. UE 2019/1024 + combinabilità del dato);
  - `maturity/hvd.py` (appartenenza HVD → peso normativo);
  - **segnale di riuso reale già nel progetto**: un dataset che *sblocca un'analisi*
    (una lente Territorio, un use-case, l'anello valore⇄maturità come *domanda di
    riuso non soddisfatta*) pesa di più. Questo è il differenziatore: il valore è
    ancorato a un riuso **osservabile nella piattaforma**, non stimato in astratto.
- **Sforzo** = campo `sforzo` del catalogo D1 corretto da `gia_aperto` (se già
  nazionale → sforzo ≈ "solo link", massima priorità di quick-win) e dalla
  sensibilità privacy (de-identificazione = sforzo maggiore).

Output: ranking + **lotto "quick win"** (KPI del pilota, issue #187) = candidati
alto-valore/basso-sforzo, tipicamente: (a) i *link* agli adempimenti nazionali già
aperti; (b) i dataset geo/ambiente locali senza privacy. Deterministico e
spiegabile (i pesi sono iniettati, non nel motore puro). Issue realizzativa: **#173**.

---

## D3 — "Politica Open Data" e "Piano di pubblicazione" generati

Il pezzo che sostituisce le competenze mancanti del RTD. Due artefatti generati
(LLM per la prosa amministrativa, con **fallback offline deterministico** — R11):

**Politica Open Data dell'ente** (bozza di atto di indirizzo/delibera):
finalità, principi (dato aperto by-default, IODL 2.0 / CC-BY 4.0), ruoli e
responsabilità, licenza standard, riferimenti normativi (CAD, Linee guida AGID
open data, HVD Reg. UE 2023/138).

**Piano di pubblicazione**: tabella dei dataset prioritizzati (§D2) con, per
ciascuno: ufficio responsabile (§D10/#181), cadenza di aggiornamento, licenza,
**template di metadati DCAT-AP_IT precompilato** (riuso `quality/dcat.py`,
`generate_dcat`), e l'analisi che sblocca (§D2). Allineamento alle Linee guida
AGID e al paniere HVD. Issue realizzative: **#174** (+ #185 assorbe la guida
normativa come corpo dell'analisi).

---

## D4 — Vincoli privacy/GDPR

Checklist applicabile in fase di produzione (§D5.5), **per famiglia di dato**.
Principio: open data = **solo aggregati/de-identificati**; mai dati personali.

| Famiglia | Regola di de-identificazione | Soglia di aggregazione |
|---|---|---|
| Tributi (IMU/TARI) | Mai per contribuente/immobile; solo totali/medie per zona | ≥ *k* unità per cella (default k=5); no zone con 1 contribuente |
| Anagrafe/ANPR | Solo conteggi per classi (età, quartiere); no nominativi/indirizzi | Sopprimere/arrotondare celle < k; classi d'età ≥ 5 anni |
| Edilizia/SUE, SUAP | Rimuovere richiedente/PII; tenere dato territoriale (zona, tipo) | Aggregare esercizi per via/zona quando il puntuale identifica una persona |
| Atti/protocollo | Pubblicare metadati; contenuto solo se già pubblico (albo) | — (revisione umana obbligatoria) |
| Geo/patrimonio/rifiuti/mobilità | Nessun PII → pubblicabile puntuale | — |

Regole trasversali: no *quasi-identificatori* incrociabili (data di nascita +
CAP + genere); rispetto delle soglie ISTAT per micro-dati; **revisione umana**
sui dati a rischio prima della pubblicazione. L'AI **propone** i caveat, non
decide da sola sui casi sensibili. Issue realizzativa: **#175**.

---

## D5 — Design tecnico (decisione architetturale)

**Decisione: nuovo motore puro `opendata_core/dataplan/`** (non estensione di
`maturity/`). Motivazione: la pianificazione ha un dominio proprio (catalogo
candidati, prioritizzazione, politica/piano) distinto dalla *valutazione* di
maturità; mescolarli confonderebbe `assess_entity`. `dataplan/` **riusa** i motori
esistenti per iniezione, senza duplicarli. Coerente con la Capability Layer.

```
opendata_core/dataplan/          # motore PURO (no FastAPI/LLM/DB)
  catalog.py    # carica il catalogo D1 (iniettato dal backend), tipi
  prioritize.py # matrice valore×sforzo (D2) — pesi/segnali iniettati
  policy.py     # struttura Politica + Piano (D3), template DCAT iniettati
  privacy.py    # checklist GDPR per famiglia (D4)
opendata_backend/
  routers/dataplan.py            # GET /dataplan/{istat}/diagnosi|inventario|
                                 #     piano|politica  — auth + rate-limit
  dataplan/service.py            # orchestrazione: harvest + adempimenti nazionali,
                                 #     iniezione catalogo/pesi/LLM, persistenza
config_data/dataplan_catalog.yaml # artefatto D1 (in-package)
```

**Le 7 funzioni del Copilota** (tutte fail-safe, fonti sempre interrogabili):

1. **Diagnosi a costo zero** — da codice ISTAT: (a) censisce il *già pubblicato*
   sul portale regionale (riuso `maturity/harvest.py` + `assess_entity` → 4
   dimensioni ODM); (b) sonda gli adempimenti nazionali già aperti (BDAP/SIOPE via
   `bdap-mcp-server`, ANAC via CKAN generico, OpenCoesione/OpenPNRR via i
   rispettivi connettori, ISTAT come benchmark). Output: "quanto sei aperto oggi"
   + baseline maturità.
2. **Inventario del potenziale** — catalogo D1 → candidati con fonte, HVD, privacy,
   sforzo, già-aperto-altrove.
3. **Prioritizzazione** (§D2) — ranking valore×sforzo.
4. **Politica + Piano** (§D3) — generati, con template DCAT-AP_IT precompilati.
5. **Produzione assistita** — dato l'estratto grezzo (CSV/XLSX/SHP) **riusa i
   convertitori #101 e il Data Quality Lab**: schema, tipizzazione, geocodifica,
   qualità ISO 25012, **check privacy §D4**. L'AI **non** custodisce il dato: il
   dato pubblicato vive sul portale ufficiale.
6. **Dimostrazione di valore** — per ogni dataset pubblicato mostra *quale analisi
   si sblocca* (report Territorio, una lente, un use-case). Riuso diretto
   dell'**anello valore⇄maturità (Fase 5)** e del segnale "domanda di riuso non
   soddisfatta". Il PUG (#129) è l'esempio: pubblicarlo alza la confidenza della
   riconciliazione OSM↔suolo.
7. **Mantenimento** — il piano diventa watch di `opendata-monitor` (#88/#103):
   freshness, qualità, link, regressioni di maturità, notifica opt-in al RTD.

**Punti di iniezione LLM (R11, `resolve_provider`, sempre con fallback offline):**
classificazione semantica dei candidati, mappatura applicativo→dataset, redazione
policy/piano in linguaggio amministrativo, spiegazione del valore, proposta di
schema/metadati, redazione dei caveat privacy. **Motori puri (no LLM):** scoring
maturità/valore, stima HVD, qualità ISO 25012, prioritizzazione → decisione
spiegabile e riproducibile. **Mai l'AI:** inventare un dato assente (→ diventa
*raccomandazione di apertura*) o custodire copie non ufficiali.

**Warehouse:** baseline e piani in `opendata.*` (`entities`,
`maturity_assessments`, `territory_reports`, eventuale `dataplan_*`), DDL
dialect-aware (R4). Issue realizzativa del design tecnico: **#176**.

---

## D6 — Feasibility export dai gestionali

Vendor tipici: Maggioli, Halley, PA Digitale, Dedagroup, Sicraweb, … L'export
strutturato dai gestionali locali è **eterogeneo e spesso manuale**. Strategia
raccomandata: **prima gli adempimenti nazionali già digitali** (BDAP, ANAC,
OpenCoesione/OpenPNRR, ANPR/ISTAT), dove il dato è già strutturato e nazionale →
quick-win immediati con sforzo minimo; **poi** i dati geo/ambiente/patrimonio
locali (export CSV/SHP realistico); **infine** i gestionali con export difficile
o dati sensibili (tributi, edilizia). L'implementazione dei connettori di export
per singolo vendor è **fuori scope** dell'analisi (issue: **#177**, con la base di
conoscenza per-vendor #182 e l'"export brief" operativo #180).

---

## D7 — Backlog delle fasi (issue figlie)

Le fasi realizzative sono tracciate come **sub-issue di #170** (già create):

| Issue | Deliverable |
|---|---|
| #172 | D1 — catalogo YAML `applicativi → dataset candidati` |
| #173 | D2 — modello prioritizzazione valore×sforzo |
| #174 | D3 — struttura Politica + Piano generati |
| #175 | D4 — regole privacy/GDPR per famiglia |
| #176 | D5 — design tecnico `dataplan/` + endpoint + UI |
| #177 | D6 — feasibility export gestionali |
| #178 | D7 — meta: backlog & tracciamento |
| #179 | D8 — piano dati dimostrativo Gioia del Colle |
| #180 | D9 — "export brief" per dataset (istruzione operativa) |
| #181 | D10 — routing dataset → ufficio → ruolo |
| #182 | D11 — KB "dove vive il dato nel gestionale" (per-vendor) |
| #183 | D12 — loop di raffinamento qualità → export brief |
| #184 | D13 — accompagnamento attivo (stati zero→maturo) |
| #185 | D14 — assorbire la guida normativa nell'analisi |
| #186 | D15 — scope pubblicazione su CKAN via write API (gate umano) |
| #187 | D16 — KPI pilota Gioia del Colle + lotto quick-win |

Ordine consigliato di realizzazione: **#172 → #173 → #176** (fondamenta:
catalogo, prioritizzazione, motore) → **#174/#175** (policy+privacy) →
**#179/#187** (validazione sul pilota) → il resto come raffinamenti.

---

## D8 — Piano dati dimostrativo: Gioia del Colle (072021)

Applicazione end-to-end del percorso (su carta, come validazione del design):

**1. Diagnosi.** Portale regionale `dati.puglia.it` (org `comune-di-gioia-del-colle`)
→ `assess_entity` (baseline ODM). Adempimenti già aperti rilevati: bilancio
(BDAP), appalti (ANAC), progetti PNRR/coesione (OpenPNRR/OpenCoesione).

**2–3. Inventario + prioritizzazione (lotto quick-win proposto):**

| Priorità | Dataset | Perché (valore) | Sforzo |
|---|---|---|---|
| 1 | **Link** a bilancio (BDAP), appalti (ANAC), PNRR (OpenPNRR) | Trasparenza immediata, zero produzione | Solo link |
| 2 | Raccolta differenziata (% per anno) | HVD ambiente; sblocca lente ambiente | Basso |
| 3 | Punti luce / aree verdi / patrimonio | HVD geospaziale; mappe di riuso | Basso |
| 4 | **PUG/PRG** (zonizzazione) #129 | Sblocca la riconciliazione OSM↔suolo (confidenza ↑) | Medio |
| 5 | Esercizi commerciali (de-identificati) | Alto valore territoriale; lente commercio | Medio |

**4. Politica + Piano.** Bozza di delibera (IODL 2.0) + piano con cadenze e
metadati DCAT-AP_IT precompilati per i 5 dataset.

**5. Produzione.** Es. differenziata: estratto CSV → Data Quality Lab (fix,
schema, ISO 25012) → nessun PII → pronto per il portale.

**6. Valore.** Pubblicare il PUG alza la confidenza del nodo suolo nel report
Territorio; la differenziata popola la lente ambiente. Ogni pubblicazione chiude
un item di "domanda di riuso non soddisfatta".

**7. Mantenimento.** I 5 dataset diventano watch di `opendata-monitor` (freshness
+ qualità + regressioni maturità), con notifica al RTD.

KPI pilota (#187): n. dataset del lotto quick-win pubblicati, Δ punteggio maturità,
n. item "domanda di riuso" chiusi, n. analisi sbloccate.

---

## Coerenza con l'esistente, pivot e regole

- **Riuso, non riscrittura:** `maturity/` (`assess_entity`, `harvest`, `hvd`),
  `value/`, `landuse/`, connettori (bdap/anac-via-ckan/opencoesione/openpnrr,
  meteo/gtfs/wikidata), Data Quality Lab + convertitori (#101/#157),
  `opendata-monitor` (#88/#103).
- **Pivot rispettato:** gli open data sono l'unica fonte ufficiale; il Copilota
  **non** diventa repository dei dati del comune (niente upload/KG surrogato); i
  dataset mancanti sono già modellati come *domanda di riuso non soddisfatta* →
  questa analisi li rende **azionabili**.
- **Regole operative:** R11 (ogni chiamata LLM via `resolve_provider` + fallback
  offline), R4 (schema `opendata`, DDL dialect-aware), R14 (alla realizzazione:
  README + copy UI + diagramma del percorso).

## Fuori scope (di questa analisi)

- Connettori di export dai singoli gestionali proprietari (→ #177/#182).
- Qualunque storage/override dei dati del comune fuori dal portale ufficiale.
- Scrittura automatica sul portale CKAN (valutata separatamente in #186, con gate
  umano; qui ci si ferma a *piano + dataset pronto da caricare*).

## Riferimenti

- Pivot: open data unica fonte ufficiale; il riuso si registra come *domanda*.
- Anello valore⇄maturità (Fase 5); `reuse_demand_penalty` su Impact.
- #129 (PUG come fonte interrogabile) — caso particolare generalizzato qui.
- #154 (OpenPNRR), #147 (catasto/OMI), #102 (stima HVD per file), #101/#157
  (convertitori), #88/#103 (monitoraggio + regressioni).
- Motori: `opendata_core/{maturity,value,landuse}/`, `maturity/{harvest,hvd}.py`,
  `opencoesione/`. Standard: DCAT-AP_IT, Linee guida AGID open data, HVD Reg. UE
  2023/138, licenze IODL 2.0 / CC-BY 4.0, GDPR. Docs: `architettura.md`,
  `data-model.md`.
