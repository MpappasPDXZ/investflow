# InvestFlow Azure Deployment Plan

## 📋 Overview

Deploy the InvestFlow property management application to Azure using Container Apps for serverless container hosting with Lakekeeper for Iceberg catalog management.

**Key Feature**: CDC (Change Data Capture) Parquet cache in ADLS for fast authentication (~100ms login vs ~400ms without cache).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Resource Group                         │
│                      investflow-rg                              │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Frontend   │      │  Backend    │      │ Lakekeeper  │
│ Container   │─────▶│ Container   │─────▶│ Container   │
│    App      │      │    App      │      │    App      │
└─────────────┘      └─────────────┘      └─────────────┘
                              │                     │
                              ▼                     ▼
                     ┌─────────────┐      ┌─────────────┐
                     │   ADLS      │      │ PostgreSQL  │
                     │   Gen2      │      │   Flex      │
                     │ (Iceberg +  │      │  (Catalog)  │
                     │  CDC Cache) │      └─────────────┘
                     └─────────────┘

ADLS Storage Structure:
├── documents/
│   ├── cdc/
│   │   ├── users/users_current.parquet       # Fast auth lookups
│   │   └── shares/user_shares_current.parquet # Fast sharing lookups
│   ├── expenses/                              # Receipt images
│   └── user_documents/                        # Other documents
└── iceberg/                                   # Iceberg table data
```

---

## ✅ Existing Resources

### Already Created:
- ✅ **Resource Group**: `investflow-rg`
- ✅ **Storage Account (ADLS Gen2)**: `investflowadls`
- ✅ **Container Registry (ACR)**: `investflowregistry.azurecr.io`
- ✅ **Container Apps Environment**: `investflow-env`
- ✅ **Key Vault**: `investflow-kv`
- ✅ **Application Insights**: `investflow-insights`
- ✅ **PostgreSQL Flexible Server**: `if-postgres`

### Need to Create:
- ⬜ **Container App**: `investflow-lakekeeper`
- ⬜ **Container App**: `investflow-backend`
- ⬜ **Container App**: `investflow-frontend`

---

## 🚀 Quick Deploy (Recommended)

### Option 1: GitHub Actions (Automatic)

1. **Set up GitHub Secrets** (see `.github/SECRETS_SETUP.md`)
2. **Push to main branch** - deployment runs automatically
3. **Or trigger manually**: Actions → Deploy to Azure → Run workflow

### Option 2: Manual CLI Deployment

Follow the steps below.

---

## 📋 Step-by-Step Manual Deployment

### Step 1: Set Up GitHub Secrets

See `.github/SECRETS_SETUP.md` for the complete list. Quick summary:

```bash
# Required secrets to add to GitHub:
AZURE_CREDENTIALS          # Service principal JSON
ACR_USERNAME               # investflowregistry admin username
ACR_PASSWORD               # investflowregistry admin password
POSTGRES_HOST              # if-postgres.postgres.database.azure.com
POSTGRES_DB                # investflow
POSTGRES_USER              # your-username
POSTGRES_PASSWORD          # your-password
POSTGRES_CONNECTION_STRING # Full PostgreSQL connection string
AZURE_STORAGE_ACCOUNT_NAME # investflowadls
AZURE_STORAGE_ACCOUNT_KEY  # Storage account key
APP_SECRET_KEY             # openssl rand -base64 32
LAKEKEEPER_ENCRYPTION_KEY  # openssl rand -base64 32
```

### Step 2: Build and Push Images

```bash
# Login to ACR
az acr login --name investflowregistry

# Build and push Backend
cd backend
docker build -t investflowregistry.azurecr.io/investflow-backend:latest .
docker push investflowregistry.azurecr.io/investflow-backend:latest

# Build and push Frontend  
cd ../frontend
docker build -t investflowregistry.azurecr.io/investflow-frontend:latest .
docker push investflowregistry.azurecr.io/investflow-frontend:latest
```

### Step 3: Deploy Lakekeeper

```bash
# Get credentials
POSTGRES_URL="postgresql://<user>:<pass>@if-postgres.postgres.database.azure.com:5432/lakekeeper?sslmode=require"
ENCRYPTION_KEY=$(openssl rand -base64 32)

# Create Lakekeeper Container App
az containerapp create \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image quay.io/lakekeeper/catalog:latest \
  --target-port 8181 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    LAKEKEEPER__PG_DATABASE_URL_READ="$POSTGRES_URL" \
    LAKEKEEPER__PG_DATABASE_URL_WRITE="$POSTGRES_URL" \
    LAKEKEEPER__PG_ENCRYPTION_KEY="$ENCRYPTION_KEY"
