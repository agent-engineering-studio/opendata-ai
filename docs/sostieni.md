# Sostieni il progetto — modello di business OpenData AI

> Documento di analisi/proposta. I prezzi sono **calibrati sul costo reale
> dell'infrastruttura** ma restano ipotesi di lavoro da validare. La pagina
> pubblica è `/sostieni` (ex `/sostenibilita`). I prodotti Stripe sono creati
> in **modalità test**; il go-live richiede di ripubblicare i Payment Link live.

## Idea di business

OpenData AI resta **gratuito da esplorare e open source**. Il modello non punta
al profitto ma alla **sostenibilità**: coprire i costi ed evitare che l'uso
gratuito eroda risorse a carico personale di chi sviluppa. Il messaggio è
sempre **a favore del sostegno**, con un **contributo mensile a misura delle
esigenze** di chi usa il servizio, esplicitamente **calibrato sul costo
dell'infrastruttura**.

## Driver di costo

1. **Modelli linguistici (Claude API)** — costo **variabile** che scala con
   l'uso. Ogni analisi `/programma` completa esegue più chiamate LLM
   (programma + idee + marketing) oltre alla `classify` (Haiku).
2. **Infrastruttura** — VPS Aruba Docker, Postgres, Redis, server MCP. Costo
   **fisso** mensile. Baseline di riferimento: piano **O8A16** (8 vCPU / 16 GB /
   160 GB / 100 TB) a **€19,89 + IVA ≈ €24,3/mese** — profilo con margine per
   cache e picchi sullo stack completo (backend + 3 MCP + frontend + Postgres +
   Redis). Fonte: <https://www.cloud.it/vps/docker/>.
3. **Fonti esterne** — gratuite ma rate-limited (ISTAT, Overpass, 8milaCensus,
   OpenCoesione): non costano denaro ma impongono prudenza nei volumi (cache).

## Contributi mensili (calibrati su ~€24/mese infra)

Tre livelli pensati sul costo reale. La logica: **un contributo Pro copre quasi
da solo il server**; i contributi Sostenitore aggregati coprono la quota fissa;
Team/PA copre anche parte del costo LLM variabile.

| Prodotto | Prezzo | Pubblico | Sblocca | Copertura costo |
|---|---|---|---|---|
| **Sostenitore — Caffè mensile** | €8/mese | singoli, hobby | quota analisi maggiore, badge sostenitore | una fetta del server |
| **Pro — Uso intensivo** | €19/mese | professionisti, giornalisti, dev | quota alta, **API key** dedicata, export avanzati, priorità | quasi l'intero server |
| **Team / PA — Enti e redazioni** | €39/mese | redazioni, associazioni, PA | quota condivisa, più API key, supporto prioritario | server + parte del costo LLM |

Regola di calibrazione: ogni sottoscrizione deve coprire **almeno il costo LLM
atteso del suo tetto di analisi** + una quota della spesa fissa infrastruttura.

## Costo LLM: Claude API vs container Ollama CPU su VPS

> Stime parametriche da validare in produzione. Pricing Claude (per milione di
> token, giu 2026): **Opus 4.8** $5 in / $25 out · **Sonnet 4.6** $3 / $15 ·
> **Haiku 4.5** $1 / $5. Prompt caching: scrittura 1,25× (TTL 5 min) / 2× (1h),
> **lettura 0,1×**. Batch −50% (ma `/programma` è sincrono → non applicabile).

### Costo per analisi `completa` con Claude (variabile)

Una `/programma completa` esegue più chiamate: fan-out fonti (CKAN/ISTAT [+EU/OECD]
con tool MCP) → lenti → **sintesi** (output cap 8192) → **idee** (4 generatori) →
eventuale **marketing** → `classify` (Haiku, 3-layer cache). Stima mid (senza
marketing): ~55k token input, ~19k output.

| Modello sintesi | Costo/analisi (no cache) | Con prompt caching¹ |
|---|---|---|
| **Haiku 4.5** | ~$0,15 | ~$0,12 |
| **Sonnet 4.6** | ~$0,45 | ~$0,30 |
| **Opus 4.8** | ~$0,75 | ~$0,55 |

