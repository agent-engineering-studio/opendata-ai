#!/usr/bin/env bash
# setup.sh — Bootstrap CKAN MCP Agent stack from scratch (macOS / Linux)
#
# Usage:
#   ./setup.sh          # CPU mode (default)
#   ./setup.sh --gpu    # GPU mode (requires NVIDIA GPU + drivers)
#
# The script is idempotent: re-running it is safe.

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_GREEN="\033[0;32m"; C_CYAN="\033[0;36m"; C_YELLOW="\033[1;33m"
  C_RED="\033[0;31m";   C_BOLD="\033[1m";    C_RESET="\033[0m"
else
  C_GREEN=""; C_CYAN=""; C_YELLOW=""; C_RED=""; C_BOLD=""; C_RESET=""
fi

ok()   { echo -e "${C_GREEN}[OK]${C_RESET}  $*"; }
info() { echo -e "${C_CYAN}[..]${C_RESET}  $*"; }
warn() { echo -e "${C_YELLOW}[!!]${C_RESET}  $*"; }
die()  { echo -e "${C_RED}[ERRORE]${C_RESET}  $*" >&2; exit 1; }
hdr()  { echo -e "\n${C_BOLD}${C_CYAN}══ $* ══${C_RESET}"; }

# ── Arguments ────────────────────────────────────────────────────────────────
USE_GPU=false
REPO_URL="https://github.com/hevolus/agent-engineering-studio"  # update if needed
OLLAMA_MODEL="llama3.1:8b"
HEALTH_URL="http://localhost:8002/health"
MAX_WAIT=180  # seconds to wait for stack / model pull

for arg in "$@"; do
  case "$arg" in
    --gpu)  USE_GPU=true ;;
    --help|-h)
      echo "Usage: $0 [--gpu]"
      echo "  --gpu   Use GPU-enabled Ollama profile (requires NVIDIA GPU + drivers)"
      exit 0
      ;;
    *) die "Opzione sconosciuta: $arg  (usa --help per la guida)" ;;
  esac
done

# ── Phase 1 — Detect environment ─────────────────────────────────────────────
hdr "Fase 1 — Rilevamento sistema"

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin) PLATFORM="macos" ;;
  Linux)  PLATFORM="linux" ;;
  *)      die "Sistema operativo non supportato: $OS" ;;
esac

info "OS: $OS  |  Arch: $ARCH  |  GPU mode: $USE_GPU"

if [[ "$USE_GPU" == true ]]; then
  if [[ "$PLATFORM" == "linux" ]] && command -v nvidia-smi &>/dev/null; then
    ok "GPU NVIDIA rilevata — verrà usato il profilo GPU"
  elif [[ "$PLATFORM" == "macos" ]]; then
    warn "macOS non supporta il profilo GPU NVIDIA. Continuo in modalità CPU."
    USE_GPU=false
  else
    warn "nvidia-smi non trovato — GPU non rilevata. Continuo in modalità CPU."
    USE_GPU=false
  fi
fi

MAKE_TARGET="up"
[[ "$USE_GPU" == true ]] && MAKE_TARGET="up-gpu"

# ── Helpers ───────────────────────────────────────────────────────────────────
ask_sudo() {
  echo -e "\n${C_YELLOW}Questo passaggio richiede privilegi di amministratore (sudo).${C_RESET}"
  sudo -v || die "Privilegi sudo necessari per continuare."
}

command_exists() { command -v "$1" &>/dev/null; }

wait_for_health() {
  local url="$1" label="$2" waited=0 interval=5
  info "Attendo che $label sia pronto su $url ..."
  until curl -sf "$url" &>/dev/null; do
    if (( waited >= MAX_WAIT )); then
      die "$label non ha risposto entro ${MAX_WAIT}s — controlla i log con: make logs"
    fi
    sleep $interval
    (( waited += interval ))
    echo -n "."
  done
  echo ""
  ok "$label è pronto"
}

# ── Phase 2 — Install prerequisites ──────────────────────────────────────────
hdr "Fase 2 — Installazione prerequisiti"