```

### Step 4: Deploy Backend

```bash
# Get Lakekeeper URL
LAKEKEEPER_URL=$(az containerapp show \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

# Get storage key
STORAGE_KEY=$(az storage account keys list \
  --account-name investflowadls \
  --resource-group investflow-rg \
  --query [0].value -o tsv)

# Get ACR credentials
ACR_USER=$(az acr credential show --name investflowregistry --query username -o tsv)
ACR_PASS=$(az acr credential show --name investflowregistry --query passwords[0].value -o tsv)

# Create Backend Container App
az containerapp create \
  --name investflow-backend \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image investflowregistry.azurecr.io/investflow-backend:latest \
  --registry-server investflowregistry.azurecr.io \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    ENVIRONMENT="production" \
    SECRET_KEY="$(openssl rand -base64 32)" \
    CORS_ORIGINS="https://investflow-frontend.*.azurecontainerapps.io" \
    LAKEKEEPER__BASE_URI="https://$LAKEKEEPER_URL" \
    LAKEKEEPER__WAREHOUSE_NAME="lakekeeper" \
    AZURE_STORAGE_ACCOUNT_NAME="investflowadls" \
    AZURE_STORAGE_ACCOUNT_KEY="$STORAGE_KEY" \
    AZURE_STORAGE_CONTAINER_NAME="documents" \
    CDC_CACHE_CONTAINER_NAME="documents" \
    POSTGRES_HOST="if-postgres.postgres.database.azure.com" \
    POSTGRES_PORT="5432" \
    POSTGRES_DB="investflow" \
    POSTGRES_USER="<your-user>" \
    POSTGRES_PASSWORD="<your-password>"
```

### Step 5: Deploy Frontend

```bash
# Get Backend URL
BACKEND_URL=$(az containerapp show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

# Create Frontend Container App
az containerapp create \
  --name investflow-frontend \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image investflowregistry.azurecr.io/investflow-frontend:latest \
  --registry-server investflowregistry.azurecr.io \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 3000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --env-vars \
    NODE_ENV="production" \
    NEXT_PUBLIC_API_URL="https://$BACKEND_URL/api/v1"
```

### Step 6: Run CDC Cache Migration

```bash
# Sync the CDC cache from Iceberg tables
BACKEND_URL=$(az containerapp show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

# Sync cache
curl -X POST "https://$BACKEND_URL/api/v1/health/cache/sync"

# Verify cache
curl "https://$BACKEND_URL/api/v1/health/cache"
```

---

## 💰 Cost Estimate

| Service | Tier | Est. Cost/Month |
|---------|------|-----------------|
| PostgreSQL Flexible Server | Existing (shared) | $0 |
| ADLS Gen2 Storage | Standard LRS | $5-10 |
| Container Apps - Lakekeeper | 0.5 vCPU, 1GB | $10-20 |
| Container Apps - Backend | 0.5 vCPU, 1GB | $10-30 |
| Container Apps - Frontend | 0.25 vCPU, 0.5GB | $5-15 |
| Container Registry | Basic | $5 |
| Application Insights | Basic | $2-5 |
| Key Vault | Standard | $1 |
| **TOTAL** | | **~$38-85/month** |

---

## 🔒 CDC Cache Details

### What is the CDC Cache?

The CDC (Change Data Capture) cache stores user and sharing data as Parquet files in ADLS for fast authentication lookups.

### Cache Files

| File | Purpose | Update Trigger |
|------|---------|----------------|
| `cdc/users/users_current.parquet` | User auth data | User create/update |
| `cdc/shares/user_shares_current.parquet` | Sharing relationships | Share create/delete |

### Performance Impact

| Operation | Without Cache | With Cache | Improvement |
|-----------|---------------|------------|-------------|
| Login | ~400ms | ~100ms | 4x faster |
| Get Profile | ~200ms | ~5ms | 40x faster |
| Check Sharing | ~300ms | ~1ms | 300x faster |

### Cache Management APIs

```bash
# View cache status
GET /api/v1/health/cache

# Force sync from Iceberg
POST /api/v1/health/cache/sync

# Invalidate cache (rebuilds on next access)
POST /api/v1/health/cache/invalidate
```

### Migration Script

The backend includes a migration script for initial cache population:

```bash
# Run in container
docker exec investflow-backend python migrate_user_cache.py

# Or use the API
curl -X POST https://<backend-url>/api/v1/health/cache/sync
```

---

## 🔍 Monitoring & Troubleshooting

### View Container Logs

```bash
# Backend logs
az containerapp logs show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --follow

# Frontend logs
az containerapp logs show \
  --name investflow-frontend \
  --resource-group investflow-rg \
  --follow

# Lakekeeper logs
az containerapp logs show \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --follow
```

### Health Checks

```bash
# Backend health
curl https://<backend-url>/health

# Cache status
curl https://<backend-url>/api/v1/health/cache

# Lakekeeper health
curl https://<lakekeeper-url>/health
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Login 401 Unauthorized | Run cache sync: `POST /api/v1/health/cache/sync` |
| Cache shows 0 users | Run migration or sync endpoint |
| Lakekeeper connection failed | Check POSTGRES_CONNECTION_STRING |
| CORS errors | Verify CORS_ORIGINS includes frontend URL |

---

## 📝 Post-Deployment Checklist

- [ ] All containers running (`az containerapp list -g investflow-rg`)
- [ ] Frontend loads at `https://investflow-frontend.*.azurecontainerapps.io`
- [ ] Backend health check returns OK
- [ ] CDC cache populated (`/api/v1/health/cache` shows users > 0)
- [ ] Can register new user
- [ ] Can login with existing user
- [ ] Properties load correctly
- [ ] Sharing works between users
- [ ] Documents upload to ADLS

---

## 🔄 CI/CD Pipeline

The `.github/workflows/deploy.yml` handles:

1. **Build** - Creates Docker images for backend and frontend
2. **Push** - Pushes to Azure Container Registry
3. **Deploy Lakekeeper** - Creates/updates Lakekeeper container
4. **Deploy Backend** - Creates/updates backend container
5. **Deploy Frontend** - Creates/updates frontend container
6. **Migration** - Runs CDC cache sync

**Trigger**: Push to `main` branch or manual workflow dispatch.

---

## 📚 Resources

- [Azure Container Apps Docs](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Lakekeeper Documentation](https://lakekeeper.io/)
- [Apache Iceberg](https://iceberg.apache.org/)
- [CDC Cache Implementation](./backend/app/services/auth_cache_service.py)

---

**Created**: 2025-11-30  
**Last Updated**: 2025-12-04  
**Status**: Ready for deployment 🚀
