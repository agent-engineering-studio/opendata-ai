# Sostenibilità e modello di business — OpenData AI

> Documento di analisi/proposta. I numeri (quote free, prezzi) sono **ipotesi di
> lavoro da tarare sui costi reali**, non impegni. Il billing **non è implementato**
> (vedi "Roadmap tecnica"): i piani a pagamento sono comunicati come "in arrivo".

## Obiettivo
Mantenere OpenData AI **aperto, indipendente e open source** coprendo i costi di
infrastruttura ed evitando che l'uso gratuito eroda risorse a carico personale di chi
sviluppa. Non è massimizzazione del profitto: l'obiettivo è la **sostenibilità** e il
reinvestimento nel bene comune (cultura del dato nelle PA, codice aperto).

## Driver di costo
1. **Modelli linguistici (Claude API)** — la voce che **scala con l'uso**. Ogni analisi
   `/programma` in modalità `completa` esegue più chiamate LLM (programma + idee +
   eventuale marketing) oltre alla `classify` (Haiku). È il costo marginale per richiesta.
2. **Infrastruttura** — VPS Aruba (oggi a **carico personale**), Postgres, Redis, i
   server MCP. Costo prevalentemente **fisso** mensile.
3. **Fonti esterne** — gratuite ma **rate-limited** (ISTAT esploradati ~5 query/min,
   Overpass pubblico, 8milaCensus, OpenCoesione): non costano denaro ma impongono
   prudenza nei volumi (mitigata dalla cache).

> Implicazione: il vincolo di costo NON è la req/min tecnica (60), ma il **numero di
> analisi LLM**. La cache analisi 24h (`programma_cache` + `_lens_cached`) ammortizza
> le richieste ripetute sullo stesso comune.

## Free limitato (contenere i costi)
Uso esplorativo gratuito ma con tetti pensati per il costo LLM:
- **Quota analisi** bassa (proposta: ~5–10 analisi `/programma` al mese per utente);
- limite tecnico **60 req/min** (già attivo, `shared/ratelimit.py`);
- **nessuna API key** (niente uso server-to-server/batch nel free);
- risultati serviti da **cache condivisa** quando disponibili (costo zero).

## Piani a pagamento (alzano i limiti) — *in arrivo*
| Piano | Pubblico | Cosa sblocca (proposta) |
|---|---|---|
| **Sostenitore** | singoli, hobby | quota analisi maggiore, badge sponsor |
| **Pro** | professionisti, giornalisti, dev | quota alta, **API key** dedicata, export avanzati, priorità |
| **Team/PA** | redazioni, enti | quota condivisa, più API key, supporto |

Prezzi da definire sul **costo medio per analisi** (token Claude) + margine di
sostenibilità per la quota fissa infrastruttura. Regola: una sottoscrizione deve
coprire almeno il costo LLM atteso del suo tetto di analisi.

## Altri ricavi (oltre gli abbonamenti)
- **Sponsor open source** — GitHub Sponsors / Open Collective, con riconoscimento
  pubblico (README, footer, pagina sostenibilità).
- **Bandi e convenzioni** — con associazioni e PA: deploy dedicati, affiancamento,
  formazione sulla cultura del dato. Allineati alla missione (educare le PA a
  valorizzare il patrimonio pubblico).
- **Servizi** — formazione/consulenza sulla maturità open data e sull'uso delle lenti
  territoriali.

## Sostenibilità
La combinazione **free limitato + abbonamenti + sponsor/bandi** mira a coprire:
- costo **variabile** (LLM) → principalmente abbonamenti (chi consuma paga);
- costo **fisso** (infra) → sponsor/convenzioni + quota base abbonamenti.
Break-even qualitativo: pochi abbonamenti Pro + 1–2 convenzioni PA coprono VPS + un
volume moderato di analisi. Da validare con i costi reali misurati in produzione.

## Roadmap tecnica del billing (FUORI SCOPE ora)
Nessuna di queste è implementata; il gancio esiste già nel codice:
- colonna `plan`/`tier` su `opendata.users` (oggi assente, `db/models.py`);
- **rate-limit per-plan** in `shared/ratelimit.py` (commento "per-plan limits … step 6+");
  oggi limite unico 60/min;
- quota analisi per-piano (contatore mensile su Redis/Postgres);
- `POST /api-keys/generate` (modello `ApiKey` già presente, endpoint "in arrivo");
- integrazione pagamenti: **Clerk Billing** (già usiamo Clerk per l'auth) oppure Stripe.

## Coerenza dei messaggi
Finché il billing non è attivo, ovunque (home, `login`, `/sostenibilita`,
`/docs/rate-limits`) i piani a pagamento vanno indicati come **"in arrivo"**, senza
promettere funzioni attive o addebiti.