¹ Le istruzioni di sistema (CKAN/ISTAT/EUROSTAT/OECD_INSTRUCTIONS) sono prefisso
stabile → cacheabili: la lettura costa 0,1× e abbatte ~40% l'input ripetuto.
`classify` è già bounded (Haiku + Redis 24h + `opendata.classifications`).

**Implicazione costo→contributo**: a ~**€0,30–0,50/analisi** (Sonnet + cache), un
contributo **Sostenitore €8** copre ~16–25 analisi/mese; **Pro €19** ~40–60.
Coerente con i tetti del free (~5–10 analisi/mese) e con la regola di
calibrazione: chi consuma molto paga il proprio costo LLM.

### Ollama CPU su VPS (fisso, ma non sostitutivo)

L'immagine Ollama del progetto è tarata su **qwen2.5:32k** (32B), pensata per il
profilo **GPU** (`make up-gpu`). Su **CPU** il quadro cambia radicalmente:

- **Latenza**: un 32B su 8 vCPU rende ~1–3 token/s → una sintesi da 8k token
  richiede **~45–130 minuti**. Inutilizzabile sul percorso interattivo. Anche un
  7B quantizzato (~6–12 tok/s) resta sui **10–20 minuti/analisi**.
- **RAM**: con tutto lo stack acceso (Postgres, Redis, 3 MCP, backend, frontend),
  un 7–14B richiede di salire almeno a **O16A32** (€38,90+IVA ≈ **€47/mese**) —
  costo **fisso** a prescindere dall'uso.
- **Qualità/contratto**: un 7–14B locale è materialmente meno affidabile sul
  ragionamento multi-fonte e soprattutto sul **contratto `<!--RESOURCES_JSON-->`**
  (R5) — rischio output rotti.

**Break-even teorico ma fuorviante**: l'uplift VPS per l'inferenza CPU (≈ +€23/mese
vs baseline O8A16) "ripagherebbe" Claude a ~50–75 analisi/mese, **ma solo a parità
di qualità e latenza** — che non c'è. L'inferenza CPU è 20–130× più lenta e meno
accurata: non è un sostituto del synth interattivo, è una falsa economia.

### Raccomandazione

- **Synth/idee/marketing → Claude** (provider `auto` → `claude`): qualità + latenza
  accettabile grazie allo **streaming token** già implementato. Il costo variabile
  si finanzia con i contributi (è la calibrazione sopra). Per ottimizzare:
  Sonnet 4.6 come default synth + prompt caching aggressivo sulle istruzioni.
- **Ollama-CPU**: tenerlo solo come **fallback offline/cost-cap** per i task più
  leggeri e **fuori dal percorso interattivo**, accettando UX degradata. Per
  l'inferenza locale latency-viable servirebbe una **GPU**, il cui costo supera sia
  il baseline €24 sia la spesa Claude attesa a questi volumi.
- `classify` resta su **Haiku** (già economico e cache-bounded): nessun vantaggio a
  spostarlo su Ollama.

## Costo LLM: Claude API vs Ollama Cloud

> Ollama Cloud (giu 2026): **Free** $0 (1 modello cloud concorrente, uso leggero),
> **Pro** $20/mese ≈ €18,5 (3 concorrenti, "50× il Free"), **Max** $100/mese ≈ €92
> (10 concorrenti, "5× Pro"). **Non si paga a token**: l'utilizzo è misurato sul
> **tempo GPU** con finestre a reset (5h sessione / 7 giorni), per "livello" modello
> (1 leggero → 4 pesante). Modelli cloud forti disponibili: `gpt-oss:20b/120b`,
> `qwen3-coder:480b`, `deepseek-v3.1:671b`, `glm-4.6`, `kimi-k2`. Accesso via CLI/API.

Rispetto a Ollama-CPU su VPS, il Cloud gira su **GPU gestite**: latenza accettabile e
modelli grandi (120B–671B) → qualità molto superiore al 7B locale. È la vera
alternativa "open" a Claude.

### Modello di costo: variabile (Claude) vs fisso a quota (Ollama Cloud)

