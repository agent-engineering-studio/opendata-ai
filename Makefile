SHELL := /bin/bash

COMPOSE := docker compose
OLLAMA_BASE_MODEL ?= qwen2.5:7b-instruct
OLLAMA_NUM_CTX   ?= 16384
OLLAMA_MODEL     ?= qwen2.5:16k
OLLAMA_IMAGE     ?= ghcr.io/agent-engineering-studio/ckan-mcp-ollama:latest

.DEFAULT_GOAL := help

# ──────────────────────────── Helpers ────────────────────────────

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ──────────────────────────── Local stack ────────────────────────

.PHONY: up up-cpu up-gpu
up: up-cpu ## Start the stack (CPU profile — default)

up-cpu: ## Start the stack with CPU-only Ollama
	$(COMPOSE) --profile cpu up -d

up-gpu: ## Start the stack with GPU-enabled Ollama
	$(COMPOSE) --profile gpu up -d

.PHONY: down logs ps
down: ## Stop the stack
	$(COMPOSE) --profile cpu --profile gpu down

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

.PHONY: build-ollama
build-ollama: ## Build the Ollama image with $(OLLAMA_MODEL) baked in (local, ~7 GB)
	docker build \
	  --build-arg BASE_MODEL=$(OLLAMA_BASE_MODEL) \
	  --build-arg NUM_CTX=$(OLLAMA_NUM_CTX) \
	  --build-arg MODEL_TAG=$(OLLAMA_MODEL) \
	  -t $(OLLAMA_IMAGE) \
	  infra/ollama

.PHONY: pull-models
pull-models: ## Fallback: pull model directly into a running ckan-ollama container (no prebuild image)
	@echo "Pulling base model $(OLLAMA_BASE_MODEL)..."
	docker exec ckan-ollama ollama pull $(OLLAMA_BASE_MODEL)
	@echo "Creating $(OLLAMA_MODEL) with num_ctx=$(OLLAMA_NUM_CTX)..."
	docker exec ckan-ollama bash -c 'printf "FROM $(OLLAMA_BASE_MODEL)\nPARAMETER num_ctx $(OLLAMA_NUM_CTX)\n" > /tmp/Modelfile && ollama create $(OLLAMA_MODEL) -f /tmp/Modelfile'
	@echo "Done — model $(OLLAMA_MODEL) ready with context $(OLLAMA_NUM_CTX)"

.PHONY: rebuild rebuild-all
rebuild: ## Rebuild mcp + agent images without cache
	$(COMPOSE) build --no-cache ckan-mcp ckan-agent

rebuild-all: build-ollama rebuild ## Rebuild ALL images: Ollama (baked model, ~7 GB) + mcp + agent

.PHONY: refresh-ollama refresh-gpu refresh

refresh-gpu: rebuild down up-gpu
	@echo "Stack refreshed with GPU-enabled Ollama and rebuilt images"



refresh: rebuild down up
	@echo "Stack refreshed with CPU-only Ollama and rebuilt images"

# ──────────────────────────── Interactive ────────────────────────

.PHONY: agent
agent: ## Launch the interactive agent CLI against the running stack
	docker run --rm -it --network ckan-mcp_default \
	  -e LLM_PROVIDER=ollama \
	  -e OLLAMA_BASE_URL=http://ckan-ollama:11434 \
	  -e OLLAMA_LLM_MODEL=$(OLLAMA_MODEL) \
	  -e MCP_SERVER_URL=http://ckan-mcp:8080/mcp \
	  ckan-mcp-agent:local ckan-agent

# ──────────────────────────── Dev tasks ──────────────────────────

.PHONY: lint test
lint: ## Run ruff on both packages
	cd ckan-mcp-server && ruff check src
	cd ckan-mcp-agent && ruff check src

test: ## Run pytest on both packages
	cd ckan-mcp-server && pytest -q
	cd ckan-mcp-agent && pytest -q
