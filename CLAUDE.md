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

Frontend + backend both run on a shared Aruba VPS under the
`agent-engineering-studio-infra` topology at `/opt/aes-infra/` (base
`docker-compose.yml` + overlay `docker-compose.opendata.yml`, env files
`.env` + `.env.opendata`). Images are pulled from GHCR by the
`OPENDATA_TAG` env var (default `main`). The `deploy-aruba.yml` workflow
SSHs into the VPS, runs `docker compose pull && up -d` on the 5 opendata
services (ckan/istat/osm-mcp + opendata-backend + opendata-ai-ui), and
leaves traefik/redis untouched (those belong to the infra repo). The
in-repo `infra/aruba/docker-compose.prod.yml` is a legacy
single-tenant reference — the live VPS does NOT use it. There is no
Azure code anymore.

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

## Operational rules

Each rule has a **Why** (the rationale, so edge cases can be judged) and
a **How to apply** (when it kicks in).

### R1 — Docker build context is the repo root

- **Why:** every backend Dockerfile copies `opendata_core/` alongside its
  own sources. CI (`ci.yml`, `docker-publish.yml`) builds the same way.
  Switching to a per-package context silently breaks the shared client.
- **How to apply:** when adding/editing a Dockerfile or compose service,
  keep `context: .` at repo root and prefix paths with the package name.

### R2 — `opendata-backend` install needs `--pre`

- **Why:** `agent-framework` is published as a pre-release; pip skips it
  without `--pre`, and the backend fails to import.
- **How to apply:** `pip install --pre -e ".[dev,azure,claude]"` for the
  backend only. The four other packages install without `--pre`.

### R3 — Run tests via `/tmp/oda-venv`

- **Why:** the venv at `/tmp/oda-venv` is already permitted in
  `.claude/settings.local.json`. Other interpreters trigger a permission
  prompt and slow the loop down.
- **How to apply:** `/tmp/oda-venv/bin/python -m pytest -q <pkg>`. Prefer
  per-package runs over `make test` when iterating; full suite only
  before commit.

### R4 — SQLAlchemy models use the `opendata` schema + SQLite-safe PK

- **Why:** Postgres tables live under schema `opendata`, but SQLite (in
  unit tests) doesn't have schemas. `_strip_schema` and `_PK` reconcile
  the two. `BigInteger` does not auto-increment on SQLite without the
  variant alias.
- **How to apply:** new model →
  `__table_args__ = ({"schema": "opendata"},)` **and**
  `id = Column(_PK, primary_key=True)` (alias defined in
  `opendata_backend/db/models.py`). New migration → `op.execute("CREATE
  SCHEMA IF NOT EXISTS opendata")` first.

### R5 — Agent reply contract is duplicated four ways — update all

- **Why:** the `<!--RESOURCES_JSON-->` block is emitted by four prompt
  templates (`CKAN_INSTRUCTIONS`, `ISTAT_INSTRUCTIONS`,
  `EUROSTAT_INSTRUCTIONS`, `OECD_INSTRUCTIONS` in
  `opendata_backend/config.py`) and parsed in
  `opendata_backend/orchestrator/parsing.py`. Touching one without the
  others ships a contract mismatch.
- **How to apply:** any change to the marker, field names, or JSON shape
  → grep both files, update all five spots, then run
  `tests/test_synth_merge.py` and `tests/test_config.py`.

### R6 — Frontend is `output: 'export'` — no API routes

- **Why:** the UI ships as a static bundle to GitHub Pages. `app/api/*`
  handlers are silently dropped at build and 404 in production.
- **How to apply:** any new backend-mediated call goes through
  `opendata-ai-ui/lib/api.ts::apiFetch()` with a Clerk Bearer token.
  Never add files under `opendata-ai-ui/app/api/`.

### R7 — Clerk auth: dev bypass vs. prod JWKS

- **Why:** `AUTH_ENABLED=false` (dev) makes `require_user` return a
  synthetic `dev-user`. In prod the backend verifies JWTs via the
  issuer's JWKS — no app ID needed on the backend.
- **How to apply:** never add anonymous endpoints. New routes either go
  through `Depends(require_user)` or live under `/health`. If you need
  the Clerk app ID, it is pinned to `app_3EMALiLi0UTULl89JPMKtaLENoy`
  per `.clerk/config.md`.

### R8 — CORS belongs on the backend

- **Why:** UI on GitHub Pages talks cross-origin to the Aruba VPS. The
  static export has no server to set CORS on.
- **How to apply:** edit `cors_allow_origins` (comma-separated) in
  backend `Settings`. Don't add CORS shims to the frontend.

### R9 — MCP hostnames depend on the active `.env*`

- **Why:** inside docker-compose the services resolve each other by
  service name (`http://ckan-mcp:8080/mcp`). From host-side debug, only
  `http://localhost:<port>` works.
- **How to apply:** check which env file (`.env.local` vs `.env.local`
  with host-override) is active before editing `CKAN_MCP_URL` /
  `ISTAT_MCP_URL` / `OSM_MCP_URL`.

### R10 — `OLLAMA_LLM_MODEL` is the modelfile tag, not the base

- **Why:** the Ollama image bakes a tuned modelfile tagged `qwen2.5:32k`
  (32k context, T=0). The base `qwen2.5:32b` exists but isn't tuned.
