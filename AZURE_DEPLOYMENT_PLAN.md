# InvestFlow Azure Deployment Plan

## 📋 Overview

Deploy the InvestFlow property management application to Azure using Container Apps for serverless container hosting with Lakekeeper for Iceberg catalog management.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Resource Group                      │
│                      investflow-rg                           │
└─────────────────────────────────────────────────────────────┘
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
                              │                     │
                              ▼                     ▼
                     ┌─────────────┐      ┌─────────────┐
                     │   ADLS      │      │ PostgreSQL  │
                     │   Gen2      │      │   Flex      │
                     │ (Iceberg)   │      │  (Catalog)  │
                     └─────────────┘      └─────────────┘
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

---

## 🚀 Deployment Steps

### Phase 1: Database Setup (Use Existing)

**✅ PostgreSQL server already exists - just create Lakekeeper database**

```bash
# Assuming your existing PostgreSQL server details:
# Server: <your-postgres-server>.postgres.database.azure.com
# Admin: <your-admin-user>

# Create database for Lakekeeper (if not exists)
az postgres flexible-server db create \
  --resource-group investflow-rg \
  --server-name <your-postgres-server> \
  --database-name lakekeeper

# Ensure Azure services can access the database
az postgres flexible-server firewall-rule create \
  --resource-group investflow-rg \
  --name <your-postgres-server> \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Store connection string in Key Vault
# Replace with your actual server details
CONNECTION_STRING="postgresql://<admin-user>:<password>@<your-postgres-server>.postgres.database.azure.com:5432/lakekeeper?sslmode=require"
az keyvault secret set \
  --vault-name investflow-kv \
  --name PostgresConnectionString \
  --value "$CONNECTION_STRING"
```

**Cost**: $0 (using existing server)

---

### Phase 2: Container Images

**Build and push Docker images to ACR**

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

# Build and push Lakekeeper (if custom build needed)
# Or use official image: ghcr.io/lakekeeper/lakekeeper:latest
```

---

### Phase 3: Deploy Container Apps

#### 3.1 Deploy Lakekeeper Container App

```bash
# Get secrets from Key Vault
POSTGRES_URL=$(az keyvault secret show --vault-name investflow-kv --name PostgresConnectionString --query value -o tsv)
ADLS_KEY=$(az keyvault secret show --vault-name investflow-kv --name ADLSStorageAccountKey --query value -o tsv)

# Deploy Lakekeeper
az containerapp create \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image ghcr.io/lakekeeper/lakekeeper:latest \
  --target-port 8181 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    LAKEKEEPER__PG_DATABASE_URL_READ="$POSTGRES_URL" \
    LAKEKEEPER__PG_DATABASE_URL_WRITE="$POSTGRES_URL" \
    LAKEKEEPER__PG_ENCRYPTION_KEY="$(openssl rand -base64 32)" \
    LAKEKEEPER__AZURE_STORAGE_ACCOUNT_NAME="investflowadls" \
    LAKEKEEPER__AZURE_STORAGE_ACCOUNT_KEY="$ADLS_KEY" \
    LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS="true"
