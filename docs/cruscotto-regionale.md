# Cruscotto regionale open data — analisi e design

> Deliverable dell'issue **#227**. `opendata-ai` evolve da piattaforma
> multi-regione a **cruscotto di monitoraggio di UNA regione** (fissata da
> `REGION`, #191), servendo tre personas. Documento di design + decisione
> architetturale + backlog. Riuso, non riscrittura.

## 1. Personas e viste

| Persona | Chi | Cosa vede |
|---|---|---|
| **Ente regionale** | RTD / ufficio open data della Regione | Vista d'insieme: maturità aggregata dei comuni, **dove intervenire**, copertura HVD regionale, classifica/mappa dei comuni, idee/proposte a livello regionale |
| **Comune** | RTD / ufficio del singolo comune | La sua parte: maturità, Territorio, Copilota/piano, idee comunali |
| **Cittadino / riuso** | giornalisti, sviluppatori, cittadini | Vista pubblica di trasparenza: stato open data della regione e dei comuni |

Un solo deployment, una sola regione. La persona seleziona la **vista**, non un
diverso backend.

## 2. Cosa c'è già (riuso)

- **Scoping regione** `REGION`/`regioni.yaml` (#191): ricerca, territorio,
  maturità, enforcement già filtrati sulla regione.
- **Maturità**: `build_ranking(entity_type, region)` (classifica enti per
  regione), scorecard ODM, peer comparison, indicatore PPTR regionale (#168).
- **Anagrafica comuni** `ComuneAnagrafica` (cod_regione + popolazione): elenco
  completo dei comuni della regione + peer group.
- **Valore** `value/portfolio(region=…)`. **Comunale**: Territorio, Copilota
  `/dataplan/*` (#170), Idea Lab. **Monitoraggio** `opendata-monitor`.

Il grosso dell'impianto esiste: **manca uno strato di aggregazione regionale +
una UI a tre viste.**

## 3. Cosa manca (nuovo strato regionale)

1. **Overview regionale** — aggregato di maturità di *tutti* i comuni: mediana,
   **distribuzione per stato** (zero_dati/pochi/in_crescita/maturo, riusa la
   macchina a stati #184), copertura HVD regionale, e **dove intervenire**
   (comuni + dimensioni ODM più deboli; comuni "zero dati" prioritari).
2. **Classifica/mappa dei comuni** della regione (leaderboard + copertura per
   provincia; mappa opzionale via confini OSM già usati in Territorio).
3. **Idee/proposte regionali** — aggregare la *domanda di riuso non soddisfatta*
   e i candidati Copilota di tutti i comuni in una **priorità regionale**: quali
   dataset, aperti da più comuni, sbloccherebbero più valore (es. "12 comuni su
   30 non hanno pubblicato i rifiuti → dataset regionale prioritario").
4. **Vista pubblica** di trasparenza (read-only, no PII).

## 4. Architettura (decisione)

Coerente con la Capability Layer: **motore puro** per l'aggregazione (calcoli
deterministici), **backend** per query al warehouse + LLM, **UI** a tre viste.

```
opendata_core/region/            # MOTORE PURO (no FastAPI/LLM/rete)
  aggregate.py   # da una lista di sintesi-comune → distribuzione per stato,
                 #   mediane, "dove intervenire", copertura HVD regionale
  models.py      # RegionOverview, ComuneSummary, InterventionHint

opendata_backend/region/
  service.py     # query warehouse: comuni della regione (ComuneAnagrafica) +
                 #   ultimi assessment (maturity) + domanda di riuso; iniezione
                 #   nel motore puro; narrativa LLM opzionale (R11)
  routers/region.py  # GET /regione/overview | comuni | idee | pubblico
```

**Perché un nuovo motore `region/` e non estendere `maturity/`:** l'aggregazione
regionale è una *lente d'insieme* che compone maturità + Copilota + territorio;
tenerla separata evita di gonfiare `maturity/` e la rende testabile in isolamento
con dati iniettati.

### Endpoint (contratto proposto)

Tutti scoped su `REGION` (già in Settings); autenticati + rate-limited.

| Metodo | Path | Cosa |
|---|---|---|
| GET | `/regione/overview` | KPI regionali: n. comuni, distribuzione per stato, mediana ODM, copertura HVD, **dove intervenire** (top comuni/dimensioni deboli) |
| GET | `/regione/comuni` | classifica dei comuni (nome, popolazione, stato, overall, trend), filtrabile per provincia |
| GET | `/regione/idee` | proposte regionali: dataset più richiesti/mancanti tra i comuni (aggrega domanda di riuso + Copilota) |
| GET | `/regione/pubblico` | sottoinsieme read-only per la trasparenza (no dettagli sensibili) |

Forma `RegionOverview` (bozza):
```jsonc
{
  "regione": "Puglia", "cod_regione": "16",
  "comuni_totali": 257, "comuni_valutati": 40,
  "distribuzione_stato": {"zero_dati": 180, "pochi_dati": 50, "in_crescita": 22, "maturo": 5},
  "mediana_overall": 34.0,
  "hvd_copertura": {"geospatial": 0.4, "mobility": 0.1, ...},
  "dove_intervenire": [
    {"tipo": "comune", "istat": "072021", "nome": "Gioia del Colle", "overall": 12, "motivo": "zero dati"},
    {"tipo": "dimensione", "dimensione": "policy", "mediana": 18, "motivo": "policy debole in regione"}
  ]
}
```

### Personas → viste (auth)

- **Comune** e **Ente regionale** sono utenti autenticati (Clerk): la differenza
  è la **vista** (`/regione/*` vs le pagine comunali già esistenti). Un semplice
  ruolo/claim (`role=regione|comune`) o una selezione in UI instrada; il backend
  resta lo stesso, scoped su `REGION`. RBAC fine: valutare `clerk-orgs` in fase
  realizzativa (fuori scope dell'analisi).
- **Pubblico**: `/regione/pubblico` read-only. Coerente con R7 (nessun endpoint
  anonimo oltre `/health`): la vista pubblica è servita via un endpoint dedicato
  con dati già aggregati/non sensibili, o pubblicata come snapshot statico.

### LLM + persistenza

- **LLM (R11, fallback offline):** narrativa regionale ("lo stato degli open data
  in <regione>"), spiegazione del "dove intervenire". Mai per i numeri.
- **Persistenza (R4):** snapshot regionali append-only (riuso del pattern
  `dataplan_plans`/civic snapshots) per il trend regionale nel tempo.

## 5. UI (tre viste)

- **`/regione`** — landing cruscotto (persona ente regionale): KPI + distribuzione
  stati + "dove intervenire" + classifica comuni + idee regionali. Drill-down a un
  comune → riusa le pagine esistenti (`/maturita`, `/territorio`, `/copilota`).
- **Comune**: pagine già esistenti, contestualizzate al comune scelto.
- **Pubblico**: versione ridotta/embeddabile del cruscotto (trasparenza).
- **Titolo esplicativo globale** «Cruscotto Open Data · Regione …» in testata su
  ogni pagina (componente `RegioneTitle`, env `NEXT_PUBLIC_REGION_NAME`, coerente
  con `REGION` del backend): dev'essere sempre chiaro *quale* regione si sta
  monitorando. Il badge runtime «Regione: …» di `/territorio` (#191) resta per il
  dettaglio province.
- R14: README + copy + diagramma alla realizzazione.

## 6. Fasi / backlog (sotto-issue)

1. **F1 — Motore aggregazione** `opendata_core/region/` (distribuzione stati,
   mediane, dove-intervenire, copertura HVD) + test. *(puro, no dipendenze)* — **#228**
2. **F2 — Backend overview** `/regione/overview` + `/regione/comuni` (query
   `ComuneAnagrafica` + assessment; iniezione nel motore). Test. — **#229**
3. **F3 — Idee regionali** `/regione/idee` (aggrega domanda di riuso + candidati
   Copilota per comune → priorità regionale). — **#230**
4. **F4 — UI cruscotto** `/regione` (vista ente regionale) + drill-down. — **#231**
5. **F5 — Vista pubblica** `/regione/pubblico` + eventuale export statico. — **#232**
6. **F6 — Trend regionale** (snapshot append-only) + narrativa LLM. — **#233**

Ordine consigliato: F1 → F2 → F3 → F4 → F5 → F6.

Dipendenza dai residui Copilota: **#180/#181/#182/#183** (lato produzione
comunale) restano utili e complementari; **#186** (scrittura CKAN) resta **fuori
scope** del cruscotto di monitoraggio.

## 6-bis. Auth & sicurezza per il self-hosting (proposta, da confermare)

Il progetto è **open source**: ogni Regione lo ospita sulla **propria**
infrastruttura. Clerk (SaaS US) spesso **non è conforme** alle policy di un ente
pubblico → l'auth deve essere **self-hostable e standard**.

**Buona notizia — il backend è già OIDC standard**, non Clerk-proprietario:
`auth/clerk.py::verify_clerk_token` verifica i JWT via JWKS
`${issuer}/.well-known/jwks.json` (RS256, `iss`/`exp`/`sub`). Di Clerk-specifico
restano solo i *nomi* (`ClerkUser`, `clerk_jwt_issuer`, colonna `clerk_user_id`),
l'assenza del check `aud`, le chiavi Backend-API/webhook, e sul **frontend**
`@clerk/nextjs`. Puntando l'issuer a un **Keycloak** self-hosted il backend ne
verifica già i token: il vero coupling Clerk è il frontend.

### Direzione proposta

1. **Auth → OIDC neutrale.** Rinominare `CLERK_*` → `OIDC_*` (con **alias**
   retro-compatibili), rendere il check `aud` **opzionale**, documentare
   **Keycloak/Authentik** come IdP di riferimento self-hosted. Clerk resta *uno*
   degli issuer possibili, non più obbligatorio. Sul frontend sostituire
   `@clerk/nextjs` con un client OIDC generico (Auth.js / `oidc-client-ts` PKCE).
   `AUTH_ENABLED=false` resta per dev/self-host minimale.
2. **Vista pubblica cittadino** (persona #3): **sola lettura, nessun dato
   personale → nessun login**, quindi niente SPID/CIE ora. Se un domani serve,
   SPID/CIE entra come un altro issuer OIDC via bridge, senza toccare il resto.
3. **Rate limit → baseline per-IP/globale.** Il limite per-utente esiste già
   (`shared/ratelimit.py`, 60/min + override per tier) ma è no-op senza Redis e
   non copre il traffico non autenticato. Aggiungere un **middleware per-IP e
   globale** con **fallback in-process** (token bucket) quando Redis manca, sopra
   il limite per-utente. Così protegge anche gli endpoint pubblici e regge senza
   Redis.

> Impatto su R7/CLAUDE.md: Clerk oggi è *pinnato* come dipendenza. Con questa
> direzione Clerk diventa uno degli issuer OIDC supportati; R7 va aggiornata alla
> realizzazione (dev-bypass invariato, verifica JWT via JWKS di *qualsiasi*
> issuer).

## 7. Coerenza con il pivot e le regole

- **Pivot**: open data unica fonte ufficiale; il cruscotto **monitora e orienta**,
  non pubblica al posto dell'ente (niente upload/KG surrogato). I mancanti sono
  *domanda di riuso* aggregata a livello regionale.
- **Regole**: R11 (LLM via `resolve_provider` + fallback), R4 (schema `opendata`,
  DDL dialect-aware), R7 (auth), R8 (CORS), R14 (docs con la feature).

## Riferimenti

- Scoping regione: #191 (`REGION`, `regioni.yaml`). Maturità: `build_ranking`,
  #168. Copilota: `docs/copilota-open-data.md` (#170). Territorio, Idea Lab,
  `opendata-monitor`. Docs: `architettura.md`, `data-model.md`.