- **How to apply:** keep `OLLAMA_LLM_MODEL=qwen2.5:32k` unless rebuilding
  the image via `make build-ollama OLLAMA_BASE_MODEL=...
  OLLAMA_MODEL=...`.

### R11 — Classify model is separate from the synth provider

- **Why:** the classify endpoint always calls `CLAUDE_CLASSIFY_MODEL`
  (Haiku 4.5) regardless of `LLM_PROVIDER`. Three-layer cache
  (Redis 24h → `opendata.classifications` → Anthropic) means classify
  cost is bounded.
- **How to apply:** when tuning provider plumbing in `config.py` /
  `factory.py`, do not touch the classify path. When bumping classify
  models, update `CLAUDE_CLASSIFY_MODEL` only.

### R12 — Before commit: `make lint && make test`

- **Why:** ruff + pytest gate every CI run. Never `--no-verify` and never
  force-push to `main`.
- **How to apply:** if a hook fails, fix the root cause and create a new
  commit, do not amend.

### R13 — A2A is orthogonal to MCP: don't conflate the two

- **Why:** MCP exposes **tools** to a single LLM. A2A exposes **the whole
  agent** to another agent. The opendata-ai backend is an MCP client (CKAN
  / SDMX / OSM) AND an A2A server (publishes AgentCard at
  `/.well-known/agent-card.json` — SDK 1.0 path with dash — JSON-RPC at
  `/a2a/`, accepting both PascalCase `SendMessage` and slash-case
  `message/send` thanks to v0.3 compat). Mixing them — e.g. exposing SDMX
  tools over A2A or vice versa — defeats both protocols.
- **How to apply:**
  - Adding a new external **tool** for the LLM → write an MCP server,
    follow the `ckan-mcp-server/` pattern.
  - Adding a new exported **skill** for other agents → edit
    `opendata_backend/a2a/agent_card.py` and the corresponding branch in
    `opendata_backend/a2a/executor.py`. Skills delegate to existing
    orchestrator code; don't duplicate logic.
  - Recursion safety: setting `A2A_SPECIALIST_URL` to point at the same
    backend's `/.well-known/agent.json` works for the round-trip demo
    but creates infinite delegation under load. Use a separate process
    or a different agent in production.

## Skill routing

Skills available in this workspace and when to invoke them.

| Task | Skill |
|---|---|
| Add/verify Clerk auth in a new package or env | `clerk-setup` |
| List/create users, orgs, sessions via Clerk CLI | `clerk-cli` |
| Direct REST calls to Clerk Backend API | `clerk-backend-api` |
| Org switching, RBAC, multi-tenant in the UI | `clerk-orgs` |
| Custom sign-in/sign-up UI, theming | `clerk-custom-ui` |
| Next.js middleware, Server Actions, caching with Clerk | `clerk-nextjs-patterns` |
| Webhooks (svix verify, DB sync) | `clerk-webhooks` |
| E2E auth tests | `clerk-testing` |
| Classify endpoint, prompt caching, model bumps, SDK code | `claude-api` |
| Launch the stack to visually validate a change | `run` |
| Manual verification of a fix in the running app | `verify` |
| Pre-PR review of the current diff | `code-review` |
| Apply low-risk simplifications to the diff | `simplify` |
| Security review before merging | `security-review` |
| Edit `settings.json` (permissions, hooks, env) | `update-config` |
| Reduce permission prompts based on transcripts | `fewer-permission-prompts` |
| Recurring polls (CI, deploys) | `loop` |
| One-off or cron-scheduled remote agents | `schedule` |
| Reviewing a PR (not the local diff) | `review` |

**Do not use** in this repo: `init` (this file is hand-maintained —
regenerating overwrites the architecture invariants section).

Quick examples:
- "Bump the classify model to Haiku 4.5 and add prompt caching" →
  `claude-api` + edit `opendata_backend/config.py` + run classify tests.
- "Add a new authenticated endpoint" → write code, then `code-review`
  and `security-review` before push.
- "Add a webhook to sync Clerk users into `opendata.users`" →
  `clerk-webhooks` for the verify+handler skeleton, then back to normal
  edits.

## Quick reference

- **Schema source of truth (submodule):** `vendor/agent-stack/`
- **Migration stub:** `opendata-backend/migrations/versions/0001_initial.py`
- **Provider resolver:** `opendata_backend/config.py::resolve_provider`
- **Orchestrator parser:** `opendata_backend/orchestrator/parsing.py`
- **Clerk app pin:** `.clerk/config.md` (`app_3EMALiLi0UTULl89JPMKtaLENoy`)
- **Permitted Bash patterns:** `.claude/settings.local.json`
- **Backend Dockerfile + entrypoint:** `opendata-backend/Dockerfile`,
  `opendata-backend/scripts/migrate.sh`
- **Prod compose + reverse proxy (live VPS):** `/opt/aes-infra/docker-compose.yml`
  (base) + `/opt/aes-infra/docker-compose.opendata.yml` (overlay), Traefik
  routes via labels on each service. Legacy single-tenant reference at
  `infra/aruba/docker-compose.prod.yml` + `infra/aruba/Caddyfile` is kept
  for documentation but NOT used by `deploy-aruba.yml` anymore.
