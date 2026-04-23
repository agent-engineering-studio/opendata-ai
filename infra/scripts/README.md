# infra/scripts

Parameterised deploy scripts — identical behaviour between Bash and PowerShell.

| Script                   | Purpose                                                          |
|--------------------------|------------------------------------------------------------------|
| `deploy.sh` / `deploy.ps1` | Provision RG, deploy Bicep, build & push images, restart apps   |
| `destroy.sh` / `destroy.ps1` | Delete the resource group (requires confirmation unless `--yes`) |
| `setup-github-oidc.sh`   | Create SP + federated credentials for GitHub Actions OIDC       |

All scripts accept parameters **and** read defaults from env vars (handy with `.env.azure`):

```bash
set -a ; source ../../.env.azure ; set +a
./deploy.sh --skip-build                     # reuses AZURE_SUBSCRIPTION_ID / AZURE_RESOURCE_GROUP / ACR_NAME
```

PowerShell equivalent:
```powershell
./deploy.ps1 -SubscriptionId $env:AZURE_SUBSCRIPTION_ID `
             -ResourceGroup  $env:AZURE_RESOURCE_GROUP `
             -AcrName        $env:ACR_NAME `
             -SkipBuild
```
