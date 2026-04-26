SHELL := /bin/bash

COMPOSE := docker compose
OLLAMA_BASE_MODEL ?= llama3.1:8b
OLLAMA_NUM_CTX   ?= 16384
OLLAMA_MODEL     ?= llama3.1:16k

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

.PHONY: pull-models
pull-models: ## Pull base model and create $(OLLAMA_MODEL) modelfile with num_ctx=$(OLLAMA_NUM_CTX)
	@echo "Pulling base model $(OLLAMA_BASE_MODEL)..."
	docker exec ckan-ollama ollama pull $(OLLAMA_BASE_MODEL)
	@echo "Creating $(OLLAMA_MODEL) with num_ctx=$(OLLAMA_NUM_CTX)..."
	@printf 'FROM $(OLLAMA_BASE_MODEL)\nPARAMETER num_ctx $(OLLAMA_NUM_CTX)\n' | \
	  docker exec -i ckan-ollama ollama create $(OLLAMA_MODEL) -f -
	@echo "Done — model $(OLLAMA_MODEL) ready with context $(OLLAMA_NUM_CTX)"

.PHONY: rebuild
rebuild: ## Rebuild mcp + agent images without cache
	$(COMPOSE) build --no-cache ckan-mcp ckan-agent

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