| | Claude API | Ollama Cloud |
|---|---|---|
| **Struttura** | puramente **variabile** (per token) | **fisso** mensile + tetto a quota GPU |
| **Costo tipico** | ~€0,30–0,50 / analisi (Sonnet+cache) | €18,5 (Pro) o €92 (Max) /mese |
| **Marginale per analisi** | proporzionale all'uso | ~€0 finché entro la quota |
| **Cliff** | nessuno (paghi quel che usi) | **throttling** a quota esaurita |
| **Concorrenza** | alta | **3 (Pro) / 10 (Max)** modelli simultanei |
| **Qualità / contratto JSON** | top (Opus/Sonnet) | buona ma da validare su `RESOURCES_JSON` (R5) |
| **Integrazione** | provider `claude` (già attivo) | provider `ollama` verso endpoint cloud + tag `*-cloud` (riusa il path esistente) |

### Break-even

A ~**€0,40/analisi** Sonnet:

- **Ollama Cloud Pro €18,5/mese** ripaga a ~**46 analisi/mese** (~1,5/giorno).
- **Ollama Cloud Max €92/mese** ripaga a ~**230 analisi/mese**.

Sotto la soglia → **Claude pay-as-you-go** costa meno **ed** è più affidabile
(qualità + contratto). Sopra la soglia → l'abbonamento flat vince sul costo, **se**
si resta dentro quota e i limiti di concorrenza non strozzano il fan-out.

### Rischi specifici di Ollama Cloud per questo progetto

1. **Concorrenza 3 (Pro)**: l'orchestratore fa fan-out su CKAN/ISTAT[+EU/OECD] e
   **4 generatori di idee** in parallelo → 3 slot possono diventare collo di
   bottiglia (serve Max, o tenere Claude sul fan-out).
2. **Quota a tempo-GPU opaca**: difficile prevedere quante analisi `completa`
   entrano nella finestra → rischio cliff a metà mese.
3. **Contratto `RESOURCES_JSON`**: da validare su `gpt-oss:120b`/`qwen3-coder:480b`
   prima di metterlo sul percorso interattivo (rischio R5 minore del 7B ma non nullo).

### Raccomandazione

- **Allineamento col modello a contributi**: Ollama Cloud trasforma il costo LLM da
  **variabile a fisso** (€18,5–92/mese). Sommato al VPS (~€24) dà un fisso totale
  ~€42–116/mese, coperto da **poche sottoscrizioni** → semplifica la narrazione
  "tieni vivo il progetto con un contributo mensile" e azzera il marginale per analisi.
- **Strategia consigliata (ibrida)**: Claude come **default qualità** sul synth
  interattivo finché i volumi sono bassi (pilota Gioia del Colle); introdurre
  **Ollama Cloud Pro come overflow/cost-cap** quando la spesa Claude mensile
  supererebbe i contributi incassati. A regime, se la validazione del contratto
  passa, Ollama Cloud può diventare il default e Claude il **fallback premium**
  (Pro/Team) o il motore del fan-out (dove la concorrenza Cloud limita).
- **Prerequisito**: test A/B su qualità sintesi + tenuta `RESOURCES_JSON` con un
  modello cloud, e misura di quante `completa` entrano nella quota Pro.

## Costo LLM: Claude API vs Azure AI Foundry

> Prezzi token Azure **rappresentativi** (Standard/serverless, per milione di token):
> GPT-4.1 ~$2 in / $8 out · GPT-4.1-mini ~$0,40 / $1,60 · GPT-4o ~$2,50 / $10 ·
> DeepSeek-V3/R1 ~$0,5–1,3 · modelli Claude **in** Foundry ≈ tariffe Anthropic
> (~Sonnet $3/$15). Verificare sul Pricing Calculator: variano per regione e versione.

Azure AI Foundry non è un singolo prezzo ma **tre modelli di deployment**:

