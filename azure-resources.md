# InvestFlow Azure Resources Documentation

**Resource Group:** investflow-rg  
**Location:** eastus  
**Created:** 2025-11-22

## Resources Created

### 1. Storage Account
- **Name:** investflowstorage
- **Type:** Standard_LRS
- **Purpose:** Blob storage for documents (receipts, leases, etc.)
- **Container:** documents
- **Endpoint:** https://investflowstorage.blob.core.windows.net/

### 2. Azure Container Registry (ACR)
- **Name:** investflowregistry
- **SKU:** Basic
- **Login Server:** investflowregistry.azurecr.io
- **Purpose:** Store Docker images for backend and frontend

### 3. Container Apps Environment
- **Name:** investflow-env
- **Default Domain:** yellowsky-ca466dfe.eastus.azurecontainerapps.io
- **Purpose:** Host containerized applications (backend, frontend, Nessie)

### 4. Azure Key Vault
- **Name:** investflow-kv
- **Purpose:** Store secrets, connection strings, API keys
- **Location:** eastus

### 5. Application Insights
- **Name:** investflow-insights
- **Instrumentation Key:** e65a1172-cd43-47b4-b435-f689cdd47938
- **App ID:** b45e8a39-691b-4c5c-9701-60c359d082a9
- **Purpose:** Application monitoring and logging
- **Connection String:** (Stored in Key Vault - do not commit to repo)

## Connection Strings & Secrets

**⚠️ IMPORTANT: Connection strings and secrets are stored in Azure Key Vault, NOT in this repository.**

To retrieve connection strings:
```bash
# Storage Account Connection String
az storage account show-connection-string --name investflowstorage --resource-group investflow-rg

# Application Insights Connection String
az monitor app-insights component show --app investflow-insights --resource-group investflow-rg --query connectionString
```

## Next Steps

1. Store connection strings in Key Vault
2. Configure GitHub Secrets for CI/CD
3. Set up Container Apps for deployment

