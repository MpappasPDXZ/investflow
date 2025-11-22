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

### 6. Nessie REST Catalog (Container App)
- **Name:** investflow-nessie
- **Image:** ghcr.io/projectnessie/nessie:latest
- **Internal FQDN:** investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io
- **REST API Endpoint:** https://investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v2
- **Port:** 19120
- **Ingress:** Internal (accessible within Container Apps Environment)
- **Purpose:** Apache Iceberg REST Catalog for table metadata
- **Status:** Running

## Connection Strings & Secrets

**⚠️ IMPORTANT: Connection strings and secrets are stored in Azure Key Vault, NOT in this repository.**

To retrieve connection strings:
```bash
# Storage Account Connection String
az storage account show-connection-string --name investflowstorage --resource-group investflow-rg

# Application Insights Connection String
az monitor app-insights component show --app investflow-insights --resource-group investflow-rg --query connectionString
```

## Nessie Configuration

The Nessie catalog is deployed as an internal container app. To access it from the backend:

1. Backend must be deployed in the same Container Apps Environment (investflow-env)
2. Use the internal FQDN: `investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io`
3. REST API endpoint: `https://investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v2`

### Current Status
- ✅ **Deployed and Running**: Nessie is running on port 19120
- ⚠️ **Storage**: Currently using IN_MEMORY version store (data will be lost on restart)
- ⚠️ **Security**: Authentication and authorization are disabled (for development)
- 📝 **Next Steps**: Configure persistent storage (PostgreSQL or similar) and enable authentication

### Testing Nessie

**From Backend Health Endpoint:**
```bash
# Once backend is running, test Nessie connection:
curl http://localhost:8000/api/v1/health/nessie
```

**Direct Nessie API Test (from within Azure):**
```bash
# List namespaces
curl https://investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v2/namespaces

# Get default branch
curl https://investflow-nessie.internal.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v2/branches/main
```

For local development, you may need to:
- Use port forwarding: `az containerapp proxy --name investflow-nessie --resource-group investflow-rg`
- Or deploy a local Nessie instance for development

## Next Steps

1. ✅ Store connection strings in Key Vault - DONE
2. Configure GitHub Secrets for CI/CD
3. Deploy backend Container App (will connect to Nessie)
4. Deploy frontend Container App