| Deployment | Billing | Quando conviene |
|---|---|---|
| **Standard** (serverless) | **pay-per-token** | basso/medio volume, burst — come Claude API |
| **Provisioned Throughput (PTU)** | **$/PTU/h** fisso (sconti forti con Azure Reservation annuale) | alto volume **costante** in produzione |
| **Managed compute** | **$/ora** per GPU (SKU acceleratore) | modelli OSS/Hugging Face/NIM su GPU dedicata |

### Posizionamento costi

- **Standard (token)**: per analisi `completa` (~55k in / 19k out) un GPT-4.1 costa
  ~$0,11+$0,15 ≈ **$0,26/analisi**, GPT-4.1-mini ~**$0,05**; Claude-in-Foundry ≈
  Claude diretto (~€0,40). Cioè **paragonabile a Claude API**, ma con overhead Azure.
- **PTU**: il modello orario richiede di dimensionare **centinaia di PTU** per la
  capacità minima → costo dell'ordine di **migliaia di €/mese**: sovradimensionato
  per il pilota. Conviene solo con throughput alto e costante.
- **Managed compute**: GPU-hour come una GPU self-hosted → fisso elevato, non per
  questo volume.

### Il vero motivo per Azure: compliance PA, non costo

Il progetto è un verticale **PA**. Azure AI Foundry abilita ciò che né Claude diretto
né Ollama danno facilmente:

- **Residenza dati UE** (deployment *Data Zone* EU) e **data processing regionale**;
- conformità/certificazioni utili per la PA italiana (tenant Azure del comune,
  ACN/PSN, AgID), content filtering integrato;
- **deploy nel tenant Azure del committente** → monetizzabile come **convenzione**
  (tier Team/PA), non come costo del servizio pubblico.

Integrazione: il provider `azure_foundry` esiste già (`config.py` + `factory.py`),
ma il setup Azure (subscription, resource, deployment, quota) è più pesante di
Claude/Ollama Cloud.

## Sintesi: quattro opzioni LLM a confronto

| | **Claude API** | **Ollama CPU/VPS** | **Ollama Cloud** | **Azure AI Foundry** |
|---|---|---|---|---|
| **Costo** | variabile ~€0,40/analisi | fisso VPS grande (~€47) | fisso $20–100/mese | Standard ≈ Claude · PTU migliaia/mese |
| **Marginale/analisi** | proporzionale | ~€0 | ~€0 (entro quota) | proporzionale (Standard) |
| **Latenza** | buona (streaming) | **inaccettabile** (min) | buona (GPU) | buona |
| **Qualità** | **top** | bassa (7B) | alta (120–671B) | alta (GPT-4.1/Claude/DeepSeek) |
| **Contratto JSON (R5)** | affidabile | a rischio | da validare | affidabile (GPT-4.1/Claude) |
| **Setup** | minimo (attivo) | medio (VPS) | minimo | **pesante** (Azure) |
| **Compliance PA / dati UE** | no nativo | sì (self-host) | no | **sì (Data Zone EU)** |
| **Prevedibilità spesa** | bassa | alta | alta (con cliff) | alta (PTU) / bassa (Standard) |

