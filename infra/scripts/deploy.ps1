<#
.SYNOPSIS
  Provision + build + deploy ckan-mcp to Azure.

.DESCRIPTION
  Mirrors `deploy.sh`. Creates/updates the resource group, deploys the
  Bicep template, builds Docker images via ACR Tasks and restarts the
  Container Apps so they pull the new revisions.

.PARAMETER SubscriptionId
  Azure subscription ID.

.PARAMETER ResourceGroup
  Target resource group (created if missing).

.PARAMETER Location
  Azure region. Defaults to westeurope.

.PARAMETER EnvName
  Short environment suffix (dev/test/prod). Defaults to 'dev'.

.PARAMETER AcrName
  Globally-unique Container Registry name (5-50 chars, lowercase).

.PARAMETER ImageTag
  Tag applied to images. Defaults to 'latest'.

.PARAMETER AzureOpenAIEndpoint
  Endpoint used when LlmProvider=azure_openai.

.PARAMETER AzureOpenAIDeployment
  AOAI deployment name. Defaults to 'gpt-4o-mini'.

.PARAMETER AzureOpenAIApiKey
  Optional AOAI key. Prefer managed identity where possible.

.PARAMETER OpenAIApiKey
  OpenAI API key if LlmProvider=openai.

.PARAMETER LlmProvider
  'azure_openai' | 'openai' | 'ollama'. Defaults to 'azure_openai'.

.PARAMETER CkanDefaultUrl
  Default CKAN portal used when a tool omits base_url.

.PARAMETER SkipBuild
  Skip `az acr build` step.

.PARAMETER SkipInfra
  Skip `az deployment group create` step.

.EXAMPLE
  ./deploy.ps1 -SubscriptionId '00000000-...' -ResourceGroup 'rg-ckan-mcp-dev' `
               -AcrName 'ckanmcpdev' -AzureOpenAIEndpoint 'https://my.openai.azure.com/' `
               -AzureOpenAIApiKey $env:AOAI_KEY
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $SubscriptionId,
    [Parameter(Mandatory=$true)][string] $ResourceGroup,
    [string] $Location = 'westeurope',
    [string] $EnvName = 'dev',
    [Parameter(Mandatory=$true)][ValidateLength(5,50)][string] $AcrName,
    [string] $ImageTag = 'latest',
    [string] $AzureOpenAIEndpoint = '',
    [string] $AzureOpenAIDeployment = 'gpt-4o-mini',
    [string] $AzureOpenAIApiKey = '',
    [string] $OpenAIApiKey = '',
    [ValidateSet('azure_openai','openai','ollama')][string] $LlmProvider = 'azure_openai',
    [string] $CkanDefaultUrl = 'https://www.dati.gov.it/opendata',
    [switch] $SkipBuild,
    [switch] $SkipInfra
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$bicepMain = Join-Path $repoRoot 'infra\bicep\main.bicep'

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "az CLI not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli"
}

Write-Host "┌──────────── ckan-mcp :: Azure deploy ────────────" -ForegroundColor Cyan
Write-Host "│ Subscription : $SubscriptionId"
Write-Host "│ Resource grp : $ResourceGroup  ($Location)"
Write-Host "│ Env name     : $EnvName"
Write-Host "│ ACR          : $AcrName"
Write-Host "│ Image tag    : $ImageTag"
Write-Host "│ LLM provider : $LlmProvider"
Write-Host "│ CKAN default : $CkanDefaultUrl"
Write-Host "└──────────────────────────────────────────────────" -ForegroundColor Cyan

az account set --subscription $SubscriptionId | Out-Null

Write-Host "`n▶ Ensuring resource group..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output none

Write-Host "`n▶ Ensuring Azure Container Registry '$AcrName'..." -ForegroundColor Yellow
$acrExists = az acr show --name $AcrName --resource-group $ResourceGroup --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    az acr create --name $AcrName --resource-group $ResourceGroup `
        --location $Location --sku Basic --output none
}
$acrLoginServer = az acr show --name $AcrName --resource-group $ResourceGroup --query loginServer -o tsv
Write-Host "  ✓ ACR login server: $acrLoginServer" -ForegroundColor Green

if (-not $SkipBuild) {
    Write-Host "`n▶ Building and pushing images via ACR Tasks..." -ForegroundColor Yellow

    az acr build `
        --registry $AcrName `
        --image "ckan-mcp-server:$ImageTag" `
        --image "ckan-mcp-server:latest" `
        --file (Join-Path $repoRoot 'ckan-mcp-server\Dockerfile') `
        (Join-Path $repoRoot 'ckan-mcp-server')

    az acr build `
        --registry $AcrName `
        --image "ckan-mcp-agent:$ImageTag" `
        --image "ckan-mcp-agent:latest" `
        --file (Join-Path $repoRoot 'ckan-mcp-agent\Dockerfile') `
        (Join-Path $repoRoot 'ckan-mcp-agent')
}

if (-not $SkipInfra) {
    Write-Host "`n▶ Deploying Bicep template..." -ForegroundColor Yellow
    $deployName = "ckan-mcp-$EnvName-$(Get-Date -Format 'yyyyMMddHHmmss')"
    az deployment group create `
        --name $deployName `
        --resource-group $ResourceGroup `
        --template-file $bicepMain `
        --parameters `
            envName=$EnvName `
            acrName=$AcrName `
            imageTag=$ImageTag `
            ckanDefaultBaseUrl=$CkanDefaultUrl `
            llmProvider=$LlmProvider `
            azureOpenAIEndpoint=$AzureOpenAIEndpoint `
            azureOpenAIDeployment=$AzureOpenAIDeployment `
            azureOpenAIApiKey=$AzureOpenAIApiKey `
            openAIApiKey=$OpenAIApiKey `
        --output none
    Write-Host "  ✓ deployment $deployName created" -ForegroundColor Green
}

Write-Host "`n▶ Restarting container apps..." -ForegroundColor Yellow
$apps = @("ca-ckan-mcp-$EnvName", "ca-ckan-agent-$EnvName")
foreach ($app in $apps) {
    $exists = az containerapp show --name $app --resource-group $ResourceGroup --output none 2>$null
    if ($LASTEXITCODE -eq 0) {
        $deployedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        az containerapp update --name $app --resource-group $ResourceGroup `
            --set-env-vars "DEPLOYED_AT=$deployedAt" --output none
        Write-Host "  ✓ $app restarted" -ForegroundColor Green
    }
}

$mcpFqdn = az containerapp show -n "ca-ckan-mcp-$EnvName" -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv 2>$null
$agentFqdn = az containerapp show -n "ca-ckan-agent-$EnvName" -g $ResourceGroup --query properties.configuration.ingress.fqdn -o tsv 2>$null

Write-Host ""
Write-Host "╔═══════════════════════ Deploy done ═══════════════════════╗" -ForegroundColor Green
if ($mcpFqdn)   { Write-Host "║ MCP    : https://$mcpFqdn/mcp" }
if ($agentFqdn) { Write-Host "║ Agent  : https://$agentFqdn" }
if ($agentFqdn) { Write-Host "║ Health : https://$agentFqdn/health" }
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
