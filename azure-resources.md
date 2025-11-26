# InvestFlow Azure Resources Documentation

**Resource Group:** investflow-rg  
**Location:** eastus  
**Created:** 2025-11-22

## Resources Created

### 1. Storage Accounts

#### investflowadls (ADLS Gen2) - Primary Storage Account
- **Name:** investflowadls
- **Type:** Standard_LRS
- **Purpose:** Azure Data Lake Storage Gen2 for Iceberg tables, blob storage, and Azure File Share
- **Container:** documents
- **DFS Endpoint:** https://investflowadls.dfs.core.windows.net/
- **Blob Endpoint:** https://investflowadls.blob.core.windows.net/
- **Hierarchical Namespace:** ✅ **Enabled** (true ADLS Gen2)
- **Iceberg Warehouse Path:** `abfss://documents@investflowadls.dfs.core.windows.net/iceberg-warehouse`
- **File Share:** `gravitino-metastore` (10 GB) - for Gravitino H2 metastore persistence

#### investflowstorage (Deprecated - To Be Deleted)
- **Name:** investflowstorage
- **Status:** ⚠️ **Deprecated** - Consolidating to single ADLS Gen2 account
- **Action Required:** Check for important data, then delete if empty/unused

### 2. Azure Container Registry (ACR)
- **Name:** investflowregistry
- **SKU:** Basic
- **Login Server:** investflowregistry.azurecr.io
- **Purpose:** Store Docker images for backend and frontend

### 3. Container Apps Environment
- **Name:** investflow-env
- **Default Domain:** yellowsky-ca466dfe.eastus.azurecontainerapps.io
- **Purpose:** Host containerized applications (backend, frontend)

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

To retrieve connection strings and keys:
```bash
# ADLS Gen2 Storage Account Connection String
az storage account show-connection-string --name investflowadls --resource-group investflow-rg

# ADLS Gen2 Storage Account Key (from Key Vault)
az keyvault secret show --vault-name investflow-kv --name ADLSStorageAccountKey --query value -o tsv

# Note: StorageAccountKey secret can be removed from Key Vault after investflowstorage is deleted

# Application Insights Connection String
az monitor app-insights component show --app investflow-insights --resource-group investflow-rg --query connectionString
```

## Iceberg Catalog Configuration

InvestFlow uses **Gravitino** as the catalog layer for Iceberg tables, with **Hadoop** as the catalog type and **Azure Data Lake Storage Gen2** for storage.

### ADLS Gen2 Storage
- **Storage Account:** `investflowadls` (ADLS Gen2 with hierarchical namespace enabled)
- **Container:** `documents`
- **Warehouse Path:** `abfss://documents@investflowadls.dfs.core.windows.net/iceberg-warehouse`
- **Format:** `abfss://container@account.dfs.core.windows.net/path`
- **Purpose:** Store Iceberg table data and metadata files

### Gravitino Metastore
- **Type:** H2 embedded database (file-based)
- **Storage:** Azure File Share `gravitino-metastore` in `investflowadls` account
- **Mount Path:** `/mnt/gravitino-metastore` (in container apps)
- **Purpose:** Persistent storage for Gravitino catalog metadata (metalakes, catalogs, schemas)

### Testing Catalog Connection

**From Backend Health Endpoint:**
```bash
# Once backend is running, test catalog connection:
curl http://localhost:8000/api/v1/health/catalog
```

## Cleanup Complete ✅

**Unnecessary container apps have been deleted to reduce costs:**
- ✅ Removed catalog server (not needed with HadoopCatalog)
- ✅ Removed database server (not needed with HadoopCatalog)
- **Cost Savings:** ~$20-40/month

## Next Steps

1. ✅ Store connection strings in Key Vault - DONE
2. ✅ Clean up catalog and database containers - DONE (saves ~$20-40/month)
3. Configure GitHub Secrets for CI/CD
4. Deploy backend Container App (will use HadoopCatalog)
5. Deploy frontend Container App

