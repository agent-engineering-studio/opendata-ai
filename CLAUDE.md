# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

`opendata-ai` is a polyglot mono-repo that fans a user query across **up to four open-data sources** (CKAN portals + three SDMX-based statistical providers: ISTAT, Eurostat, OECD) and synthesises a single answer. Five Python services + one Next.js UI:

- `ckan-mcp-server/` — FastMCP server wrapping the CKAN Action API (`/api/3/action/*`). Transport: `stdio` or `streamable-http`. Entry: `ckan_mcp.server:main` → `ckan-mcp-server`. Default port `8080`.
- `ckan-mcp-agent/` — Microsoft Agent Framework client for CKAN. CLI `ckan-agent` + FastAPI `ckan-agent-api` on port `8002`. Mounts the CKAN MCP server via `MCPStreamableHTTPTool`.
- `istat-mcp-server/` — FastMCP server wrapping the SDMX 2.1 REST protocol. **Despite the legacy name, this server is source-agnostic** — `istat_list_dataflows` accepts an `agency` parameter ("IT1" for ISTAT, "ESTAT" for Eurostat, "all" for OECD) and every tool takes a `base_url`. Default port `8081`. 9 tools: dataflow search, structure, codelist, concept, constraints, get-data (CSV), territorial codes (ISTAT-only), cache stats.
- `istat-mcp-agent/` — Microsoft Agent Framework client for ISTAT proper. CLI `istat-agent` + FastAPI `istat-agent-api` on port `8003`. Mounts the SDMX MCP server via `MCPStreamableHTTPTool`. Same three LLM providers as `ckan-mcp-agent`. **The Dockerfile installs both `[azure]` and `[claude]` extras** so production deploys can pick the provider via `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` without rebuilding.
- `opendata-orchestrator/` — **Multi-agent orchestrator** built with `agent_framework.orchestrations.ConcurrentBuilder`. Fans the query out in parallel to up to 4 specialists (CKAN + ISTAT + Eurostat + OECD; the last two are opt-in via `ENABLE_EUROSTAT` / `ENABLE_OECD`). The three SDMX specialists all dial **the same** `istat-mcp-server` — they differ only by the `agency` + `base_url` baked into their instructions. A tool-less `synth` agent then merges their narratives. Returns the canonical `{text, resources[]}` shape with a `source: "ckan" | "istat" | "eurostat" | "oecd"` tag on each resource. CLI `opendata-agent` + FastAPI `opendata-orchestrator-api` on port `8000`. **This is the entry the UI talks to.**
- `opendata-ai-ui/` — Next.js 15 chat demo (port `3000`). Proxies `/api/chat` to the orchestrator (`AGENT_API_URL=http://opendata-orchestrator:8000`). ResourceCard renders a per-source coloured badge (violet=ckan, amber=istat, sky=eurostat, rose=oecd).

Each specialist agent still exposes its own `/chat` (8002 / 8003) for direct debug; the UI uses only the orchestrator on `:8000`.

## LLM provider — two environments, one mental model

All three agents (`ckan-mcp-agent`, `istat-mcp-agent`, `opendata-orchestrator`) share the **same** `Provider = Literal["ollama", "azure_foundry", "claude"]` and the same 3-branch `build_chat_client(settings)` in their respective `factory.py`. All three Docker images pre-install BOTH the `[azure]` and `[claude]` optional dependencies, so a deploy can switch provider via env vars alone, with no image rebuild.

The repo is designed around exactly **two `.env*.example` files**:

### `.env.local.example` — local debug
Default `LLM_PROVIDER=ollama`. Two sub-variants of local debug live in this same file:

- **Docker stack (default)**: copy to `.env` (or `.env.local`), `make up` brings up `opendata-ai-ollama` + `ckan-mcp` (8080) + `istat-mcp` (8081) + `ckan-agent` (8002) + `istat-agent` (8003) + `opendata-orchestrator` (8000) + `opendata-ai-ui` (3000). No API key needed. `OLLAMA_LLM_MODEL=qwen2.5:32k` must match the modelfile tag baked in the Ollama image (`ghcr.io/agent-engineering-studio/opendata-ai-ollama:latest` — qwen2.5:32b + num_ctx 16384 + temperature 0).
- **Host-side Python with Claude**: set `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` in the same file, run MCP servers + agents + orchestrator as host Python processes (VS Code stack debug), and flip `CKAN_MCP_URL` / `ISTAT_MCP_URL` to `http://localhost:…`. Ollama is not started.

In LOCAL DEBUG `azure_foundry` is intentionally not exercised — reserve it for production.