install_macos() {
  # Homebrew
  if ! command_exists brew; then
    info "Installazione Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    if [[ "$ARCH" == "arm64" ]] && [[ -f /opt/homebrew/bin/brew ]]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
  else
    ok "Homebrew già installato"
  fi

  # git
  if ! command_exists git; then
    info "Installazione git..."
    brew install git
  else
    ok "git già installato: $(git --version)"
  fi

  # make
  if ! command_exists make; then
    info "Installazione make..."
    brew install make
  else
    ok "make già installato"
  fi

  # Docker Desktop
  if ! command_exists docker; then
    info "Installazione Docker Desktop (questo può richiedere qualche minuto)..."
    brew install --cask docker
    warn "Docker Desktop è stato installato. Aprilo dal Launchpad/Finder per avviarlo, poi premi INVIO per continuare."
    read -r -p ""
  else
    ok "Docker già installato: $(docker --version 2>/dev/null || true)"
  fi

  # Ensure Docker daemon is running
  if ! docker info &>/dev/null 2>&1; then
    info "Avvio Docker Desktop..."
    open -a Docker
    info "Attendo che Docker sia pronto (max ${MAX_WAIT}s)..."
    waited=0
    until docker info &>/dev/null 2>&1; do
      if (( waited >= MAX_WAIT )); then
        die "Docker Desktop non si è avviato entro ${MAX_WAIT}s. Aprilo manualmente e riesegui lo script."
      fi
      sleep 5; (( waited += 5 )); echo -n "."
    done
    echo ""; ok "Docker Desktop avviato"
  else
    ok "Docker daemon già in esecuzione"
  fi
}

install_linux() {
  # Detect package manager
  if command_exists apt-get; then
    PKG_INSTALL="sudo apt-get install -y"
    PKG_UPDATE="sudo apt-get update -qq"
    PKG_GIT="git"
    PKG_MAKE="make"
    PKG_CURL="curl"
  elif command_exists dnf; then
    PKG_INSTALL="sudo dnf install -y"
    PKG_UPDATE="true"
    PKG_GIT="git"
    PKG_MAKE="make"
    PKG_CURL="curl"
  elif command_exists pacman; then
    PKG_INSTALL="sudo pacman -S --noconfirm"
    PKG_UPDATE="sudo pacman -Sy"
    PKG_GIT="git"
    PKG_MAKE="make"
    PKG_CURL="curl"
  else
    die "Package manager non supportato. Installa manualmente: git, make, curl, docker."
  fi

  # curl (needed for docker install script)
  if ! command_exists curl; then
    ask_sudo
    $PKG_UPDATE
    $PKG_INSTALL $PKG_CURL
  else
    ok "curl già installato"
  fi

  # git
  if ! command_exists git; then
    ask_sudo
    $PKG_UPDATE
    $PKG_INSTALL $PKG_GIT
  else
    ok "git già installato: $(git --version)"
  fi

  # make
  if ! command_exists make; then
    ask_sudo
    $PKG_INSTALL $PKG_MAKE
  else
    ok "make già installato"
  fi

  # Docker Engine
  if ! command_exists docker; then
    info "Installazione Docker Engine tramite script ufficiale..."
    ask_sudo
    curl -fsSL https://get.docker.com | sudo sh
    # Add current user to docker group
    sudo usermod -aG docker "$USER"
    warn "L'utente '$USER' è stato aggiunto al gruppo 'docker'."
    warn "Per usare docker senza sudo in sessioni future, esegui: newgrp docker"
    warn "In questa sessione verrà usato sudo dove necessario."
  else
    ok "Docker già installato: $(docker --version)"
  fi

  # docker compose plugin (v2)
  if ! docker compose version &>/dev/null 2>&1; then
    info "Installazione docker compose plugin..."
    DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
    mkdir -p "$DOCKER_CONFIG/cli-plugins"
    COMPOSE_VERSION="$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')"
    COMPOSE_URL="https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"
    curl -fsSL "$COMPOSE_URL" -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
    chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
    ok "docker compose plugin installato (v${COMPOSE_VERSION})"
  else
    ok "docker compose già disponibile: $(docker compose version --short 2>/dev/null || true)"
  fi

  # Start Docker daemon if not running
  if ! docker info &>/dev/null 2>&1; then
    info "Avvio Docker daemon..."
    sudo systemctl start docker 2>/dev/null || sudo service docker start 2>/dev/null || \
      die "Impossibile avviare Docker. Avvialo manualmente con: sudo systemctl start docker"
    ok "Docker daemon avviato"
  else
    ok "Docker daemon già in esecuzione"
  fi
}

