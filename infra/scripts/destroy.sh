#!/usr/bin/env bash
# destroy.sh — remove the ckan-mcp resource group.
#
# Usage:
#   ./destroy.sh --subscription <id> --resource-group <rg> [--yes]

set -euo pipefail

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-}"
YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription|-s)   SUBSCRIPTION_ID="$2"; shift 2 ;;
    --resource-group|-g) RESOURCE_GROUP="$2"; shift 2 ;;
    --yes|-y)            YES=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

: "${SUBSCRIPTION_ID:?--subscription / AZURE_SUBSCRIPTION_ID required}"
: "${RESOURCE_GROUP:?--resource-group / AZURE_RESOURCE_GROUP required}"

az account set --subscription "$SUBSCRIPTION_ID"

if [[ "$YES" != "true" ]]; then
  read -r -p "Delete resource group '$RESOURCE_GROUP' and all its contents? Type the RG name to confirm: " answer
  if [[ "$answer" != "$RESOURCE_GROUP" ]]; then
    echo "Aborted." ; exit 1
  fi
fi

echo "▶ Deleting resource group $RESOURCE_GROUP (no-wait)..."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait
echo "  ✓ delete scheduled"
