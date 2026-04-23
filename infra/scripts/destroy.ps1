<#
.SYNOPSIS
  Delete the ckan-mcp resource group.

.EXAMPLE
  ./destroy.ps1 -SubscriptionId '...' -ResourceGroup 'rg-ckan-mcp-dev' -Yes
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $SubscriptionId,
    [Parameter(Mandatory=$true)][string] $ResourceGroup,
    [switch] $Yes
)

$ErrorActionPreference = 'Stop'

az account set --subscription $SubscriptionId | Out-Null

if (-not $Yes) {
    $answer = Read-Host "Delete resource group '$ResourceGroup' and ALL contents? Type the RG name to confirm"
    if ($answer -ne $ResourceGroup) {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "▶ Deleting resource group $ResourceGroup (no-wait)..." -ForegroundColor Yellow
az group delete --name $ResourceGroup --yes --no-wait
Write-Host "  ✓ delete scheduled" -ForegroundColor Green
