# opendata-ai

![OpenData AI — dal patrimonio di dati al valore per il territorio](docs/assets/hero.png)

Conversational + map-based access to **Italian and European open data
portals** through a single AI-powered backend. The user asks for
"electric-vehicle charging stations in Lombardy" and the platform fans the
query out across CKAN portals (`dati.gov.it`, regional / municipal CKAN
instances) and statistical providers (ISTAT, Eurostat, OECD via SDMX 2.1),
synthesises one answer, renders any geographic resources on a Leaflet+OSM
map, and optionally classifies the dataset against a caller-supplied
taxonomy with Claude Haiku.

> Static frontend on GitHub Pages, FastAPI backend on a self-hosted Aruba
> VPS, Clerk-authenticated everywhere except `/health`.

## Capability layer (valorizzazione + maturità)

Sopra l'accesso ai dati, la piattaforma offre un **capability layer** (Fasi 0–5):
maturità open-data degli enti (ODM 2025), valore del dato (art. 14 Dir. UE
2019/1024), modalità Territorio (profilo + investimenti OpenCoesione), use case
applicativi (ApriQui AI, PugliaTrip Brain), **sito civico** statico esportabile con
accountability di community, e un **anello valore⇄maturità** (i gap di dato
penalizzano l'Impact dell'ente). Diagramma e flussi: **`docs/architettura.md`**;
modello dati: **`docs/data-model.md`**. Pilota: Comune di Gioia del Colle.

### Maturità open data (modello ODM 2025)

![Maturità open data — scorecard ODM 2025 con radar delle 4 dimensioni e leve di miglioramento](docs/assets/maturita.png)

Scorecard 0–100 di un ente su quattro dimensioni — **Policy, Portale, Qualità,
Impatto** — con livello (Beginner → Follower → Fast-tracker → Trend-setter),
radar delle dimensioni e leve di miglioramento ordinate per impatto sul
punteggio. Sotto la soglia minima di dati dichiara *"dato insufficiente"*
invece di assegnare punteggi fuorvianti.

## Supported open data sources

| Source | Endpoint | What we fetch | Tool |
|---|---|---|---|
| **CKAN** (any portal) | `<portal>/api/3/action/*` | datasets, resources, file content (CSV/JSON/GeoJSON/TXT) | `ckan-mcp-server` (11 tools) |
| **ISTAT** | `esploradati.istat.it/SDMXWS/rest` | dataflows, DSDs, codelists, observations (SDMX-CSV) | `istat-mcp-server` (9 tools, agency `IT1`) |
| **Eurostat** *(opt-in)* | `ec.europa.eu/eurostat/api/dissemination/sdmx/2.1` | same as ISTAT | `istat-mcp-server` (agency `ESTAT`) |
| **OECD** *(opt-in)* | `sdmx.oecd.org/public/rest` | same as ISTAT | `istat-mcp-server` (agency `all`) |
| **OpenStreetMap** *(render-only)* | `nominatim/overpass/osrm` | renders GeoJSON layers into Leaflet HTML | `osm-mcp` |

Default portals for CKAN: the agent picks from an embedded list (`dati.gov.it`,
`data.gov.uk`, `data.gov`, `open.canada.ca`, `data.gov.au`, …). Override per
call via `base_url` in the chat payload or via `CKAN_DEFAULT_BASE_URL` env.

## MCP servers

Ogni fonte è un server **MCP** componibile (stdio o streamable-HTTP su `/mcp`),
usabile dal backend e da qualsiasi client MCP (Claude Desktop, Cursor, …). README
dedicato per ciascuno:

| Server | Cosa espone | README |
|---|---|---|
| **ckan-mcp-server** | Action API CKAN, `base_url` per-portale | [`ckan-mcp-server/README.md`](ckan-mcp-server/README.md) |
| **istat-mcp-server** | SDMX 2.1 — ISTAT · Eurostat · OECD | [`istat-mcp-server/README.md`](istat-mcp-server/README.md) |
| **osm-mcp** | Geocoding, POI, routing, zone + mappe Leaflet | [`osm-mcp/README.md`](osm-mcp/README.md) |
| **opencoesione-mcp-server** | Progetti coesione: finanziato vs speso | [`opencoesione-mcp-server/README.md`](opencoesione-mcp-server/README.md) |
| **ispra-mcp-server** | Rischio idrogeologico per comune (IdroGEO) | [`ispra-mcp-server/README.md`](ispra-mcp-server/README.md) |
| **maturity-mcp-server** | Scorecard maturità open data (ODM 2025) | [`maturity-mcp-server/README.md`](maturity-mcp-server/README.md) |
| **web-mcp** | Web search/fetch via SearXNG self-hosted | [`web-mcp/README.md`](web-mcp/README.md) |