### `.env.production.example` — production deploy
Two production variants, **same file**, pick one by setting `LLM_PROVIDER`:

- **A — Claude (default)**: `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY` (store as platform secret). Cheapest path. Works on any container host.
- **B — Azure AI Foundry**: `LLM_PROVIDER=azure_foundry` + `AZURE_AI_PROJECT_ENDPOINT` + `AZURE_AI_MODEL_DEPLOYMENT_NAME`. Auth via `DefaultAzureCredential` (managed identity in Azure Container Apps). Required for the Bicep-based ACA deploy.

In PRODUCTION Ollama is not used — leave all `OLLAMA_*` unset.

When editing provider-selection code (`*/factory.py`, `*/config.py`) verify all three branches still build in **all three** of `ckan-mcp-agent`, `istat-mcp-agent`, `opendata-orchestrator`. When editing env handling, update both `.env.local.example` and `.env.production.example` so they stay in sync.

## Commands

```bash
# Stack lifecycle (Ollama profile)
make up              # CPU stack
make up-gpu          # NVIDIA stack
make down            # stop everything (both profiles)
make ps / logs       # status / tail logs
make rebuild         # rebuild all MCP servers + agents + orchestrator (no cache)
make build-ollama    # bake the Ollama image with qwen2.5:32k (num_ctx 16384, temp 0) locally
make pull-models     # fallback when Ollama image has no baked model

# Interactive REPL against the running stack
make agent                       # default = orchestrator (fan-out)
make agent SOURCE=ckan           # CKAN specialist only
make agent SOURCE=istat          # ISTAT specialist only

# Lint + test all five Python packages
make lint
make test

# Single test
cd ckan-mcp-agent       && pytest -q tests/test_api_parsing.py::test_name
cd opendata-orchestrator && pytest -q tests/test_synth_merge.py
```

Per-package editable installs (note `--pre` — `agent-framework` is pre-release):

```bash
cd ckan-mcp-server       && pip install -e ".[dev]"
cd ckan-mcp-agent        && pip install --pre -e ".[dev,azure]"
cd istat-mcp-server      && pip install -e ".[dev]"
cd istat-mcp-agent       && pip install --pre -e ".[dev,azure]"
cd opendata-orchestrator && pip install --pre -e ".[dev,azure,claude]"
```

Run a service standalone:

```bash
# A specialist MCP server, host-side
cd ckan-mcp-server  && TRANSPORT=streamable-http PORT=8080 ckan-mcp-server
cd istat-mcp-server && TRANSPORT=streamable-http PORT=8081 istat-mcp-server

# A specialist agent (requires its MCP server + an LLM reachable)
cd ckan-mcp-agent       && ckan-agent              # REPL
cd ckan-mcp-agent       && ckan-agent-api          # FastAPI on :8002
cd istat-mcp-agent      && istat-agent-api         # FastAPI on :8003

# The orchestrator (requires BOTH MCP servers + an LLM reachable)
cd opendata-orchestrator && opendata-orchestrator-api   # FastAPI on :8000
cd opendata-orchestrator && opendata-agent              # REPL
```

## Architecture notes that span files

