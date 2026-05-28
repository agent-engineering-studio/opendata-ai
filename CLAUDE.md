# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Repository purpose

`opendata-ai` exposes Italian + European open-data portals through an
authenticated REST surface and a static map UI. Five Python packages + a
Next.js 15 frontend:

- `opendata_core/` — shared async clients (CKAN, SDMX, OSM render +
  Nominatim/Overpass/OSRM) consumed by both the MCP wrappers and the
  backend. **No FastMCP, no FastAPI, no LLM code here.**
- `ckan-mcp-server/` — FastMCP wrapper exposing 11 CKAN tools (per-call
  `base_url`, so one image works against any portal). Transports: stdio
  or streamable-HTTP.
- `istat-mcp-server/` — FastMCP wrapper for SDMX 2.1. Works for ISTAT,
  Eurostat and OECD via the `agency` / `base_url` arguments — same image.
- `osm-mcp/` — FastMCP wrapper that turns GeoJSON into self-contained
  Leaflet+OSM HTML pages. Also exposes geocoding/POI/routing tools
  (unused by the backend today, kept for Claude Desktop integrations).
- `opendata-backend/` — **the single backend**, FastAPI on port 8000. It
  absorbed the previous orchestrator + per-source agents; the multi-source
  fan-out (CKAN + ISTAT [+ Eurostat + OECD]) lives under
  `opendata_backend.orchestrator`. Adds Clerk auth on every endpoint
  except `/health`, Postgres ORM for `opendata.users/favorites/history/
  api_keys/classifications`, Redis cache + per-user rate limit, and a
  Claude Haiku 4.5 classify endpoint.
- `opendata-ai-ui/` — Next.js 15 with `output: 'export'` for GitHub Pages.
  Uses `@clerk/nextjs` for auth and talks to the backend cross-origin via
  `lib/api.ts::apiFetch()` with a Bearer token.

## Architecture invariants

- **Submodule for the schema.** `opendata.*` migrations live in
  `vendor/agent-stack/` (a read-only submodule). The backend ships a stub
  `opendata-backend/migrations/versions/0001_initial.py` that mirrors the
  expected shape so `alembic upgrade head` works even when the submodule
  is not initialised.
- **Three-layer cache for classify.** `Redis (24h)` → `Postgres
  opendata.classifications` (durable) → `Anthropic Haiku`. Cache key is
  `(source, dataset_id, sha256(sorted(taxonomy)))` so the order of the
  taxonomy doesn't change the cache hit.
- **Clerk app `app_3EMALiLi0UTULl89JPMKtaLENoy`** is pinned in
  `.clerk/config.md`. Anytime you run `clerk init`, pass
  `--app app_3EMALiLi0UTULl89JPMKtaLENoy`. The backend verifies JWTs via
  the issuer's JWKS — it doesn't need the app ID itself.
- **`AUTH_ENABLED=false`** in `.env.local.example` is the dev-mode bypass.
  When false, `require_user` returns a synthetic `dev-user` instead of
  rejecting the request. **There is no anonymous endpoint** — every route
  except `/health` either authenticates or runs in dev-bypass mode.
- **CORS lives on the backend** because the frontend ships cross-origin
  via GitHub Pages. `cors_allow_origins` in Settings is a comma-separated
  list (defaults to `http://localhost:3000`).
- **Build context = repo root** for every backend image. The Dockerfiles
  copy `opendata_core/` and the service's own sources side-by-side. CI
  (`ci.yml` + `docker-publish.yml`) builds the same way; do not change
  the context back to the per-package directory.

## Commands

```bash
make up / down / logs / ps        # stack lifecycle (cpu profile by default)
make up-gpu                       # NVIDIA Ollama profile
make rebuild                      # build all custom images without cache
make lint                         # ruff over all 5 Python packages
make test                         # pytest over all 5 Python packages
make agent                        # REPL into the running backend
make mcp-stdio-ckan|istat|osm     # one-shot tools/list over stdio
```

Per-package editable install (note `--pre` for `agent-framework`):

```bash
cd opendata_core      && pip install -e ".[dev]"
cd ../ckan-mcp-server && pip install -e ".[dev]"
cd ../istat-mcp-server && pip install -e ".[dev]"
cd ../osm-mcp         && pip install -e ".[dev]"
cd ../opendata-backend && pip install --pre -e ".[dev,azure,claude]"
```

Run the backend stand-alone (needs an LLM key + the MCP servers reachable):

```bash
cd opendata-backend
DATABASE_URL=postgresql+asyncpg://opendata:opendata@localhost:5432/opendata \
REDIS_URL=redis://localhost:6379/1 \
AUTH_ENABLED=false \
ANTHROPIC_API_KEY=... \
opendata-backend-api    # http://localhost:8000
```

## LLM provider

`LLM_PROVIDER = ollama | azure_foundry | claude | auto` resolved by
`opendata_backend.config.resolve_provider`. `auto` (default) picks
`claude` if `ANTHROPIC_API_KEY` is set, `azure_foundry` if the Azure
endpoint + deployment name are set, else `ollama`. The **classify**
endpoint always uses `CLAUDE_CLASSIFY_MODEL` (Haiku 4.5 by default)
regardless of the synth provider — keep them separate.

## Production layout

Frontend → GitHub Pages (`deploy-pages.yml`). Backend → Aruba VPS
(`infra/aruba/docker-compose.prod.yml` + Caddyfile, deployed via
`deploy-aruba.yml`). There is no Azure code anymore.

## Things easy to get wrong

- `OLLAMA_LLM_MODEL` must match the modelfile *tag* baked in the Ollama
  image (`qwen2.5:32k`), not the base model name (`qwen2.5:32b`).
- `CKAN_MCP_URL` / `ISTAT_MCP_URL` use compose-internal hostnames inside
  Docker (`http://ckan-mcp:8080/mcp`) but `http://localhost:…` for
  host-side debug. Pick the right one for the active `.env*`.
- When changing provider plumbing, touch `config.py` AND `factory.py`
  inside `opendata-backend/`. Don't reintroduce the per-source agent
  packages — the orchestrator lives in `opendata_backend.orchestrator`.
- When changing the agent response contract (the `<!--RESOURCES_JSON-->`
  block), update the four sources of truth: `opendata_backend/config.py`
  (CKAN_INSTRUCTIONS, ISTAT_INSTRUCTIONS, EUROSTAT_INSTRUCTIONS,
  OECD_INSTRUCTIONS) and the parser in
  `opendata_backend/orchestrator/parsing.py`.
- Don't strip `--pre` from the `opendata-backend` install —
  `agent-framework` is published as a pre-release.
- The frontend uses `output: 'export'` — do NOT add new `app/api/*`
  route handlers; they won't be reachable. New backend-mediated calls go
  through `lib/api.ts::apiFetch()`.
- The Postgres schema is `opendata`. SQLAlchemy models declare
  `__table_args__ = ({"schema": "opendata"},)` and migrations create the
  schema explicitly. SQLite (used in unit tests) ignores the schema kwarg
  via the `_strip_schema` helper.
- `BigInteger` primary keys don't auto-increment on SQLite. Use the
  `_PK = BigInteger().with_variant(Integer(), "sqlite")` alias defined in
  `db/models.py`.