> Materiale di comunicazione (descrizioni brevi + bozze post social) per i server
> MCP: **[`docs/mcp-social-kit.md`](docs/mcp-social-kit.md)**.

## Infrastructure

```
┌─────────────────────────┐                    ┌──────────────────────────────┐
│ GitHub Pages            │                    │ Aruba VPS — Caddy 2 (TLS)    │
│ opendata.<domain>       │  HTTPS+Clerk JWT   │                              │
│ Next.js 15 static export│ ─────────────────▶ │ opendata-backend (FastAPI)   │
└─────────────────────────┘                    │   • /datasets/{search,…}     │
                                               │   • /me/{favorites,history}  │
       │ login: Clerk app                      │   • /api-keys/generate       │
       │ app_3EMALiLi0UTULl89JPMKtaLENoy       │   • /datasets/classify       │
       │                                       │   • /webhooks/clerk (svix)   │
       ▼                                       │                              │
┌──────────────┐                               └──────────────┬───────────────┘
│ Clerk.com    │ ◀── webhooks ────────────────────────────────┘   │
└──────────────┘                                                  │ fan-out
                                                                  ▼
                                  ┌─────────────┬────────────┬────────────┐
                                  │ ckan-mcp    │ istat-mcp  │ osm-mcp    │
                                  │ (HTTP/MCP)  │ (HTTP/MCP) │ (HTTP/MCP) │
                                  └──────┬──────┴────────────┴────────────┘
                                         │
                       ┌─────────────────┴─────────────────┐
                       ▼                                   ▼
              ┌────────────────┐                  ┌────────────────┐
              │ Postgres 16    │                  │ Redis 7        │
              │ opendata.*     │                  │ db=1 cache+RL  │
              └────────────────┘                  └────────────────┘

                                ┌──────────────┐
                                │ Anthropic    │  Sonnet 4.6 (synth)
                                │ Claude API   │  Haiku 4.5 (classify)
                                └──────────────┘
```

| Component | Stack |
|---|---|
| Frontend | Next.js 15 (`output: 'export'`) → GitHub Pages, Leaflet map (KML/GeoJSON/GPX/SHP/WMS/ZIP/KMZ), Clerk `<ClerkProvider>` + `clerkMiddleware` |
| Auth | **Clerk** on every endpoint except `/health`; svix-signed webhook on `/webhooks/clerk` |
| Backend | FastAPI on Aruba VPS, dockerised, exposed at `https://api.opendata.<domain>` via Caddy + Let's Encrypt |
| MCP servers | `ckan-mcp-server`, `istat-mcp-server`, `osm-mcp` — same image speaks **stdio** (Claude Desktop) or **streamable-HTTP** (backend) |
| Database | Postgres 16 self-hosted, schema `opendata.*` (users / favorites / history / api_keys / classifications). Migrations owned by [agent-stack](vendor/agent-stack); local stub in `opendata-backend/migrations/` |
| Cache | Redis 7 logical db 1 — `od:fetch:*` 6h, `od:classify:*` 24h, `od:by-category:*` 5min, `od:ratelimit:*` 60s window |
| AI | Anthropic Claude. **Sonnet 4.6** for the synth aggregator; **Haiku 4.5** for the classify endpoint — cheaper task, smaller model |
| CI/CD | GitHub Actions — `ci.yml` (ruff + pytest + buildx), `docker-publish.yml` (multi-arch GHCR), `deploy-pages.yml` (frontend), `deploy-aruba.yml` (backend, tag-driven SSH) |

## Repository layout

| Path | Role |
|---|---|
| `opendata_core/` | Shared async clients (CKAN, SDMX, OSM render + Nominatim/Overpass/OSRM). Consumed by both the MCP wrappers and the backend |
| `ckan-mcp-server/` | FastMCP wrapper exposing 11 CKAN Action API tools |
| `istat-mcp-server/` | FastMCP wrapper for SDMX 2.1 — works for ISTAT/Eurostat/OECD via the `agency` arg |
| `osm-mcp/` | FastMCP wrapper that renders GeoJSON into self-contained Leaflet+OSM HTML |
| `opendata-backend/` | FastAPI app — routers (`datasets/me/api_keys/webhooks`), Clerk auth, Postgres ORM, Redis cache + rate limit, Claude classify |
| `opendata-ai-ui/` | Next.js 15 static-export frontend (Clerk + Leaflet) |
| `infra/aruba/` | Production compose + Caddyfile + bootstrap guide for the Aruba VPS |
| `infra/ollama/` | Optional baked Ollama image for local debug (qwen2.5:32k) |
| `vendor/agent-stack/` | Submodule with the canonical `opendata.*` Postgres migrations |
| `docs/claude-desktop.md` | How to plug the 3 MCP servers into Claude Desktop |
| `.clerk/config.md` | Clerk CLI setup recipe — pinned to app `app_3EMALiLi0UTULl89JPMKtaLENoy` |

