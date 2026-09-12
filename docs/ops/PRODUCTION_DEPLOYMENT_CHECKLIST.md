# Production Deployment Checklist

## ⚠️ Critical Issue Found

The **production backend was pointing to localhost Lakekeeper**, which caused the authentication failures you experienced. This is what led to the PostgreSQL reset incident.

## Required Azure Container App Environment Variables

### Backend Container App (`investflow-backend`)

You **MUST** set these environment variables in the Azure Container App:

```bash
# Lakekeeper Connection (CRITICAL - was missing/wrong)
LAKEKEEPER__BASE_URI=https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io

# Lakekeeper Warehouse
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper

# OAuth2/OIDC for Lakekeeper Authentication
LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd
LAKEKEEPER__OAUTH2__CLIENT_SECRET=<your-oauth2-client-secret>
LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e
LAKEKEEPER__OAUTH2__SCOPE=api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=<your-key>

# PostgreSQL (for Lakekeeper metadata)
LAKEKEEPER__PG_DATABASE_URL_READ=postgres://pgadmin:pass1234%21@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require
LAKEKEEPER__PG_DATABASE_URL_WRITE=postgres://pgadmin:pass1234%21@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require

# Encryption Key (must match what Lakekeeper uses)
LAKEKEEPER__PG_ENCRYPTION_KEY=<your-encryption-key>
```

### Frontend Container App (`investflow-frontend`)

The frontend is already configured correctly via the GitHub Actions workflow (line 46):
```yaml
--build-arg NEXT_PUBLIC_API_URL=${{ env.BACKEND_URL }}
```

This sets: `NEXT_PUBLIC_API_URL=https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io`

## Deployment Steps

### 1. Update Backend Environment Variables

```bash
# Set Lakekeeper URI (THIS WAS MISSING!)
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --set-env-vars \
    LAKEKEEPER__BASE_URI=https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io \
    LAKEKEEPER__OAUTH2__CLIENT_ID=2f43977e-7c3d-478f-86b0-f72b82e869dd \
    LAKEKEEPER__OAUTH2__TENANT_ID=479bc30b-030f-4a2e-8ea2-67f549b32f5e \
    LAKEKEEPER__OAUTH2__SCOPE="api://9c72d190-0a2f-4b94-9cb5-99349363f4f7/.default"

# Set secrets separately (not exposed in env vars listing)
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --secrets \
    lakekeeper-oauth-secret=<your-oauth2-client-secret> \
    azure-storage-key=<your-azure-storage-key> \
    pg-encryption-key=<your-encryption-key>

# Reference secrets in env vars
az containerapp update \
  --name investflow-backend \
  --resource-group investflow-rg \
  --set-env-vars \
    LAKEKEEPER__OAUTH2__CLIENT_SECRET=secretref:lakekeeper-oauth-secret \
    AZURE_STORAGE_ACCOUNT_KEY=secretref:azure-storage-key \
    LAKEKEEPER__PG_ENCRYPTION_KEY=secretref:pg-encryption-key
```

### 2. Deploy Using GitHub Actions

The GitHub Actions workflow will automatically:
1. Build both backend and frontend Docker images
2. Push to Azure Container Registry
3. Deploy to Azure Container Apps
4. Use the correct production backend URL for the frontend

**To trigger deployment:**
```bash
git push origin main
```

Or trigger manually in GitHub Actions tab.

### 3. Verify Deployment

```bash
# Check backend health
curl https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v1/health

# Check backend can reach Lakekeeper
curl https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io/api/v1/properties \
  -H "Authorization: Bearer <your-token>"

# Check frontend
curl https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io
```

## What Was Fixed

1. ✅ **Leases API**: Now uses `leases_full` table (actual leases) instead of `leases` (comps)
2. ✅ **Comparables API**: Now uses `leases` table and deduplicates by ID
3. ✅ **Property-based Access Control**: All services filter by property ownership
4. ✅ **Document Service**: Fixed to use `vault` table
5. ✅ **Duplicate Comps**: 38 duplicates removed, leaving 28 unique comps
6. ✅ **NaN Validation**: Fixed `year_built` NaN causing lease API failures

## What Needs to Be Fixed in Production

⚠️ **CRITICAL**: Set `LAKEKEEPER__BASE_URI` to production Lakekeeper URL
⚠️ **CRITICAL**: Ensure all OAuth2 env vars are set correctly
⚠️ **CRITICAL**: Ensure `LAKEKEEPER__PG_ENCRYPTION_KEY` matches across all services

## Production URLs

- **Frontend**: https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io
- **Backend**: https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io
- **Lakekeeper**: https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io

## Notes

- The frontend build embeds the backend URL at **build time** via `NEXT_PUBLIC_API_URL`
- The GitHub Actions workflow correctly sets this on line 46
- The backend connects to Lakekeeper at **runtime** via `LAKEKEEPER__BASE_URI`
- This env var was likely not set in production, causing localhost fallback
- This is why you couldn't authenticate to Lakekeeper from production

