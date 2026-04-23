param name string
param location string
param tags object = {}
param environmentId string
param userAssignedIdentityId string
param registryServer string
param image string
param targetPort int = 8080
param external bool = true
param minReplicas int = 1
param maxReplicas int = 3
param cpu string = '0.5'
param memory string = '1.0Gi'
param env array = []
param secrets array = []

// Filter out empty-string secrets so we don't push blank values to ACA.
var effectiveSecrets = [for s in secrets: s if (contains(s, 'value') && length(string(s.value)) > 0)]
var effectiveSecretNames = [for s in effectiveSecrets: s.name]
// Drop env entries that reference a secret we didn't materialize.
var effectiveEnv = [for e in env: e if (!contains(e, 'secretRef') || contains(effectiveSecretNames, e.secretRef))]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registryServer
          identity: userAssignedIdentityId
        }
      ]
      secrets: effectiveSecrets
    }
    template: {
      containers: [
        {
          name: name
          image: image
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: effectiveEnv
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