- **Two MCP servers, four (optional) specialist agents, one orchestrator.** The orchestrator does **not** call the specialist agents over HTTP; it builds its own `Agent` instances (one per enabled source) that connect directly to an MCP server. CKAN talks to `ckan-mcp`; ISTAT / Eurostat / OECD all talk to `istat-mcp` (same server, different `agency` + `base_url` baked into their instructions). The standalone specialist agents (`ckan-agent`, `istat-agent`) are kept around for direct debug only.
- **Concurrent fan-out.** `opendata-orchestrator/src/orchestrator/workflow.py` builds `ConcurrentBuilder(participants=[…]).with_aggregator(synth).build()` where `participants` is built dynamically from the enable flags (`ENABLE_CKAN`, `ENABLE_ISTAT`, `ENABLE_EUROSTAT`, `ENABLE_OECD`). The aggregator (`orchestrator/synth.py`) parses each branch's reply with `parse_agent_reply`, deterministically dedupes resources by URL (preferring entries with non-null content), tags each resource with `source: "ckan" | "istat" | "eurostat" | "oecd"`, then calls a tool-less synth agent (`SYNTH_INSTRUCTIONS`) to merge the N narratives into one paragraph. The final output keeps the existing `<narrative>\n<!--RESOURCES_JSON-->\n<array>\n<!--/RESOURCES_JSON-->` shape so `opendata-ai-ui` consumes it unchanged.
- **Eurostat / OECD default OFF.** Each enabled SDMX specialist adds 1 LLM call per query, so flipping them on globally roughly doubles or triples the per-query cost on Claude / Foundry. The defaults in `Settings` are `enable_eurostat=False` and `enable_oecd=False`; production envs opt in via the `ENABLE_EUROSTAT=true` / `ENABLE_OECD=true` envs (already set to `true` in `.env.production.example`, left `false` in `.env.local.example`).
- **Response contract preserved.** All three agents (CKAN, ISTAT, orchestrator) emit the same `{text, resources[]}` shape via `/chat`. The only addition is the optional `source` field on each `Resource`. UI components `ResourceCard.tsx` render a small extra badge when `source` is present.
- **Per-call `base_url` is the design contract.** Every MCP tool in `ckan_mcp/tools.py` and `istat_mcp/tools.py` takes an optional `base_url`. The CKAN agent's instructions (in `ckan_agent/config.py` AND in `orchestrator/config.py::CKAN_INSTRUCTIONS` — kept in sync verbatim) pick one portal from an embedded international list when no `PORTAL_HINT:` prefix is given. ISTAT only has one base URL.
- **Instruction duplication is intentional.** `orchestrator/config.py` carries verbatim copies of `CKAN_INSTRUCTIONS` and a shared SDMX template that renders `ISTAT_INSTRUCTIONS`, `EUROSTAT_INSTRUCTIONS`, `OECD_INSTRUCTIONS` at module load. The orchestrator package has no Python-level dependency on `ckan-mcp-agent` or `istat-mcp-agent`. **If you edit `ckan_agent.config.AGENT_INSTRUCTIONS` or `istat_agent.config.AGENT_INSTRUCTIONS`, port the change to `orchestrator/config.py` as well.** Adding a new SDMX source means: extend `_SDMX_INSTRUCTIONS_TEMPLATE.format(...)` invocations, add the corresponding Settings fields + enable flag, add a tuple in `OrchestratorSession.__aenter__::sdmx_specs`, extend `parsing.SourceTag` + `synth._normalise_source_tag` + `synth._SYNTH_SOURCE_ORDER`, and finally `opendata-ai-ui/lib/types.ts::ResourceSource` + `ResourceCard.tsx::sourceBadgeColor / sourceTooltip`.
- **CkanError / SdmxError surface.** `ckan_mcp/ckan_client.py::CkanError` and `istat_mcp/sdmx_client.py::SdmxError` are each the single error class for their server. Keep that contract — tools modules only handle the dedicated error.
- **Transport dispatch.** Both MCP servers switch between `stdio` / `streamable-http` / `sse` via `TRANSPORT`. Docker images run `streamable-http`; Claude Desktop integrations run `stdio`.
- **CI matrix.** `.github/workflows/ci.yml` runs ruff + pytest **per package** across all five Python packages, then buildx docker builds for each image. `docker-publish.yml` pushes multi-arch images to GHCR for all five.

## Things easy to get wrong

- `OLLAMA_LLM_MODEL` must match the modelfile *tag* baked in the Ollama image (`qwen2.5:32k`), not the base model name (`qwen2.5:32b`). `make build-ollama` and `publish-ollama.yml` bake `num_ctx 16384` + `temperature 0`; override the base/tag via the Makefile `OLLAMA_*` vars for lighter machines (e.g. `qwen2.5:14b`/`:14k`).
- `CKAN_MCP_URL` / `ISTAT_MCP_URL` use compose-internal hostnames inside Docker (`http://ckan-mcp:8080/mcp`, `http://istat-mcp:8081/mcp`) but `http://localhost:8080/mcp` / `http://localhost:8081/mcp` for host-side debug. Pick the right one for the active `.env*` file.
- When changing provider plumbing, touch **all three** `factory.py` / `config.py` pairs (`ckan-mcp-agent`, `istat-mcp-agent`, `opendata-orchestrator`) plus the three `.env*.example` files. The provider literal and the builder branches are duplicated by design (side-by-side layout, no shared package).
- When changing the agent response contract (the `<!--RESOURCES_JSON-->` block), update **four** sources of truth: `ckan_agent.config.AGENT_INSTRUCTIONS`, `istat_agent.config.AGENT_INSTRUCTIONS`, `orchestrator.config.CKAN_INSTRUCTIONS` and `orchestrator.config.ISTAT_INSTRUCTIONS`. The parser lives in three places (each agent's `api.py` + `orchestrator/parsing.py`); changes must be mirrored.
- Don't strip `--pre` from the agent installs — `agent-framework` is published as a pre-release.
- The orchestrator's port is `8000`, not `8002`. The UI's `AGENT_API_URL` default has been updated accordingly; if a `.env.local` already exists locally with `:8002`, update it.
