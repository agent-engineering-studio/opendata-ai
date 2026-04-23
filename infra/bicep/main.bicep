// Entry-point Bicep template for deploying ckan-mcp + ckan-agent to
// Azure Container Apps, fronted by an Azure Container Registry.
//
// Scope: resource group (use `az deployment group create`).

targetScope = 'resourceGroup'

// ────────────────────────── Parameters ──────────────────────────

@description('Short environment name — becomes the resource name suffix (dev, test, prod).')
param envName string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Globally-unique Container Registry name (lowercase, 5-50 chars, no dashes).')
@minLength(5)
@maxLength(50)
param acrName string

@description('Tag applied to images that will be deployed.')
param imageTag string = 'latest'

@description('Default CKAN portal URL used when a tool call omits base_url.')
param ckanDefaultBaseUrl string = 'https://www.dati.gov.it/opendata'

@description('LLM provider used by the agent in cloud (azure_openai recommended).')
@allowed([ 'azure_openai', 'openai', 'ollama' ])
param llmProvider string = 'azure_openai'

@description('Azure OpenAI endpoint (leave empty if llmProvider != azure_openai).')
param azureOpenAIEndpoint string = ''

@description('Azure OpenAI deployment name.')
param azureOpenAIDeployment string = 'gpt-4o-mini'

@description('Azure OpenAI API version.')
param azureOpenAIApiVersion string = '2024-10-21'

@secure()
@description('Azure OpenAI API key (optional — prefer managed identity in production).')
param azureOpenAIApiKey string = ''

@secure()
@description('OpenAI API key (only used when llmProvider=openai).')
param openAIApiKey string = ''

// ────────────────────────── Locals ──────────────────────────────

var tags = {
  project: 'ckan-mcp'
  environment: envName
  managedBy: 'bicep'
}

var mcpImage = '${acr.outputs.loginServer}/ckan-mcp-server:${imageTag}'
var agentImage = '${acr.outputs.loginServer}/ckan-mcp-agent:${imageTag}'
var mcpInternalUrl = 'https://${mcp.outputs.fqdn}/mcp'

// ────────────────────────── Modules ─────────────────────────────

module acr 'modules/acr.bicep' = {
  name: 'acr-${envName}'
  params: {
    name: acrName
    location: location
    tags: tags
  }
}

module env 'modules/container-apps-env.bicep' = {
  name: 'cae-${envName}'
  params: {
    name: 'cae-ckan-mcp-${envName}'
    location: location
    tags: tags
  }
}

module identity 'modules/identity.bicep' = {
  name: 'uami-${envName}'
  params: {
    name: 'uami-ckan-mcp-${envName}'
    location: location
    tags: tags
    acrId: acr.outputs.id
  }
}

module mcp 'modules/container-app.bicep' = {
  name: 'ca-mcp-${envName}'
  params: {
    name: 'ca-ckan-mcp-${envName}'
    location: location
    tags: tags
    environmentId: env.outputs.id
    image: mcpImage
    targetPort: 8080
    external: true
    userAssignedIdentityId: identity.outputs.id
    registryServer: acr.outputs.loginServer
    minReplicas: 1
    maxReplicas: 3
    cpu: '0.5'
    memory: '1.0Gi'
    env: [
      { name: 'TRANSPORT', value: 'streamable-http' }
      { name: 'HOST', value: '0.0.0.0' }
      { name: 'PORT', value: '8080' }
      { name: 'MCP_PATH', value: '/mcp' }
      { name: 'CKAN_DEFAULT_BASE_URL', value: ckanDefaultBaseUrl }
      { name: 'LOG_LEVEL', value: 'INFO' }
    ]
  }
}

module agent 'modules/container-app.bicep' = {
  name: 'ca-agent-${envName}'
  params: {
    name: 'ca-ckan-agent-${envName}'
    location: location
    tags: tags
    environmentId: env.outputs.id
    image: agentImage
    targetPort: 8002
    external: true
    userAssignedIdentityId: identity.outputs.id
    registryServer: acr.outputs.loginServer
    minReplicas: 1
    maxReplicas: 2
    cpu: '0.5'
    memory: '1.0Gi'
    secrets: [
      {
        name: 'azure-openai-api-key'
        value: azureOpenAIApiKey
      }
      {
        name: 'openai-api-key'
        value: openAIApiKey
      }
    ]
    env: [
      { name: 'LLM_PROVIDER', value: llmProvider }
      { name: 'MCP_SERVER_URL', value: mcpInternalUrl }
      { name: 'CKAN_DEFAULT_BASE_URL', value: ckanDefaultBaseUrl }
      { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAIEndpoint }
      { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAIDeployment }
      { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAIApiVersion }
      { name: 'AZURE_OPENAI_API_KEY', secretRef: 'azure-openai-api-key' }
      { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
      { name: 'API_HOST', value: '0.0.0.0' }
      { name: 'API_PORT', value: '8002' }
      { name: 'LOG_LEVEL', value: 'INFO' }
    ]
  }
  dependsOn: [
    mcp
  ]
}

// ────────────────────────── Outputs ─────────────────────────────

output acrLoginServer string = acr.outputs.loginServer
output acrName string = acr.outputs.name
output mcpFqdn string = mcp.outputs.fqdn
output agentFqdn string = agent.outputs.fqdn
output mcpUrl string = 'https://${mcp.outputs.fqdn}/mcp'
output agentUrl string = 'https://${agent.outputs.fqdn}'
