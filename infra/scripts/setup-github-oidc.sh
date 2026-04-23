#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  setup-github-oidc.sh — create an Azure AD app + SP with federated
#  credentials for GitHub Actions OIDC, and grant it `Contributor`
#  on the target resource group. Run once per environment.
#
#  Usage:
#    ./setup-github-oidc.sh \
#      --subscription <id> \
#      --resource-group <rg> \
#      --github-org <org> \
#      --github-repo <repo> \
#     [--app-name ckan-mcp-gh-oidc] \
#     [--branch main]
#
#  Prints the secrets you must add to the GitHub repo:
#    - AZURE_CLIENT_ID
#    - AZURE_TENANT_ID
#    - AZURE_SUBSCRIPTION_ID
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
GITHUB_ORG="${GITHUB_ORG:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
APP_NAME="ckan-mcp-gh-oidc"
BRANCH="main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription|-s)   SUBSCRIPTION_ID="$2"; shift 2 ;;
    --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
    --github-org)        GITHUB_ORG="$2"; shift 2 ;;
    --github-repo)       GITHUB_REPO="$2"; shift 2 ;;
    --app-name)          APP_NAME="$2"; shift 2 ;;
    --branch)            BRANCH="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

: "${SUBSCRIPTION_ID:?--subscription required}"
: "${RESOURCE_GROUP:?--resource-group required}"
: "${GITHUB_ORG:?--github-org required}"
: "${GITHUB_REPO:?--github-repo required}"

az account set --subscription "$SUBSCRIPTION_ID"
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "▶ Ensuring resource group exists..."
az group create --name "$RESOURCE_GROUP" --location "${AZURE_LOCATION:-westeurope}" --output none

echo "▶ Creating/locating Azure AD app '$APP_NAME'..."
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)
if [[ -z "$APP_ID" ]]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
  echo "  ✓ created app $APP_ID"
else
  echo "  ✓ reused existing app $APP_ID"
fi

SP_OBJECT_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv)
if [[ -z "$SP_OBJECT_ID" ]]; then
  SP_OBJECT_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
  echo "  ✓ created service principal"
fi

echo "▶ Granting Contributor on resource group..."
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --output none 2>/dev/null || echo "  (role assignment already exists)"

# Also grant AcrPush so `az acr build` works from CI.
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPush \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --output none 2>/dev/null || true

echo "▶ Registering federated credentials..."
register_fic() {
  local name="$1" subject="$2"
  local body
  body=$(cat <<JSON
{
  "name": "$name",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "$subject",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
  )
  az ad app federated-credential create --id "$APP_ID" --parameters "$body" --output none 2>/dev/null \
    || echo "  (credential '$name' already exists)"
  echo "  ✓ fic: $name"
}

register_fic "gh-branch-${BRANCH}"       "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/${BRANCH}"
register_fic "gh-pull-request"           "repo:${GITHUB_ORG}/${GITHUB_REPO}:pull_request"
register_fic "gh-environment-dev"        "repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:dev"
register_fic "gh-environment-prod"       "repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:prod"

echo
echo "╔═════════════════ GitHub repo secrets to set ═════════════════╗"
echo "║ AZURE_CLIENT_ID        : $APP_ID"
echo "║ AZURE_TENANT_ID        : $TENANT_ID"
echo "║ AZURE_SUBSCRIPTION_ID  : $SUBSCRIPTION_ID"
echo "╚═══════════════════════════════════════════════════════════════╝"
