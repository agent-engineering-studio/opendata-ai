# A2A Tester — opendata-ai

Mini client **Next.js** per provare le skill A2A esposte dal backend OpenData AI
(`AgentCard` + JSON-RPC `SendMessage`). È un progetto **standalone** (non fa
parte dell'export statico della UI principale): usa route API server-side che
**proxano** la chiamata A2A, quindi non servono header CORS sul backend e il
bearer token resta lato server.

## Skill provate
- `search_open_data` — fan-out CKAN + SDMX, sintesi + risorse
- `find_geo_resources` — come sopra, bias geografico
- `classify_dataset` — classifica un dataset su una tassonomia (JSON)
- `assess_maturity` — scorecard di maturità ODM di un ente
- `analyze_territory` — SWOT + proposte per un comune (JSON)

## Avvio

```bash
cd examples/a2a-tester
cp .env.local.example .env.local      # imposta A2A_BACKEND_URL (es. http://localhost:8000)
npm install
npm run dev                           # http://localhost:3030
```

Poi nella UI:
1. (facoltativo) **Carica AgentCard** per vedere le skill pubblicate dal backend
   e selezionarle con un click.
2. Scegli la **skill**, edita il **messaggio** (testo per search/maturity, JSON
   per classify/territory) e premi **Invia**.
3. Vedi la **risposta** estratta dagli artifacts + il **JSON-RPC grezzo**.

## Note
- Il backend deve esporre A2A: AgentCard su `/.well-known/agent-card.json`
  (fallback `/.well-known/agent.json`), JSON-RPC su `/a2a/`.
- Se il backend gira con `AUTH_ENABLED=true`, inserisci un **Bearer** (JWT Clerk
  o API key `od_…`) nel form o in `A2A_BEARER`.
- L'envelope inviato è SDK 1.0 (`method: "SendMessage"`, `role: "ROLE_USER"`,
  `metadata.skill`), come in `/docs/a2a` della UI principale.
- Le analisi (`analyze_territory`) possono durare minuti: il proxy ha timeout
  alto (10 min).
