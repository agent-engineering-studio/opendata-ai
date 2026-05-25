# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

`mcp-ckan` is a polyglot mono-repo with three deployable units that wrap **any** CKAN open-data portal behind an MCP server and an agent:

- `ckan-mcp-server/` — Python MCP server (FastMCP). Wraps the CKAN Action API (`/api/3/action/*`). Runs over `stdio` (Claude Desktop) or `streamable-http` (containerised). Entry: `ckan_mcp.server:main` → `ckan-mcp-server`.
- `ckan-mcp-agent/` — Python Microsoft Agent Framework client. CLI (`ckan-agent`) + FastAPI (`ckan-agent-api`, port 8002). Mounts the MCP server as an `MCPStreamableHTTPTool` and reasons with one of three LLM providers. Entry: `ckan_agent.main:main` and `ckan_agent.api:main`.
- `opendata-ai-ui/` — Next.js 15 chat demo (port 3000). Proxies `/api/chat` to the agent (`AGENT_API_URL`).

The agent is **always** wired to the MCP server. What changes per environment is the **LLM provider** behind the agent.

## The two supported configurations

This repo is explicitly designed around two day-to-day setups. Treat them as first-class — every change must work in both.

### 1. Local Docker stack with Ollama (default — no API key)

- `.env` is the active config (copy from `.env.example`).
- `LLM_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://ckan-ollama:11434`.
- The Ollama image bakes a custom modelfile `qwen2.5:16k` (= base `qwen2.5:7b-instruct` + `PARAMETER num_ctx 16384`). `OLLAMA_LLM_MODEL` must match the baked tag — using the base name yields *"model not found"*.
- `OLLAMA_IMAGE` defaults to the GHCR pre-built image (~7 GB). For a locally-built image set `OLLAMA_PULL_POLICY=if_not_present`, otherwise compose's default `always` will overwrite it on each `up`.
- All four services run via `docker compose`: `ckan-ollama` (cpu or gpu profile), `ckan-mcp` (8080), `ckan-agent` (8002), `opendata-ai-ui` (3000).
- Bring up with `make up` (CPU) / `make up-gpu` (NVIDIA). First boot needs `make pull-models` only when *not* using the baked image.

### 2. Local debug against Anthropic Claude API (no Ollama, no agent container)

- `.env.dev-claude` is the active config (copy from `.env.dev-claude.example`).
- `LLM_PROVIDER=claude`, requires `ANTHROPIC_API_KEY`. Model via `CLAUDE_MODEL` (default `claude-sonnet-4-6`).
- The agent and MCP server run **as host Python processes** (typically VS Code → *"Stack debug — Claude"*), not in Docker.
- `MCP_SERVER_URL=http://localhost:8080/mcp` (not the compose-internal `http://ckan-mcp:8080/mcp`).
- No Ollama container is started; the Ollama service in `docker-compose.yml` is irrelevant here.

A third provider, `azure_foundry`, exists for cloud deploys (Azure Container Apps) and uses `AZURE_AI_PROJECT_ENDPOINT` + `AZURE_AI_MODEL_DEPLOYMENT_NAME` via `DefaultAzureCredential`. It is the default in Bicep deploys; locally it's an opt-in.

When editing provider-selection code (`ckan_agent/factory.py`, `config.py`) verify all three branches still build. When editing env handling, update all three of `.env.example`, `.env.dev-claude.example`, `.env.azure.example` so they stay in sync.

## Commands

```bash
# Stack lifecycle (Ollama profile)
make up            # CPU stack
make up-gpu        # NVIDIA stack
make down          # stop everything (both profiles)
make ps / logs     # status / tail logs
make rebuild       # rebuild ckan-mcp + ckan-agent images, no cache
make build-ollama  # bake the Ollama image with qwen2.5:16k locally
make pull-models   # fallback when Ollama image has no baked model

# Interactive agent against the running stack
make agent

# Lint + test both Python packages
make lint
make test

# Single test
cd ckan-mcp-agent  && pytest -q tests/test_api_parsing.py::test_name
cd ckan-mcp-server && pytest -q tests/test_ckan_client.py
```

Per-package editable installs (note `--pre` — `agent-framework` is pre-release):

```bash
cd ckan-mcp-server && pip install -e ".[dev]"
cd ckan-mcp-agent  && pip install --pre -e ".[dev,azure]"
```

Run a service standalone:

```bash
# MCP server only, HTTP
cd ckan-mcp-server && TRANSPORT=streamable-http PORT=8080 ckan-mcp-server

# MCP server only, stdio (for Claude Desktop)
cd ckan-mcp-server && TRANSPORT=stdio ckan-mcp-server

# Agent only (requires MCP + an LLM reachable)
cd ckan-mcp-agent && ckan-agent           # REPL
cd ckan-mcp-agent && ckan-agent-api       # FastAPI on :8002
```

## Architecture notes that span files

- **Per-call `base_url` is the design contract.** Every MCP tool in `ckan_mcp/tools.py` takes an optional `base_url`; when omitted, `CkanClient` falls back to `CKAN_DEFAULT_BASE_URL`. Portal selection happens at two layers: (1) `ckan_agent/factory.py::detect_region` prepends an explicit `PORTAL_HINT` line for Italian regional portals it recognises by regex; (2) for everything else the LLM picks one portal from the international list embedded in `AGENT_INSTRUCTIONS` (`ckan_agent/config.py`) based on the query language and scope. The UI no longer ships a portal selector. Do not hard-code portals in the server.
- **Agent output contract.** The agent is instructed to produce a narrative paragraph followed by a `<!--RESOURCES_JSON-->…<!--/RESOURCES_JSON-->` block. `ckan_agent/api.py` parses this into `{text, resources[]}`. The narrative MUST NOT contain URLs; resources carry `content` only for CSV / JSON / GeoJSON / TXT (other formats → `null`). If the LLM fails to emit the block, the API falls back to `text = raw reply, resources = []`. Tests for this live in `tests/test_api_parsing.py` and `tests/test_fill_missing_content.py`.
- **Transport dispatch.** `ckan_mcp/server.py` switches between `stdio`, `streamable-http`, and `sse` based on `TRANSPORT`. The Docker image runs `streamable-http`; Claude Desktop integrations run `stdio`. Tools and the CKAN client are transport-agnostic.
- **CkanError surface.** `ckan_mcp/ckan_client.py` raises a single `CkanError` for transport failure, non-2xx, non-JSON, or `success=false`. Keep that contract — `tools.py` only handles `CkanError`.
- **CI matrix.** `.github/workflows/ci.yml` runs ruff + pytest **per package** in a matrix, then a buildx docker build for both images. `docker-publish.yml` pushes multi-arch images to GHCR. `deploy-azure.yml` does OIDC → `az acr build` → Bicep deploy of two Container Apps.

## Things easy to get wrong

- `OLLAMA_LLM_MODEL` must match the modelfile *tag* baked in the Ollama image (`qwen2.5:16k`), not the base model name (`qwen2.5:7b-instruct`).
- `MCP_SERVER_URL` is `http://ckan-mcp:8080/mcp` inside the compose network but `http://localhost:8080/mcp` for host-side debug. Pick the right one for the active `.env*` file.
- When changing provider plumbing, also touch `factory.py` (build path), `config.py` (settings + the `Provider` literal), and the three `.env*.example` files.
- Don't strip `--pre` from the agent install — `agent-framework` is published as a pre-release.