case "$PLATFORM" in
  macos) install_macos ;;
  linux) install_linux ;;
esac

# ── Phase 3 — Repository ──────────────────────────────────────────────────────
hdr "Fase 3 — Repository"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=""

# Check if we're already inside the repo
if [[ -f "$SCRIPT_DIR/docker-compose.yml" ]] && [[ -f "$SCRIPT_DIR/Makefile" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
  ok "Già nella cartella del progetto: $REPO_ROOT"
else
  info "Clone del repository in corso..."
  TARGET_DIR="$HOME/ckan-mcp"
  if [[ -d "$TARGET_DIR/.git" ]]; then
    ok "Repository già clonato in $TARGET_DIR — aggiorno..."
    git -C "$TARGET_DIR" pull --ff-only
  else
    git clone "$REPO_URL" "$TARGET_DIR"
    ok "Repository clonato in $TARGET_DIR"
  fi
  REPO_ROOT="$TARGET_DIR"
fi

cd "$REPO_ROOT"

# ── Phase 4 — Configuration (.env) ───────────────────────────────────────────
hdr "Fase 4 — Configurazione"

if [[ ! -f ".env" ]]; then
  cp .env.example .env
  ok ".env creato da .env.example"
else
  ok ".env già presente"
fi

# Ask about LLM provider
echo ""
echo -e "${C_BOLD}Provider LLM${C_RESET}"
echo "  1) Ollama locale (gratis, nessuna API key — richiede ~5 GB, lento su CPU)"
echo "  2) Anthropic Claude (veloce, richiede API key)"
echo "  3) Azure AI Foundry (veloce, richiede endpoint Azure)"
echo ""
read -r -p "Scegli il provider [1/2/3] (default: 1): " PROVIDER_CHOICE
PROVIDER_CHOICE="${PROVIDER_CHOICE:-1}"

case "$PROVIDER_CHOICE" in
  2)
    read -r -p "Inserisci la tua Anthropic API key (sk-ant-...): " ANTHROPIC_KEY
    if [[ -z "$ANTHROPIC_KEY" ]]; then
      warn "Nessuna key inserita — uso Ollama come fallback"
    else
      sed -i.bak "s/^LLM_PROVIDER=.*/LLM_PROVIDER=claude/" .env
      if grep -q "^ANTHROPIC_API_KEY=" .env; then
        sed -i.bak "s/^ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=${ANTHROPIC_KEY}/" .env
      else
        echo "ANTHROPIC_API_KEY=${ANTHROPIC_KEY}" >> .env
      fi
      rm -f .env.bak
      ok "Provider impostato: claude"
      OLLAMA_MODEL=""  # skip model pull
    fi
    ;;
  3)
    read -r -p "Inserisci AZURE_AI_PROJECT_ENDPOINT: " AZURE_ENDPOINT
    read -r -p "Inserisci AZURE_AI_MODEL_DEPLOYMENT_NAME: " AZURE_DEPLOYMENT
    if [[ -n "$AZURE_ENDPOINT" ]] && [[ -n "$AZURE_DEPLOYMENT" ]]; then
      sed -i.bak "s/^LLM_PROVIDER=.*/LLM_PROVIDER=azure_foundry/" .env
      if grep -q "^AZURE_AI_PROJECT_ENDPOINT=" .env; then
        sed -i.bak "s|^AZURE_AI_PROJECT_ENDPOINT=.*|AZURE_AI_PROJECT_ENDPOINT=${AZURE_ENDPOINT}|" .env
      else
        echo "AZURE_AI_PROJECT_ENDPOINT=${AZURE_ENDPOINT}" >> .env
      fi
      if grep -q "^AZURE_AI_MODEL_DEPLOYMENT_NAME=" .env; then
        sed -i.bak "s/^AZURE_AI_MODEL_DEPLOYMENT_NAME=.*/AZURE_AI_MODEL_DEPLOYMENT_NAME=${AZURE_DEPLOYMENT}/" .env
      else
        echo "AZURE_AI_MODEL_DEPLOYMENT_NAME=${AZURE_DEPLOYMENT}" >> .env
      fi
      rm -f .env.bak
      ok "Provider impostato: azure_foundry"
      OLLAMA_MODEL=""  # skip model pull
    else
      warn "Dati Azure incompleti — uso Ollama come fallback"
    fi
    ;;
  *)
    ok "Provider: ollama con modello ${OLLAMA_MODEL}"
    sed -i.bak "s/^LLM_PROVIDER=.*/LLM_PROVIDER=ollama/" .env
    sed -i.bak "s/^OLLAMA_LLM_MODEL=.*/OLLAMA_LLM_MODEL=${OLLAMA_MODEL}/" .env
    rm -f .env.bak
    ;;
