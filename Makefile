SHELL := /bin/bash

# `ENV_FILE` is the docker-compose env file all targets read by default.
# Override on the command line:  `make ENV_FILE=.env.production up-host-ollama`
ENV_FILE ?= .env.local

COMPOSE := docker compose --env-file $(ENV_FILE)

# Profili compose opzionali extra (es. web). Uso: `make up PROFILES="web"`.
PROFILES ?=
_PROFILE_FLAGS := $(foreach p,$(PROFILES),--profile $(p))

# Overpass self-hosted incluso nel `make up` di default. Spegnilo con
# `make up OVERPASS=0` (resta avviabile a parte con `make overpass-up`).
# Pesante: ~25-50GB di disco e init ~1-2h alla PRIMA accensione (download .pbf
# Italia + build del DB). Vedi infra/overpass/README.md.
OVERPASS ?= 1
ifeq ($(OVERPASS),1)
_OVERPASS_PROFILE := --profile overpass
_OVERPASS_SVC := overpass
endif
# Baked Ollama model. Default qwen2.5:32b → qwen2.5:32k (num_ctx 16384,
# temperature 0) for best faithfulness on a 48GB Apple-Silicon box; override
# e.g. `make build-ollama OLLAMA_BASE_MODEL=qwen2.5:14b OLLAMA_MODEL=qwen2.5:14k`.
OLLAMA_BASE_MODEL ?= qwen2.5:32b
OLLAMA_NUM_CTX   ?= 16384
OLLAMA_TEMPERATURE ?= 0
OLLAMA_MODEL     ?= qwen2.5:32k
OLLAMA_IMAGE     ?= ghcr.io/agent-engineering-studio/opendata-ai-ollama:latest

# Custom-built compose services (skip the Ollama service — it uses a pre-built image
# managed by `make build-ollama` / `make pull-models`, not by `docker compose build`).
CUSTOM_SERVICES := ckan-mcp istat-mcp opencoesione-mcp ispra-mcp osm-mcp web-mcp opendata-backend opendata-ai-ui

# `make agent` launches the unified backend REPL against the running stack.
SOURCE ?= backend
COMPOSE_PROJECT ?= opendata-ai

.DEFAULT_GOAL := help

# ──────────────────────────── Helpers ────────────────────────────

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ──────────────────────────── Local stack ────────────────────────

.PHONY: up up-cpu up-gpu up-host-ollama up-claude
up: up-cpu ## Start the stack (CPU profile — default)

up-cpu: ## Start the stack with CPU-only Ollama (Dockerized)
	$(COMPOSE) --profile cpu $(_OVERPASS_PROFILE) $(_PROFILE_FLAGS) up -d

up-gpu: ## Start the stack with GPU-enabled Ollama (Linux + NVIDIA only)
	$(COMPOSE) --profile gpu $(_OVERPASS_PROFILE) $(_PROFILE_FLAGS) up -d

up-host-ollama: ## Start the stack against a host-installed Ollama (NO Docker Ollama). Best on macOS for Metal GPU.
	@if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then \
		echo "⚠️  Host Ollama not reachable at http://localhost:11434 — start it with: ollama serve &"; \
		exit 1; \
	fi
	@echo "✅ Host Ollama reachable. Bringing up stack without the Ollama container…"
	$(COMPOSE) up -d $(CUSTOM_SERVICES) $(_OVERPASS_SVC)

up-claude: ## Start the stack with LLM_PROVIDER=claude (no Ollama). Requires ANTHROPIC_API_KEY in $(ENV_FILE).
	@if ! grep -qE '^ANTHROPIC_API_KEY=.+' $(ENV_FILE); then \
		echo "⚠️  ANTHROPIC_API_KEY not set in $(ENV_FILE) — Claude provider needs it."; \
		exit 1; \
	fi
	@echo "✅ Using Claude as LLM provider. Bringing up stack without the Ollama container…"
	LLM_PROVIDER=claude $(COMPOSE) up -d $(CUSTOM_SERVICES) $(_OVERPASS_SVC)

.PHONY: down logs ps overpass-up overpass-logs
down: ## Stop the stack
	$(COMPOSE) --profile cpu --profile gpu --profile overpass --profile web down

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

overpass-up: ## Avvia (o aggiorna) solo l'istanza Overpass self-hosted
	$(COMPOSE) --profile overpass up -d overpass

overpass-logs: ## Segui i log di Overpass (utile durante l'init iniziale ~1-2h)
	$(COMPOSE) --profile overpass logs -f overpass

.PHONY: build-ollama
build-ollama: ## Build the Ollama image with $(OLLAMA_MODEL) baked in (local, ~7 GB)
	docker build \
	  --build-arg BASE_MODEL=$(OLLAMA_BASE_MODEL) \
	  --build-arg NUM_CTX=$(OLLAMA_NUM_CTX) \
	  --build-arg MODEL_TAG=$(OLLAMA_MODEL) \
	  --build-arg TEMPERATURE=$(OLLAMA_TEMPERATURE) \
	  -t $(OLLAMA_IMAGE) \
	  infra/ollama

