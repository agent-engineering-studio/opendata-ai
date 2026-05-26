# mcp-ckan

Read **any** CKAN open data portal through a local **MCP server**, consumed by a **Microsoft Agent Framework** agent backed by **Ollama** (local), **Azure AI Foundry** (cloud), or **Anthropic Claude**.

The repository ships a complete, reproducible stack — a Python MCP server that wraps the CKAN Action API, a chat agent that uses it as a tool, Docker Compose for local development (with optional GPU Ollama), Bicep + scripts for deployment on Azure Container Apps, and GitHub Actions for CI and OIDC-based CD.

Inspired by [ondata/ckan-mcp-server](https://github.com/ondata/ckan-mcp-server); aligned operationally with [agent-engineering-studio/knowledge-graph](https://github.com/agent-engineering-studio/knowledge-graph).

---

## Table of contents

- [Why this project](#why-this-project)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start — local with Ollama](#quick-start--local-with-ollama)
- [Use from Claude Desktop (stdio)](#use-from-claude-desktop-stdio)
- [Tools exposed over MCP](#tools-exposed-over-mcp)
- [Agent usage](#agent-usage)
- [Configuration reference](#configuration-reference)
- [Deploy on Azure](#deploy-on-azure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [References](#references)
- [License](#license)

---

## Why this project

CKAN is the dominant platform for national and regional open data portals (dati.gov.it, data.gov.uk, data.gov, open.canada.ca, data.gov.au, and many more). Each portal exposes the same **Action API** shape (`/api/3/action/*`), which makes it a natural fit for a single MCP server that can serve **any** portal on demand — callers pass a `base_url` per request, or rely on a server-wide default.

The repository demonstrates an end-to-end **agent-over-MCP** pattern:

- **MCP server** (`ckan-mcp-server/`) — a small Python service built on the official [FastMCP](https://github.com/modelcontextprotocol/python-sdk) runtime. It exposes 11 CKAN actions as tools over **stdio** (for local MCP hosts like Claude Desktop) or **Streamable HTTP** (for container deployment).
- **Agent** (`ckan-mcp-agent/`) — a [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) `Agent` that plugs the MCP server in as an `MCPStreamableHTTPTool`, reasons with an LLM (Ollama, Azure AI Foundry, or Claude), and speaks both a CLI and a small FastAPI surface.
- **Ops** — Docker Compose (CPU/GPU profiles), Bicep templates for Azure Container Apps + ACR + UAMI, Bash and PowerShell deploy scripts, and GitHub Actions for CI (lint + test + docker build) and CD (OIDC federation, ACR tasks, ARM deployment).

---

## Architecture

```
 ┌─────────────────┐        ┌───────────────────────────┐        ┌──────────────────┐
 │  User / Client  │ chat → │  ckan-mcp-agent (FastAPI) │ tools→ │  ckan-mcp-server │
 │ (curl, REPL,    │        │  Microsoft Agent Framework│  MCP   │   (FastMCP)      │
 │  Claude Desktop)│ ←reply │  Agent + MCP tool         │ ←──    │  stdio / http    │
 └─────────────────┘        └─────────────┬─────────────┘        └────────┬─────────┘
                                          │ LLM                           │ HTTPS
                                          ▼                               ▼
                          ┌────────────────────────────┐        ┌──────────────────┐
                          │ Ollama / Azure AI Foundry  │        │  CKAN Action API │
                          │        / Claude            │        │ /api/3/action/*  │
                          └────────────────────────────┘        └──────────────────┘
```

**Cloud topology** (Azure Container Apps): one external Container App for the MCP server, one for the agent — both pulling from ACR via a User-Assigned Managed Identity with `AcrPull`, with Log Analytics behind the Container Apps Environment. In the cloud the default `LLM_PROVIDER` is `azure_foundry`; Ollama is kept for local dev.

---

## Repository layout

| Path                       | Role                                                                                           |
|----------------------------|------------------------------------------------------------------------------------------------|
| `ckan-mcp-server/`         | Python MCP server (FastMCP) — stdio + Streamable HTTP. Wraps the CKAN Action API.              |
| `ckan-mcp-server/src/ckan_mcp/ckan_client.py` | Async CKAN HTTP client (`httpx`) with per-call `base_url` resolution.                |
| `ckan-mcp-server/src/ckan_mcp/tools.py`       | Tool definitions registered on the FastMCP instance.                                 |
| `ckan-mcp-server/src/ckan_mcp/server.py`      | Transport dispatcher (`stdio` / `streamable-http` / `sse`).                          |
| `ckan-mcp-agent/`          | Python Microsoft Agent Framework client — CLI + FastAPI, consumes the MCP server.              |
| `ckan-mcp-agent/src/ckan_agent/factory.py`    | Builds the chat client + `AgentSession` async context manager with the MCP tool.     |
| `ckan-mcp-agent/src/ckan_agent/main.py`       | `ckan-agent` CLI entry point — interactive REPL or one-shot query.                   |
| `ckan-mcp-agent/src/ckan_agent/api.py`        | `ckan-agent-api` FastAPI app (`GET /health`, `POST /chat`).                          |
| `docker-compose.yml`       | Full local stack: Ollama (CPU/GPU profiles) + MCP server + Agent, sharing one Docker network. |
| `Makefile`                 | Shortcuts: `up`, `up-gpu`, `down`, `logs`, `pull-models`, `agent`, `lint`, `test`, `rebuild`. |
| `infra/bicep/main.bicep`   | Azure IaC entry point: ACR + Container Apps Environment + 2 Container Apps + UAMI.             |
| `infra/bicep/modules/`     | Reusable Bicep modules (`acr`, `container-apps-env`, `container-app`, `identity`).             |
| `infra/scripts/`           | Parameterised deploy + destroy scripts, plus `setup-github-oidc.sh`, in Bash and PowerShell.   |
| `.github/workflows/ci.yml` | CI: ruff + pytest matrix across both packages, then Docker buildx for both images.             |
| `.github/workflows/docker-publish.yml` | Publish multi-arch images to **GitHub Container Registry** (GHCR) on push / tags.   |
| `.github/workflows/deploy-azure.yml` | CD: Azure OIDC login, ACR Tasks build, Bicep deploy, restart + healthcheck.         |
| `.env.local.example`       | Template for LOCAL DEBUG (default: `LLM_PROVIDER=ollama`; opt-in to claude for host debug).   |
| `.env.production.example`  | Template for PRODUCTION (`LLM_PROVIDER=claude` by default, `azure_foundry` as variant B).     |

---

## Quick start — local with Ollama

Prerequisites: Docker + Docker Compose, GNU Make (optional but convenient). An NVIDIA GPU is optional and only used if you select the `gpu` profile.

```bash
# 1. Prep env
cp .env.local.example .env

# 2. Bring up the stack (CPU by default; use `make up-gpu` with an NVIDIA GPU)
make up

# 3. Pull the LLM into Ollama (first run only; large download)
make pull-models                           # defaults to qwen3:8b

# 4. Open an interactive agent session
make agent
```

Endpoints exposed on the host:

| Service              | URL                              | Notes                                                |
|----------------------|----------------------------------|------------------------------------------------------|
| CKAN MCP server      | `http://localhost:8080/mcp`      | Streamable HTTP JSON-RPC. Try `tools/list`.          |
| Agent API (FastAPI)  | `http://localhost:8002`          | `GET /health`, `POST /chat` (see payload below).     |
| Web UI               | `http://localhost:3000`          | Chat demo (Next.js). Talks to the agent via `/api/chat`. |
| Ollama               | `http://localhost:11434`         | OpenAI-compatible endpoint is at `/v1`.              |

Quick `curl` test of the agent:

```bash
curl -X POST http://localhost:8002/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"Mostrami i dettagli del dataset 2908fe96-58c4-40fe-8b29-9d4d78715ba7"}'
```

Probe the MCP server directly (no agent):

```bash
curl -s -X POST http://localhost:8080/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

Useful `make` targets:

```bash
make ps            # show service status
make logs          # tail compose logs
make down          # stop everything
make rebuild       # rebuild mcp + agent images without cache
```

---

## Use from Claude Desktop (stdio)

The MCP server also runs over stdio, which is what Claude Desktop and similar MCP hosts expect. Two supported patterns:

**A. Invoke the Docker image directly** — no Python installation needed:

```json
{
  "mcpServers": {
    "ckan": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "TRANSPORT=stdio", "ckan-mcp-server:local"],
      "env": { "CKAN_DEFAULT_BASE_URL": "https://www.dati.gov.it/opendata" }
    }
  }
}
```

**B. Invoke the installed Python entry point** — after `pip install -e .` in `ckan-mcp-server/`:

```json
{
  "mcpServers": {
    "ckan": {
      "command": "ckan-mcp-server",
      "env": { "CKAN_DEFAULT_BASE_URL": "https://data.gov.uk" }
    }
  }
}
```

Any MCP host that supports stdio + MCP 1.x should work (Cursor, Continue, etc.).

---

## Tools exposed over MCP

All tools accept an optional `base_url`, so the same server can target **any** CKAN portal (`dati.gov.it`, `data.gov.uk`, `data.gov`, `open.canada.ca`, `data.gov.au`, …). When `base_url` is omitted, `CKAN_DEFAULT_BASE_URL` is used.

| Tool                        | CKAN action            | Key arguments                                                                 |
|-----------------------------|------------------------|-------------------------------------------------------------------------------|
| `ckan_status_show`          | `status_show`          | `base_url` — portal metadata (version, extensions, site title).               |
| `ckan_site_read`            | `site_read`            | `base_url` — confirms public read access.                                     |
| `ckan_package_search`       | `package_search`       | `q` (Solr), `fq`, `rows`, `start`, `sort`, `base_url`.                        |
| `ckan_package_show`         | `package_show`         | `id` (name or UUID), `base_url`.                                              |
| `ckan_organization_list`    | `organization_list`    | `all_fields`, `limit`, `base_url`.                                            |
| `ckan_organization_show`    | `organization_show`    | `id`, `include_datasets`, `base_url`.                                         |
| `ckan_group_list`           | `group_list`           | `all_fields`, `limit`, `base_url`.                                            |
| `ckan_group_show`           | `group_show`           | `id`, `include_datasets`, `base_url`.                                         |
| `ckan_tag_list`             | `tag_list`             | `query`, `all_fields`, `base_url`.                                            |
| `ckan_datastore_search`     | `datastore_search`     | `resource_id` (UUID), `q`, `limit`, `offset`, `filters`, `base_url`.          |
| `ckan_datastore_search_sql` | `datastore_search_sql` | `sql` (read-only SELECT; table name is the resource UUID), `base_url`.        |

Error handling: when CKAN returns `success=false`, transport fails, or the response is not JSON, the server raises `CkanError`. Non-2xx ≥ 500 are surfaced with a truncated body excerpt.

---

## Agent usage

### CLI — `ckan-agent`

```bash
# Editable install (use [azure] extra for Azure AI Foundry auth helpers)
cd ckan-mcp-agent && pip install --pre -e ".[dev,azure]"

ckan-agent                                      # interactive REPL (rich panel)
ckan-agent "List the 5 most recent datasets on https://data.gov.uk"
ckan-agent --provider azure_foundry "…"         # override provider for this invocation
ckan-agent --mcp-url http://localhost:8080/mcp "…"
```

Quit the REPL with `/quit`, `/exit`, `:q`, or Ctrl-D.

### HTTP API — `ckan-agent-api`

```bash
ckan-agent-api                                  # binds 0.0.0.0:8002 by default
```

| Method | Path      | Body / Query                                                                 |
|--------|-----------|------------------------------------------------------------------------------|
| GET    | `/health` | —                                                                            |
| POST   | `/chat`   | `{"query": "…", "base_url": "https://…"}` — `base_url` is optional.           |

#### `POST /chat` response format

The response is structured JSON with a pure narrative `text` field and a `resources` array — one entry per dataset resource found:

```json
{
  "text": "Ho trovato il dataset 'Stazioni di ricarica auto elettriche' pubblicato dal Comune di Milano (CC BY 4.0).",
  "resources": [
    {
      "name": "stazioni_ricarica.csv",
      "url": "https://dati.comune.milano.it/.../stazioni_ricarica.csv",
      "format": "CSV",
      "content": "id,lat,lon,tipo_presa\n1,45.46,9.19,CCS\n..."
    },
    {
      "name": "Mappa stazioni",
      "url": "https://dati.comune.milano.it/.../stazioni.shp",
      "format": "SHP",
      "content": null
    }
  ]
}
```

- **`text`** — narrative only; never contains resource URLs or file content.
- **`resources`** — every resource found, any format. `content` is populated for CSV, JSON, GeoJSON, and TXT; `null` for all other formats (PDF, SHP, XLSX, WMS, KML, ZIP, …).
- If the LLM does not emit a parseable resource block, `resources` is `[]` and `text` contains the full raw reply (graceful fallback).

#### Test queries

The `requests/` folder ships ready-to-use query sets:

| File | Tool | Coverage |
| ---- | ---- | -------- |
| `requests/agent-chat.http` | VS Code REST Client | 84 queries across 13 thematic categories |
| `requests/postman/ckan-mcp-agent.postman_collection.json` | Postman | Same 84 queries as a Postman collection |
| `requests/postman/test-agent-chat.sh` | bash + curl | All 84 queries — automated pass/fail with summary |
| `requests/postman/test-agent-chat.ps1` | PowerShell | All 84 queries — same, coloured output |

Run the bash suite:

```bash
# against local stack (default)
bash requests/postman/test-agent-chat.sh

# against Azure Container Apps
bash requests/postman/test-agent-chat.sh https://<agent-fqdn>
```

Run the PowerShell suite:

```powershell
./requests/postman/test-agent-chat.ps1
# or
./requests/postman/test-agent-chat.ps1 -BaseUrl https://<agent-fqdn>
```

The agent is instructed to always cite portal URLs, dataset names and resource IDs, and to prefer concrete facts over speculation (see `agent_instructions` in `src/ckan_agent/config.py`).

---

## Configuration reference

All configuration is environment-driven; `.env` is auto-loaded by `pydantic-settings`.

### Agent (`ckan-mcp-agent`)

| Variable                           | Default                              | Description                                                                 |
|------------------------------------|--------------------------------------|-----------------------------------------------------------------------------|
| `LLM_PROVIDER`                     | `ollama`                             | One of `ollama`, `azure_foundry`, `claude`.                                 |
| `MCP_SERVER_URL`                   | `http://localhost:8080/mcp`          | Streamable HTTP endpoint of the MCP server.                                 |
| `MCP_SERVER_NAME`                  | `ckan`                               | Logical name used inside the agent.                                         |
| `CKAN_DEFAULT_BASE_URL`            | `https://www.dati.gov.it/opendata`   | Default portal hint surfaced to the LLM.                                    |
| `OLLAMA_BASE_URL`                  | `http://localhost:11434`             | In Compose, resolves to `http://opendata-ai-ollama:11434`.                  |
| `OLLAMA_LLM_MODEL`                 | `qwen3:8b`                           | Any model pulled into Ollama.                                               |
| `AZURE_AI_PROJECT_ENDPOINT`        | —                                    | Required when `LLM_PROVIDER=azure_foundry`.                                 |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME`   | —                                    | Model deployment name for Azure AI Foundry.                                 |
| `ANTHROPIC_API_KEY`                | —                                    | Required when `LLM_PROVIDER=claude`.                                        |
| `CLAUDE_MODEL`                     | `claude-sonnet-4-6`                  | Anthropic model id.                                                         |
| `AGENT_NAME`                       | `CkanAgent`                          | Name passed to `Agent`.                                                     |
| `AGENT_INSTRUCTIONS`               | *(see `config.py`)*                  | System prompt — override to change agent behaviour.                         |
| `API_HOST` / `API_PORT`            | `0.0.0.0` / `8002`                   | FastAPI bind.                                                               |
| `LOG_LEVEL`                        | `INFO`                               | Standard Python logging level.                                              |

### MCP server (`ckan-mcp-server`)

| Variable                | Default                              | Description                                                      |
|-------------------------|--------------------------------------|------------------------------------------------------------------|
| `TRANSPORT`             | `stdio`                              | `stdio` \| `streamable-http` \| `sse`.                           |
| `HOST` / `PORT`         | `0.0.0.0` / `8080`                   | Only used by HTTP transports.                                    |
| `MCP_PATH`              | `/mcp`                               | Mount path for Streamable HTTP.                                  |
| `CKAN_DEFAULT_BASE_URL` | `https://www.dati.gov.it/opendata`   | Fallback portal when a tool omits `base_url`.                    |
| `CKAN_HTTP_TIMEOUT`     | `30`                                 | Per-request timeout (seconds).                                   |
| `CKAN_USER_AGENT`       | `ckan-mcp-server/0.1 …`              | UA header sent to every CKAN portal.                             |
| `LOG_LEVEL`             | `INFO`                               |                                                                  |

---

## Deploy on Azure

Default target: **Azure Container Apps** (scale-to-zero, HTTPS ingress) + **ACR** + **Log Analytics** + **User-Assigned Managed Identity** with `AcrPull`. Two Container Apps — one for the MCP server, one for the agent — both externally reachable; the agent calls the MCP server via its container app FQDN.

> In the cloud Ollama is impractical at this scale; the agent is wired to **Azure AI Foundry** by default (`LLM_PROVIDER=azure_foundry`). Keep Ollama for local dev.

### 1. One-off setup — GitHub OIDC federation

From a machine with `az` CLI and Owner / User-Access-Admin on the subscription:

```bash
./infra/scripts/setup-github-oidc.sh \
  --subscription 00000000-0000-0000-0000-000000000000 \
  --resource-group rg-ckan-mcp-dev \
  --github-org agent-engineering-studio \
  --github-repo mcp-ckan
```

Add the printed `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` as **GitHub repo secrets**. Then add these application **secrets** as needed:

- `ANTHROPIC_API_KEY` (only if `LLM_PROVIDER=claude`)

And these **repo variables**:

- `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`
- `ACR_NAME`, `AZURE_LOCATION`, `AZURE_ENV_NAME`
- `CKAN_DEFAULT_BASE_URL`

### 2. Deploy from the GitHub Action

`Actions → deploy-azure → Run workflow`, fill the inputs (all have sensible defaults):

```
subscription_id  : 00000000-...
resource_group   : rg-ckan-mcp-dev
location         : westeurope
env_name         : dev
acr_name         : ckanmcpdev
image_tag        : latest           # or a specific SHA
llm_provider     : azure_foundry
ckan_default_url : https://www.dati.gov.it/opendata
```

The workflow: logs in with OIDC → ensures RG + ACR → runs `az acr build` for both images → `az deployment group create` on `main.bicep` → restarts both Container Apps → hits `/health` on the agent and reports URLs in the job summary.

### 3. Deploy from the local CLI

Bash:

```bash
cp .env.production.example .env.production
# edit .env.production — uncomment Variant B (azure_foundry) + the Azure deploy block
set -a ; source .env.production ; set +a

./infra/scripts/deploy.sh \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --location westeurope \
  --env-name dev \
  --acr-name "$ACR_NAME" \
  --azure-openai-endpoint "$AZURE_AI_PROJECT_ENDPOINT" \
  --azure-openai-api-key "$AZURE_AI_MODEL_DEPLOYMENT_NAME"
```

PowerShell:

```powershell
./infra/scripts/deploy.ps1 `
  -SubscriptionId  '<subscription-id>' `
  -ResourceGroup   'rg-ckan-mcp-dev' `
  -Location        'westeurope' `
  -EnvName         'dev' `
  -AcrName         'ckanmcpdev' `
  -AzureOpenAIEndpoint 'https://<your-endpoint>.services.ai.azure.com/' `
  -AzureOpenAIApiKey   $env:AZURE_AI_MODEL_DEPLOYMENT_NAME
```

Both scripts:

1. `az account set --subscription …`
2. `az group create` + `az acr create` (idempotent)
3. `az acr build` → pushes `ckan-mcp-server:<tag>` and `ckan-mcp-agent:<tag>`
4. `az deployment group create` against `infra/bicep/main.bicep`
5. Force a new revision of each Container App and print URLs

Skip the image build (e.g. re-deploy Bicep only) with `--skip-build` / `-SkipBuild`.

### 4. Tear down

```bash
./infra/scripts/destroy.sh --subscription <id> --resource-group rg-ckan-mcp-dev --yes
# or
./infra/scripts/destroy.ps1 -SubscriptionId <id> -ResourceGroup rg-ckan-mcp-dev -Yes
```

---

## Development

### Tooling

```bash
make lint             # ruff on both packages
make test             # pytest on both packages
make rebuild          # rebuild images without cache
```

### Per-package editable installs

```bash
cd ckan-mcp-server && pip install -e ".[dev]"
cd ckan-mcp-agent  && pip install --pre -e ".[dev,azure]"
```

The agent depends on `agent-framework` which is currently published as a pre-release — hence `--pre`. The `[azure]` extra pulls `azure-identity` for `DefaultAzureCredential`.

### Running just one service

```bash
# Only the MCP server, over HTTP
cd ckan-mcp-server
TRANSPORT=streamable-http PORT=8080 ckan-mcp-server

# Only the MCP server, over stdio (pipe into your MCP host)
cd ckan-mcp-server
TRANSPORT=stdio ckan-mcp-server

# Only the agent (expects an MCP server + LLM available)
cd ckan-mcp-agent
MCP_SERVER_URL=http://localhost:8080/mcp \
  LLM_PROVIDER=ollama \
  OLLAMA_BASE_URL=http://localhost:11434 \
  ckan-agent
```

### CI

`.github/workflows/ci.yml` runs on pushes and PRs to `main`:

- `lint-and-test` — matrix over both packages: editable install, `ruff check src`, `pytest -q` if `tests/` exists.
- `docker-build` — buildx build for both images with GitHub Actions cache.

### Publishing images to GHCR

`.github/workflows/docker-publish.yml` builds and pushes **multi-arch** (`linux/amd64`, `linux/arm64`) images to **GitHub Container Registry** whenever code under `ckan-mcp-server/`, `ckan-mcp-agent/` or the workflow itself changes on `main`, on semver tags `vX.Y.Z`, or via manual dispatch.

Images are published as:

```
ghcr.io/<owner>/ckan-mcp-server:<tag>
ghcr.io/<owner>/ckan-mcp-agent:<tag>
```

Tags generated automatically by [`docker/metadata-action`](https://github.com/docker/metadata-action):

| Trigger                | Tags produced                                                                 |
|------------------------|-------------------------------------------------------------------------------|
| Push to `main`         | `main`, `sha-<short>`, `latest`                                               |
| Tag `v1.2.3`           | `1.2.3`, `1.2`, `1`, `sha-<short>`                                            |
| Pull request           | `pr-<number>`, `sha-<short>`                                                  |
| `workflow_dispatch`    | `sha-<short>` (plus `latest` when `push_latest=true`)                         |

Authentication uses the built-in `GITHUB_TOKEN` (no PAT required). The workflow also emits **provenance** and **SBOM** attestations. Make the package public (or grant read access) from the repository's *Packages* page if you want to pull anonymously.

Pull and run:

```bash
# Pull the MCP server and start it over HTTP
docker run --rm -p 8080:8080 \
  -e CKAN_DEFAULT_BASE_URL=https://data.gov.uk \
  ghcr.io/<owner>/ckan-mcp-server:latest

# Or wire it into Claude Desktop over stdio
docker run --rm -i -e TRANSPORT=stdio \
  ghcr.io/<owner>/ckan-mcp-server:latest
```

To consume the published image from Docker Compose, override `image:` and drop `build:` in `docker-compose.yml`.

---

## Troubleshooting

| Symptom                                                              | Likely cause / fix                                                                                          |
|----------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| `CkanError: Transport error calling status_show on …`                | Portal unreachable or TLS issue. Verify with `curl "$URL/api/3/action/status_show"`.                        |
| `CkanError: Unexpected CKAN response shape`                          | Portal returned HTML (often a login wall or WAF). Try a different endpoint or authentication.               |
| `CkanError: CKAN action 'package_search' failed`                     | Invalid Solr query or filter. Check `fq`/`q` syntax against the CKAN docs.                                  |
| Agent replies with "I don't have tools"                              | `MCP_SERVER_URL` wrong or MCP server not reachable. Hit `tools/list` manually (see Quick start).            |
| `RuntimeError: AZURE_AI_PROJECT_ENDPOINT is required when LLM_PROVIDER=azure_foundry` | Set `AZURE_AI_PROJECT_ENDPOINT`, or change `LLM_PROVIDER`.                                        |
| Ollama healthcheck flapping on first boot                            | Model is still being pulled. Run `make pull-models` and wait — `start_period` is 20s.                       |
| Azure deploy fails with `Image not found` on first run               | ACR is fresh and `imageTag=latest` doesn't exist yet. Re-run; the workflow pushes `:<sha>` and `:latest`.   |
| `Healthcheck agent failed` in the GitHub Action                      | Cold start of the agent Container App took > 60s. Re-run the workflow or check agent logs in Log Analytics. |

Useful one-liners:

```bash
# Verify the MCP server can talk to a portal
docker compose exec ckan-mcp python -c "\
import asyncio; from ckan_mcp.ckan_client import CkanClient; \
print(asyncio.run((lambda: (lambda c: c.__aenter__().__await__())(CkanClient()))))"

# List the tools the agent actually sees
curl -s -X POST http://localhost:8080/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' | jq '.result.tools[].name'
```

---

## References

- [Model Context Protocol — Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP, transports)
- [Microsoft Agent Framework](https://learn.microsoft.com/agent-framework/) and [Local MCP tools](https://learn.microsoft.com/agent-framework/agents/tools/local-mcp-tools?pivots=programming-language-csharp)
- [CKAN Action API reference](https://docs.ckan.org/en/latest/api/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/)
- [GitHub OIDC federation with Azure](https://learn.microsoft.com/azure/developer/github/connect-from-azure)

---

## License

MIT — see [LICENSE](LICENSE).