**Lettura strategica**:
- **Pilota / basso volume** → **Claude API** (qualità + zero overhead + paghi l'uso).
- **Tetto di spesa prevedibile** a volume medio → **Ollama Cloud Pro** come
  overflow/cost-cap (costo LLM da variabile a fisso).
- **Convenzione PA con requisiti di residenza dati UE** → **Azure AI Foundry**
  (Data Zone), fatturato come servizio Team/PA, non come costo del servizio aperto.
- **Ollama-CPU**: escluso dal percorso interattivo (latenza).

Il modello a contributi resta agnostico al motore: copre il **costo variabile**
(Claude/Azure Standard) o il **fisso** (Ollama Cloud / convenzione Azure PA) a
seconda dell'opzione attiva.

## Catalogo Stripe

Prodotti + prezzi ricorrenti mensili (EUR) creati via Stripe MCP (modalità test):

- `OpenData AI — Sostenitore` → price €8/mese ricorrente
- `OpenData AI — Pro` → price €19/mese ricorrente
- `OpenData AI — Team / PA` → price €39/mese ricorrente

Per ciascun prezzo è creato un **Payment Link** Stripe-hosted: il frontend è
`output: 'export'` (statico, GitHub Pages) quindi non può ospitare un checkout
server-side. I Payment Link sono cablati nel blocco `CONTRIBUTI` di
`opendata-ai-ui/app/sostieni/page.tsx`.

### Risorse Stripe create (account `agentengineering`, **LIVE**, EUR/mese)

| Tier | Product ID | Price ID | Payment Link |
|---|---|---|---|
| Sostenitore €8 | `prod_UjbukNItNOQYLI` | `price_1Tk8hlJTWGUeNFIfEKKbvHAV` | `https://buy.stripe.com/fZu8wQ7Km4wY02O4oY3oA01` |
| Pro €19 | `prod_Ujbve2gZclCIH1` | `price_1Tk8hmJTWGUeNFIfShzmBade` | `https://buy.stripe.com/dRm28s5Ce6F602O3kU3oA02` |
| Team/PA €39 | `prod_UjbvTmmhD2ZYGy` | `price_1Tk8hnJTWGUeNFIffIrW5hnM` | `https://buy.stripe.com/3cIfZi4ya0gI5n85t23oA03` |

> **Nota go-live**: i Payment Link sono **live** ma incassano solo a pagina
> deployata. Prima del deploy valutare: webhook Stripe → sync stato abbonamento su
> `opendata.users` (vedi roadmap billing sotto), eventuale Tax/IVA, e collegamento
> contributo→privilegi (tier).

## Altri ricavi (oltre i contributi)

- **Sponsor open source** — GitHub Sponsors / Open Collective, riconoscimento
  pubblico (README, footer, pagina sostieni).
- **Bandi e convenzioni** — con associazioni e PA: deploy dedicati,
  affiancamento, formazione sulla cultura del dato.
- **Servizi** — formazione/consulenza su maturità open data e lenti territoriali.

## Roadmap tecnica del billing

I Payment Link rendono i contributi **incassabili da subito** senza backend. Il
collegamento contributo → privilegi è ora parzialmente cablato.

**Fatto:**
- colonna `opendata.users.subscription_tier` (migrazione `0010`) — già letta da
  `ClerkUser.subscription_tier` e `config.rate_limit_for(tier)`;
- colonna `opendata.users.stripe_customer_id` (migrazione `0011`) per mappare gli
  eventi Stripe (keyed per customer) all'utente locale;
- **webhook Stripe** `POST /webhooks/stripe` (`routers/webhooks.py`): verifica
  firma con `stripe.Webhook.construct_event`, gestisce
  `checkout.session.completed` (bind customer↔utente via `client_reference_id`
  o email) e `customer.subscription.created|updated|deleted` (set
  `subscription_tier` per customer). Endpoint backend dietro verifica firma,
  **non** una route Next.js (R6, `output: 'export'`). Mappa price→tier via
  `STRIPE_PRICE_TIERS` (`config.tier_for_price`).
- **binding robusto lato UI**: `components/SostieniButton.tsx` (client component)
  appende `?client_reference_id=<clerkUserId>` al Payment Link per gli utenti
  loggati, così il webhook lega il contributo all'utente senza dipendere dal
  match email né dall'ordine degli eventi Stripe. Guardia keyless come
  `DashboardGate`: build senza chiave Clerk → link semplice.

**Da fare (hardening + prodotto):**
- **idempotency** per `event.id` (oggi le scritture sono set-op idempotenti, ok
  per i retry, ma un dedup store evita lavoro doppio) e **IP allowlist** Stripe;
- **quota analisi per-piano** (contatore mensile su Redis/Postgres) oltre al
  `rate_limit_tiers` già presente;
- **IVA/Stripe Tax** se necessario;
- definire i valori `rate_limit_tiers` per `sostenitore`/`pro`/`team`.

## Coerenza dei messaggi

Ovunque (home, `login`, `/sostieni`, `/docs/rate-limits`) il tono è **a favore
del sostegno**: contributo mensile a misura delle esigenze, trasparenza sui
costi infra, nessuna promessa di funzioni di prodotto non ancora cablate al
billing.
