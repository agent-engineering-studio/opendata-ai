@minLength(5)
@maxLength(50)
param name string
param location string
param tags object = {}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output id string = acr.id
output name string = acr.name
output loginServer string = acr.properties.loginServer
