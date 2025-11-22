# GitHub Secrets Setup

This document outlines the GitHub Secrets that need to be configured for CI/CD.

## Required Secrets

### Azure Container Registry (ACR)
- **ACR_USERNAME**: Azure Container Registry username
  - Get with: `az acr credential show --name investflowregistry --query username -o tsv`
- **ACR_PASSWORD**: Azure Container Registry password
  - Get with: `az acr credential show --name investflowregistry --query passwords[0].value -o tsv`

### Azure Deployment (for future deployment jobs)
- **AZURE_CREDENTIALS**: Service principal credentials for Azure deployment
  - Create with: `az ad sp create-for-rbac --name investflow-github-actions --role contributor --scopes /subscriptions/{subscription-id}/resourceGroups/investflow-rg --sdk-auth`
- **RESOURCE_GROUP**: `investflow-rg`
- **STORAGE_CONNECTION_STRING**: (Optional - can be retrieved from Key Vault)

### Application Configuration
- **NEXT_PUBLIC_API_URL**: (Optional) API URL for frontend builds
  - Development: `http://localhost:8000`
  - Production: Your production API URL

## How to Add Secrets

1. Go to your GitHub repository: https://github.com/MpappasPDXZ/investflow
2. Navigate to: Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with the name and value above

## Getting ACR Credentials

```bash
# Enable admin user (if not already enabled)
az acr update --name investflowregistry --admin-enabled true

# Get username
az acr credential show --name investflowregistry --query username -o tsv

# Get password
az acr credential show --name investflowregistry --query passwords[0].value -o tsv
```

## Security Notes

- Never commit secrets to the repository
- Rotate secrets regularly
- Use Azure Key Vault for production secrets
- Limit secret access to necessary workflows only

