# opendata-ai

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

All authenticated with a Clerk Bearer token, except where noted.

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
| POST | `/api-keys/generate` | Programmatic API key — token returned once, persisted as SHA-256 |
| POST | `/webhooks/clerk` | svix-signed; upserts `opendata.users` on `user.{created,updated,deleted}` |

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

## Use the MCP servers from Claude Desktop

The three MCP servers ship a stdio transport. Drop this into your
`claude_desktop_config.json` (full reference in `docs/claude-desktop.md`):

```json
{
  "mcpServers": {
    "opendata-ckan": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/ckan-mcp-server:latest"],
      "env": { "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata" }
    },
    "opendata-istat": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/istat-mcp-server:latest"]
    },
    "opendata-osm": {
      "command": "docker",
      "args": ["run","--rm","-i","-e","MCP_TRANSPORT=stdio",
               "ghcr.io/agent-engineering-studio/osm-mcp:latest"]
    }
  }
}
```

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
