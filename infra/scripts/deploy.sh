#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  deploy.sh — provision + build + deploy ckan-mcp to Azure.
#
#  Usage:
#    ./deploy.sh \
#      --subscription <id> \
#      --resource-group <rg> \
#      --location westeurope \
#      --env-name dev \
#      --acr-name <globally-unique> \
#     [--image-tag v0.1.0] \
#     [--azure-openai-endpoint https://xx.openai.azure.com/] \
#     [--azure-openai-deployment gpt-4o-mini] \
#     [--azure-openai-api-key ****] \
#     [--ckan-default-url https://www.dati.gov.it/opendata] \
#     [--skip-build] [--skip-infra]
#
#  Environment variables prefixed with AZURE_ / ACR_ are used as fallbacks.
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "${SCRIPT_DIR}/../.." && pwd )"
BICEP_MAIN="${REPO_ROOT}/infra/bicep/main.bicep"

# ─── Parameters with env fallbacks ───
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
LOCATION="${AZURE_LOCATION:-westeurope}"
ENV_NAME="${AZURE_ENV_NAME:-dev}"
ACR_NAME="${ACR_NAME:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
AOAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
AOAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-gpt-4o-mini}"
AOAI_API_KEY="${AZURE_OPENAI_API_KEY:-}"
OPENAI_API_KEY_VAL="${OPENAI_API_KEY:-}"
LLM_PROVIDER="${LLM_PROVIDER:-azure_openai}"
CKAN_URL="${CKAN_DEFAULT_BASE_URL:-https://www.dati.gov.it/opendata}"
SKIP_BUILD=false
SKIP_INFRA=false

usage() { sed -n '2,20p' "$0" ; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription|-s)          SUBSCRIPTION_ID="$2"; shift 2 ;;
    --resource-group|-g)        RESOURCE_GROUP="$2"; shift 2 ;;
    --location|-l)              LOCATION="$2"; shift 2 ;;
    --env-name|-e)              ENV_NAME="$2"; shift 2 ;;
    --acr-name)                 ACR_NAME="$2"; shift 2 ;;
    --image-tag)                IMAGE_TAG="$2"; shift 2 ;;
    --azure-openai-endpoint)    AOAI_ENDPOINT="$2"; shift 2 ;;
    --azure-openai-deployment)  AOAI_DEPLOYMENT="$2"; shift 2 ;;
    --azure-openai-api-key)     AOAI_API_KEY="$2"; shift 2 ;;
    --openai-api-key)           OPENAI_API_KEY_VAL="$2"; shift 2 ;;
    --llm-provider)             LLM_PROVIDER="$2"; shift 2 ;;
    --ckan-default-url)         CKAN_URL="$2"; shift 2 ;;
    --skip-build)               SKIP_BUILD=true; shift ;;
    --skip-infra)               SKIP_INFRA=true; shift ;;
    -h|--help)                  usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# ─── Validation ───
: "${SUBSCRIPTION_ID:?--subscription / AZURE_SUBSCRIPTION_ID is required}"
: "${RESOURCE_GROUP:?--resource-group / AZURE_RESOURCE_GROUP is required}"
: "${ACR_NAME:?--acr-name / ACR_NAME is required}"
if ! command -v az >/dev/null 2>&1; then
  echo "az CLI not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli" >&2
  exit 1
fi

echo "┌──────────── ckan-mcp :: Azure deploy ────────────"
echo "│ Subscription : $SUBSCRIPTION_ID"
echo "│ Resource grp : $RESOURCE_GROUP  ($LOCATION)"
echo "│ Env name     : $ENV_NAME"
echo "│ ACR          : $ACR_NAME"
echo "│ Image tag    : $IMAGE_TAG"
echo "│ LLM provider : $LLM_PROVIDER"
echo "│ CKAN default : $CKAN_URL"
echo "└──────────────────────────────────────────────────"

az account set --subscription "$SUBSCRIPTION_ID"

# ─── 1. Resource group ───
echo "▶ Ensuring resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# ─── 2. ACR (standalone, idempotent) so images exist before Bicep ───
echo "▶ Ensuring Azure Container Registry '$ACR_NAME'..."
az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" --sku Basic --output none 2>/dev/null || \
  az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --output none

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
echo "  ✓ ACR login server: $ACR_LOGIN_SERVER"

# ─── 3. Build & push images (must run before Bicep so Container Apps find them) ───
if [[ "$SKIP_BUILD" == "false" ]]; then
  echo "▶ Building and pushing images via ACR Tasks..."
  az acr build \
    --registry "$ACR_NAME" \
    --image "ckan-mcp-server:${IMAGE_TAG}" \
    --image "ckan-mcp-server:latest" \
    --file "${REPO_ROOT}/ckan-mcp-server/Dockerfile" \
    "${REPO_ROOT}/ckan-mcp-server"

  az acr build \
    --registry "$ACR_NAME" \
    --image "ckan-mcp-agent:${IMAGE_TAG}" \
    --image "ckan-mcp-agent:latest" \
    --file "${REPO_ROOT}/ckan-mcp-agent/Dockerfile" \
    "${REPO_ROOT}/ckan-mcp-agent"
fi

# ─── 4. Infra (Bicep) — idempotent, re-confirms ACR and deploys Container Apps ───
if [[ "$SKIP_INFRA" == "false" ]]; then
  echo "▶ Deploying Bicep template..."
  DEPLOY_NAME="ckan-mcp-${ENV_NAME}-$(date -u +%Y%m%d%H%M%S)"
  az deployment group create \
    --name "$DEPLOY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_MAIN" \
    --parameters \
        envName="$ENV_NAME" \
        acrName="$ACR_NAME" \
        imageTag="$IMAGE_TAG" \
        ckanDefaultBaseUrl="$CKAN_URL" \
        llmProvider="$LLM_PROVIDER" \
        azureOpenAIEndpoint="$AOAI_ENDPOINT" \
        azureOpenAIDeployment="$AOAI_DEPLOYMENT" \
        azureOpenAIApiKey="$AOAI_API_KEY" \
        openAIApiKey="$OPENAI_API_KEY_VAL" \
    --output none
  echo "  ✓ deployment $DEPLOY_NAME created"
fi

# ─── 5. Force revision refresh so apps pull the new images on re-deploys ───
echo "▶ Restarting container apps..."
for app in "ca-ckan-mcp-${ENV_NAME}" "ca-ckan-agent-${ENV_NAME}"; do
  if az containerapp show --name "$app" --resource-group "$RESOURCE_GROUP" --output none 2>/dev/null; then
    az containerapp update --name "$app" --resource-group "$RESOURCE_GROUP" \
      --set-env-vars "DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --output none
    echo "  ✓ $app restarted"
  fi
done

# ─── 6. Report URLs ───
MCP_FQDN=$(az containerapp show -n "ca-ckan-mcp-${ENV_NAME}" -g "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || echo "")
AGENT_FQDN=$(az containerapp show -n "ca-ckan-agent-${ENV_NAME}" -g "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn -o tsv 2>/dev/null || echo "")

echo
echo "╔═══════════════════════ Deploy done ═══════════════════════╗"
[[ -n "$MCP_FQDN"   ]] && echo "║ MCP    : https://${MCP_FQDN}/mcp"
[[ -n "$AGENT_FQDN" ]] && echo "║ Agent  : https://${AGENT_FQDN}"
[[ -n "$AGENT_FQDN" ]] && echo "║ Health : https://${AGENT_FQDN}/health"
echo "╚════════════════════════════════════════════════════════════╝"