.PHONY: pull-models
pull-models: ## Fallback: pull model directly into a running opendata-ai-ollama container (no prebuild image)
	@echo "Pulling base model $(OLLAMA_BASE_MODEL)..."
	docker exec opendata-ai-ollama ollama pull $(OLLAMA_BASE_MODEL)
	@echo "Creating $(OLLAMA_MODEL) with num_ctx=$(OLLAMA_NUM_CTX) temperature=$(OLLAMA_TEMPERATURE)..."
	docker exec opendata-ai-ollama bash -c 'printf "FROM $(OLLAMA_BASE_MODEL)\nPARAMETER num_ctx $(OLLAMA_NUM_CTX)\nPARAMETER temperature $(OLLAMA_TEMPERATURE)\n" > /tmp/Modelfile && ollama create $(OLLAMA_MODEL) -f /tmp/Modelfile'
	@echo "Done — model $(OLLAMA_MODEL) ready with context $(OLLAMA_NUM_CTX), temperature $(OLLAMA_TEMPERATURE)"

.PHONY: build build-svc rebuild rebuild-all
build: ## Build all custom images (mcp servers + agents + orchestrator + UI), reusing cache
	$(COMPOSE) build $(CUSTOM_SERVICES)

build-svc: ## Build a single service — usage: make build-svc SVC=istat-mcp
	@if [ -z "$(SVC)" ]; then echo "usage: make build-svc SVC=<service-name>  (one of: $(CUSTOM_SERVICES))" >&2; exit 2; fi
	$(COMPOSE) build $(SVC)

rebuild: ## Rebuild all custom images (mcp servers + agents + orchestrator + UI) WITHOUT cache
	$(COMPOSE) build --no-cache $(CUSTOM_SERVICES)

rebuild-all: build-ollama rebuild ## Rebuild ALL images: Ollama (baked model, ~7 GB) + every custom image (no cache)

.PHONY: refresh-ollama refresh-gpu refresh-cpu

refresh: rebuild down
	@echo "Stack refreshed with CPU-only Ollama and rebuilt images"

refresh-gpu: refresh up-gpu
	@echo "Stack refreshed with GPU-enabled Ollama and rebuilt images"

refresh-ollama: build-ollama refresh-gpu
	@echo "Ollama image rebuilt with model $(OLLAMA_MODEL) and context $(OLLAMA_NUM_CTX), stack refreshed with GPU profile"

refresh-cpu: refresh up
	@echo "Stack refreshed with CPU-only Ollama and rebuilt images"

# ──────────────────────────── Interactive ────────────────────────

.PHONY: agent agent-backend
agent: agent-$(SOURCE) ## Interactive REPL against the running stack

agent-backend: ## Launch the unified backend REPL against the running stack
	docker run --rm -it --network $(COMPOSE_PROJECT)_default \
	  -e LLM_PROVIDER=ollama \
	  -e OLLAMA_BASE_URL=http://opendata-ai-ollama:11434 \
	  -e OLLAMA_LLM_MODEL=$(OLLAMA_MODEL) \
	  -e CKAN_MCP_URL=http://ckan-mcp:8080/mcp \
	  -e ISTAT_MCP_URL=http://istat-mcp:8081/mcp \
	  -e OSM_MCP_URL=http://osm-mcp:8080/mcp \
	  opendata-backend:local opendata-agent

.PHONY: mcp-stdio-ckan mcp-stdio-istat mcp-stdio-osm mcp-stdio-opencoesione mcp-stdio-ispra mcp-stdio-web
mcp-stdio-ckan: ## Smoke-test the CKAN MCP server over stdio (one tools/list round-trip)
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e TRANSPORT=stdio ckan-mcp-server:local

mcp-stdio-istat: ## Smoke-test the ISTAT MCP server over stdio
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e TRANSPORT=stdio istat-mcp-server:local

mcp-stdio-opencoesione: ## Smoke-test the OpenCoesione MCP server over stdio
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e TRANSPORT=stdio opencoesione-mcp-server:local

mcp-stdio-ispra: ## Smoke-test the ISPRA MCP server over stdio
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e TRANSPORT=stdio ispra-mcp-server:local

mcp-stdio-web: ## Smoke-test the Web (SearXNG) MCP server over stdio
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e TRANSPORT=stdio web-mcp:local

.PHONY: oc-sync
oc-sync: ## Ingest the OpenCoesione bulk into Postgres (vars: OC_SYNC_ARGS="--regione PUG --ciclo 2014-2020")
	docker compose exec opendata-backend opendata-opencoesione-sync $(OC_SYNC_ARGS)

.PHONY: comuni-sync
comuni-sync: ## Popola l'anagrafica comuni (peer group della modalità idee)
	docker compose exec opendata-backend opendata-comuni-sync

mcp-stdio-osm: ## Smoke-test the OSM MCP server over stdio
	@echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
	  | docker run --rm -i -e MCP_TRANSPORT=stdio osm-mcp:local

# ──────────────────────────── Dev tasks ──────────────────────────

.PHONY: lint test
lint: ## Run ruff on all Python packages
	cd opendata_core && ruff check src
	cd ckan-mcp-server && ruff check src
	cd istat-mcp-server && ruff check src
	cd opencoesione-mcp-server && ruff check src
	cd ispra-mcp-server && ruff check src
	cd osm-mcp && ruff check src
	cd web-mcp && ruff check src
	cd opendata-backend && ruff check src

test: ## Run pytest on all Python packages
	cd opendata_core && pytest -q
	cd ckan-mcp-server && pytest -q
	cd istat-mcp-server && pytest -q
	cd opencoesione-mcp-server && pytest -q
	cd ispra-mcp-server && pytest -q
	cd osm-mcp && pytest -q
	cd web-mcp && pytest -q
	cd opendata-backend && pytest -q