```

**Cost**: ~$10-20/month (0.5 vCPU, 1GB RAM)

#### 3.2 Deploy Backend Container App

```bash
# Get Lakekeeper URL
LAKEKEEPER_URL=$(az containerapp show \
  --name investflow-lakekeeper \
  --resource-group investflow-rg \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

ADLS_CONNECTION=$(az storage account show-connection-string \
  --name investflowadls \
  --resource-group investflow-rg \
  --query connectionString -o tsv)

# Deploy Backend
az containerapp create \
  --name investflow-backend \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image investflowregistry.azurecr.io/investflow-backend:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --registry-server investflowregistry.azurecr.io \
  --registry-identity system \
  --env-vars \
    ENVIRONMENT="production" \
    SECRET_KEY="$(openssl rand -base64 32)" \
    CORS_ORIGINS="https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io" \
    LAKEKEEPER__BASE_URI="https://$LAKEKEEPER_URL" \
    LAKEKEEPER__WAREHOUSE_NAME="investflow" \
    AZURE_STORAGE_CONNECTION_STRING="$ADLS_CONNECTION" \
    AZURE_STORAGE_CONTAINER_NAME="documents" \
    APPLICATIONINSIGHTS_CONNECTION_STRING="@Microsoft.KeyVault(SecretUri=https://investflow-kv.vault.azure.net/secrets/AppInsightsConnectionString/)"
```

**Cost**: ~$10-30/month (0.5 vCPU, 1GB RAM, scales 1-3)

#### 3.3 Deploy Frontend Container App

```bash
# Get Backend URL
BACKEND_URL=$(az containerapp show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

# Deploy Frontend
az containerapp create \
  --name investflow-frontend \
  --resource-group investflow-rg \
  --environment investflow-env \
  --image investflowregistry.azurecr.io/investflow-frontend:latest \
  --target-port 3000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --registry-server investflowregistry.azurecr.io \
  --registry-identity system \
  --env-vars \
    NEXT_PUBLIC_API_URL="https://$BACKEND_URL/api/v1"
```

**Cost**: ~$5-15/month (0.25 vCPU, 0.5GB RAM, scales 1-3)

---

### Phase 4: Configure Custom Domain (Optional)

```bash
# Add custom domain to frontend
az containerapp hostname add \
  --name investflow-frontend \
  --resource-group investflow-rg \
  --hostname app.investflow.com

# Add custom domain to backend  
az containerapp hostname add \
  --name investflow-backend \
  --resource-group investflow-rg \
  --hostname api.investflow.com
```

---

## 💰 Total Monthly Cost Estimate

| Service | Tier | Est. Cost |
|---------|------|-----------|
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

## 🔐 Security Best Practices

### Managed Identity Setup

```bash
# Enable system-assigned managed identity for backend
az containerapp identity assign \
  --name investflow-backend \
  --resource-group investflow-rg \
  --system-assigned

# Grant access to Key Vault
BACKEND_IDENTITY=$(az containerapp identity show \
  --name investflow-backend \
  --resource-group investflow-rg \
  --query principalId -o tsv)

az keyvault set-policy \
  --name investflow-kv \
  --object-id $BACKEND_IDENTITY \
  --secret-permissions get list

# Grant access to ADLS
az role assignment create \
  --assignee $BACKEND_IDENTITY \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/investflow-rg/providers/Microsoft.Storage/storageAccounts/investflowadls"
```

---

## 📊 Monitoring & Observability

### Application Insights Configuration

```bash
# All logs automatically flow to Application Insights
# View logs in Azure Portal:
# https://portal.azure.com -> Application Insights -> investflow-insights

# Query example (in Logs section):
traces
| where customDimensions.container == "investflow-backend"
| order by timestamp desc
| take 100
```

---

## 🚨 Troubleshooting

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

### Test Connectivity

```bash
# Test backend health
curl https://$(az containerapp show --name investflow-backend --resource-group investflow-rg --query properties.configuration.ingress.fqdn -o tsv)/api/v1/health

# Test Lakekeeper
curl https://$(az containerapp show --name investflow-lakekeeper --resource-group investflow-rg --query properties.configuration.ingress.fqdn -o tsv)/catalog/v1/config
```

---

## 🔄 CI/CD Setup (GitHub Actions)

### Required GitHub Secrets

```bash
# Add these secrets to your GitHub repository
# Settings -> Secrets and variables -> Actions

AZURE_CREDENTIALS          # Service principal JSON
ACR_LOGIN_SERVER          # investflowregistry.azurecr.io
ACR_USERNAME              # Service principal app ID
ACR_PASSWORD              # Service principal password
AZURE_RESOURCE_GROUP      # investflow-rg
```

### Sample GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Login to ACR
        run: |
          echo ${{ secrets.ACR_PASSWORD }} | docker login \
            ${{ secrets.ACR_LOGIN_SERVER }} \
            -u ${{ secrets.ACR_USERNAME }} \
            --password-stdin
      
      - name: Build and push backend
        run: |
          cd backend
          docker build -t ${{ secrets.ACR_LOGIN_SERVER }}/investflow-backend:${{ github.sha }} .
          docker push ${{ secrets.ACR_LOGIN_SERVER }}/investflow-backend:${{ github.sha }}
      
      - name: Build and push frontend
        run: |
          cd frontend
          docker build -t ${{ secrets.ACR_LOGIN_SERVER }}/investflow-frontend:${{ github.sha }} .
          docker push ${{ secrets.ACR_LOGIN_SERVER }}/investflow-frontend:${{ github.sha }}
      
      - name: Deploy backend
        run: |
          az containerapp update \
            --name investflow-backend \
            --resource-group ${{ secrets.AZURE_RESOURCE_GROUP }} \
            --image ${{ secrets.ACR_LOGIN_SERVER }}/investflow-backend:${{ github.sha }}
      
      - name: Deploy frontend
        run: |
          az containerapp update \
            --name investflow-frontend \
            --resource-group ${{ secrets.AZURE_RESOURCE_GROUP }} \
            --image ${{ secrets.ACR_LOGIN_SERVER }}/investflow-frontend:${{ github.sha }}
```

---

## 📝 Post-Deployment Checklist

- [ ] Verify all containers are running
- [ ] Test frontend URL loads
- [ ] Test backend API health endpoint
- [ ] Create initial user via backend API
- [ ] Test creating a property
- [ ] Verify data is stored in ADLS
- [ ] Check Application Insights for logs
- [ ] Set up alerts for errors
- [ ] Configure backups for PostgreSQL
- [ ] Document final URLs for team

---

## 🎯 Next Steps

1. **Immediate**: Deploy Lakekeeper + PostgreSQL
2. **Day 1**: Deploy Backend with Iceberg integration
3. **Day 2**: Deploy Frontend, test end-to-end
4. **Week 1**: Set up CI/CD pipeline
5. **Week 2**: Add custom domain, SSL certificates
6. **Month 1**: Monitor costs, optimize resources

---

## 📚 Additional Resources

- [Azure Container Apps Docs](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Lakekeeper Documentation](https://github.com/lakekeeper/lakekeeper)
- [Apache Iceberg on Azure](https://iceberg.apache.org/)
- [ADLS Gen2 Best Practices](https://learn.microsoft.com/en-us/azure/storage/blobs/data-lake-storage-best-practices)

---

**Created**: 2025-11-30  
**Last Updated**: 2025-11-30  
**Status**: Ready for deployment 🚀