## Endpoints

All endpoints (except `/health`) require authentication. Two credentials are
accepted interchangeably:

- **Clerk session JWT** — `Authorization: Bearer <jwt>`, used by the web UI.
- **API key** — `Authorization: Bearer od_…` or `X-API-Key: od_…`, for
  headless clients, scripts and agent integrations (see
  [Authentication & API keys](#authentication--api-keys)).

The same rule guards the A2A JSON-RPC endpoint (`/a2a/`); only the AgentCard
discovery (`/.well-known/agent-card.json`) is public.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | **Public** — used by health checks |
| POST | `/chat` | Back-compat alias of `/datasets/search` |
| POST | `/datasets/search` | Multi-source fan-out (CKAN + ISTAT [+ Eurostat + OECD]) |
| POST | `/datasets/by-category` | Same fan-out, scoped to a category. 5-min Redis cache |
| POST | `/datasets/fetch` | Direct resource download via shared CkanClient. 6h Redis cache |
| POST | `/datasets/classify` | Score a dataset against a taxonomy with Claude Haiku 4.5. 24h cache, durable on Postgres |
| GET / POST / DELETE | `/me/favorites[/{src}/{id}]` | Per-user dataset bookmarks |
| GET | `/me/history` | Search history per user |
| POST | `/api-keys/generate` | Create a programmatic API key — token returned once, persisted as SHA-256 |
| GET | `/api-keys` | List your keys (metadata only: name, created/last-used/revoked) |
| DELETE | `/api-keys/{id}` | Revoke one of your keys (soft-delete; 204 on success) |
| POST | `/webhooks/clerk` | svix-signed; upserts `opendata.users` on `user.{created,updated,deleted}` |
| POST | `/a2a/` | A2A JSON-RPC (authenticated). AgentCard at `/.well-known/agent-card.json` is public |

### `POST /datasets/search` — example

```bash
TOKEN=$(curl ... obtained from clerk)

curl -X POST https://api.opendata.example.com/datasets/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Stazioni di ricarica auto elettriche a Milano"}'
```

Response:
```json
{
  "text": "Ho trovato il dataset 'Stazioni di ricarica…'",
  "resources": [
    {
      "name": "stazioni_ricarica.csv",
      "url": "https://dati.comune.milano.it/.../stazioni_ricarica.csv",
      "format": "CSV",
      "source": "ckan",
      "content": "id,lat,lon,tipo_presa\n1,45.46,9.19,CCS\n…",
      "preview_html": "<html>…Leaflet map…</html>"
    }
  ]
}
```

### `POST /datasets/classify`

```bash
curl -X POST https://api.opendata.example.com/datasets/classify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source":"ckan",
    "dataset_id":"stazioni-ricarica",
    "dataset_name":"Stazioni di ricarica auto elettriche",
    "dataset_description":"Mappa delle colonnine pubbliche…",
    "taxonomy":["energy","transport","environment"]
  }'
# { "source":"ckan", "dataset_id":"stazioni-ricarica",
#   "scores":{"energy":0.78,"transport":0.94,"environment":0.41},
#   "model":"claude-haiku-4-5-20251001", "cached":false }
```

### Authentication & API keys

For programmatic access (no browser / Clerk session) use an **API key**. Mint
one from an authenticated session, then send it as a Bearer token (keys are
prefixed `od_` so the backend tells them apart from Clerk JWTs) or via the
`X-API-Key` header. The clear-text token is shown **once** — only its SHA-256
hash is stored.

```bash
# 1. Create a key (from a Clerk-authenticated session)
curl -sX POST https://api.opendata.example.com/api-keys/generate \
  -H "Authorization: Bearer $CLERK_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-cli"}'
# → { "id":42, "name":"my-cli", "token":"od_…", "created_at":"…" }

# 2. Use it on any endpoint (REST or A2A)
export OPENDATA_API_KEY="od_…"
curl -s https://api.opendata.example.com/datasets/search \
  -H "X-API-Key: $OPENDATA_API_KEY" \
  -G --data-urlencode 'q=qualità aria a Milano'

# 3. List / revoke
curl -s https://api.opendata.example.com/api-keys     -H "X-API-Key: $OPENDATA_API_KEY"
curl -sX DELETE https://api.opendata.example.com/api-keys/42 -H "X-API-Key: $OPENDATA_API_KEY"
```

A key inherits its owner's `subscription_tier` (default `free`), which drives
the per-minute rate limit. Tiers are tuned via `RATE_LIMIT_TIERS`
(`tier=limit,…`); an unlisted tier falls back to `RATE_LIMIT_PER_MINUTE`. The
concrete subscription plans are defined separately — this is the access-control
hook they build on. Full guide: `/docs/api-keys` in the developer portal.

## Use the MCP servers from an AI client

The three servers (`ckan-mcp`, `istat-mcp`, `osm-mcp`) work with any
MCP-capable client — Claude Desktop, Claude Code, Cursor, VS Code, … — over
two transports. Full walk-through (multiple clients, `mcp-remote` bridge,
troubleshooting) in the developer portal at **`/docs/clients`**.

**A · stdio** — the client launches the server as a subprocess. Easiest via
the published GHCR images (no local Python needed). Drop this into Claude
Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opendata-ckan": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/ckan-mcp-server:main"],
      "env": { "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata" }
    },
    "opendata-istat": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/istat-mcp-server:main"]
    },
    "opendata-osm": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/osm-mcp:main"]
    }
  }
}
```

Installed from source instead of Docker? Point `command` at the absolute path
of the console script (`…/.venv/bin/ckan-mcp`). From the **Claude Code** CLI:

```bash
pip install -e ./ckan-mcp-server -e ./istat-mcp-server -e ./osm-mcp
claude mcp add opendata-ckan --env TRANSPORT=stdio -- ckan-mcp   # + istat, osm
```

**B · streamable-http** — run the servers as a service (`make up` →
ckan `:18080`, istat `:18081`, osm `:18085`) and connect over HTTP. Clients
that speak HTTP natively (Cursor, VS Code, Claude Code) use the URL directly:

```bash
claude mcp add --transport http opendata-ckan http://localhost:18080/mcp
```

stdio-only clients (Claude Desktop) bridge with `npx -y mcp-remote
http://localhost:18080/mcp`. If you expose a hosted MCP endpoint publicly
behind the gateway, authenticate it with your API key —
`mcp-remote … --header "Authorization: Bearer od_…"`. (The servers themselves
are auth-free infra; in prod they sit on a private network reached only by the
backend.)

