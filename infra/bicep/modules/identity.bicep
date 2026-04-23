param name string
param location string
param tags object = {}
param acrId string

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

// AcrPull role — 7f951dda-4ed3-4680-a7ca-43fe172d538d
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrId, uami.id, 'acrpull')
  scope: resourceGroup()
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

output id string = uami.id
output principalId string = uami.properties.principalId
output clientId string = uami.properties.clientId