esac

# ── Phase 5 — Build and start stack ──────────────────────────────────────────
hdr "Fase 5 — Build e avvio stack (make ${MAKE_TARGET})"

info "Build immagini Docker e avvio stack..."
make "$MAKE_TARGET"

# Wait for the agent to be healthy
wait_for_health "$HEALTH_URL" "ckan-agent"

# ── Phase 6 — Pull Ollama model ───────────────────────────────────────────────
if [[ -n "$OLLAMA_MODEL" ]]; then
  hdr "Fase 6 — Download modello LLM (${OLLAMA_MODEL})"

  info "Attendo che il container Ollama sia pronto..."
  waited=0
  until docker exec ckan-ollama ollama list &>/dev/null 2>&1; do
    if (( waited >= MAX_WAIT )); then
      die "Container Ollama non disponibile entro ${MAX_WAIT}s"
    fi
    sleep 5; (( waited += 5 )); echo -n "."
  done
  echo ""
  ok "Container Ollama pronto"

  # Check if model already present
  if docker exec ckan-ollama ollama list 2>/dev/null | grep -q "${OLLAMA_MODEL%%:*}"; then
    ok "Modello ${OLLAMA_MODEL} già presente nel container"
  else
    info "Download ${OLLAMA_MODEL} (~4.7 GB — può richiedere alcuni minuti)..."
    docker exec ckan-ollama ollama pull "$OLLAMA_MODEL"
    ok "Modello ${OLLAMA_MODEL} pronto"
  fi
fi

# ── Phase 7 — Smoke test ──────────────────────────────────────────────────────
hdr "Fase 7 — Verifica finale"

HEALTH_RESPONSE="$(curl -sf "$HEALTH_URL" 2>/dev/null || true)"
if echo "$HEALTH_RESPONSE" | grep -q '"ok"'; then
  ok "Health check superato: $HEALTH_RESPONSE"
else
  warn "Health check non ha restituito il risultato atteso: ${HEALTH_RESPONSE:-nessuna risposta}"
  warn "Controlla i log con: make logs"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${C_BOLD}${C_GREEN}╔══════════════════════════════════════════════╗"
echo -e "║         Stack avviato correttamente!         ║"
echo -e "╚══════════════════════════════════════════════╝${C_RESET}"
echo ""
echo -e "  ${C_BOLD}Agent API${C_RESET}   →  http://localhost:8002"
echo -e "  ${C_BOLD}API Docs${C_RESET}    →  http://localhost:8002/docs"
echo -e "  ${C_BOLD}MCP server${C_RESET}  →  http://localhost:8080"
echo ""
echo -e "  Comandi utili:"
echo -e "    ${C_CYAN}make logs${C_RESET}   — mostra i log in tempo reale"
echo -e "    ${C_CYAN}make ps${C_RESET}     — stato dei container"
echo -e "    ${C_CYAN}make down${C_RESET}   — ferma lo stack"
if [[ "$USE_GPU" == true ]]; then
  echo -e "    ${C_CYAN}make up-gpu${C_RESET} — riavvia in modalità GPU"
else
  echo -e "    ${C_CYAN}make up${C_RESET}     — riavvia lo stack"
fi
echo ""