## Local development

```bash
# 1. Submodule (optional in dev — the stub schema mirrors agent-stack).
git submodule update --init --depth=1

# 2. Bring up Postgres, Redis, the three MCP servers + the unified backend.
cp .env.local.example .env.local
make up

# 3. (one-off) apply database migrations.
docker compose exec opendata-backend alembic upgrade head

# 4. Run the frontend.
cd opendata-ai-ui && npm install && npm run dev      # http://localhost:3000
```

`AUTH_ENABLED=false` in `.env.local.example` lets the backend treat every
caller as a synthetic `dev-user`, so the UI works without a real Clerk
token while you iterate.

Targets:

```bash
make up / down / logs / ps        # stack lifecycle
make lint / test                  # ruff + pytest across all 5 Python packages
make rebuild                      # docker compose build --no-cache
make agent                        # interactive REPL against the running backend
make mcp-stdio-ckan|istat|osm     # smoke-test each MCP server's stdio transport
```

## Production deploy

Backend → Aruba VPS, frontend → GitHub Pages. Full procedure in
`infra/aruba/README.md`. Short version:

1. DNS: `api.opendata.<domain>` → VPS, `opendata.<domain>` CNAME → `<gh-user>.github.io`
2. On the VPS: clone the repo, copy `infra/aruba/.env.prod.example` → `.env.prod`, edit, then
   `docker compose --env-file .env.prod -f infra/aruba/docker-compose.prod.yml up -d` and
   `alembic upgrade head`.
3. GitHub repo Settings:
   - Pages source = "GitHub Actions"
   - Variables: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, sign-in/up URLs
   - Secrets: `CLERK_SECRET_KEY`, `ARUBA_SSH_KEY`
4. Configure the Clerk webhook endpoint to point at `https://api.opendata.<domain>/webhooks/clerk`.

## Remaining manual steps to a live deploy

- [ ] Provision Aruba VPS + DNS records
- [ ] Run `clerk init --app app_3EMALiLi0UTULl89JPMKtaLENoy` and capture the JWT issuer + publishable + secret keys
- [ ] Configure the Clerk webhook endpoint
- [ ] Top up Anthropic API key with budget for Sonnet + Haiku
- [ ] Configure GitHub repo Variables/Secrets (CI deploy expects them)
- [ ] First-time `git submodule update --init` if the agent-stack repo is accessible

## License

MIT — see [LICENSE](LICENSE).
