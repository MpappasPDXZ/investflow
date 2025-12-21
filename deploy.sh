#!/bin/bash
# InvestFlow Azure Deployment Script
# Run this from the project root: /Users/matt/code/property

set -e  # Exit on error

echo "=========================================="
echo "InvestFlow Azure Deployment"
echo "=========================================="

# Configuration
RESOURCE_GROUP="investflow-rg"
ACR_NAME="investflowregistry"
ACR_SERVER="investflowregistry.azurecr.io"
ENVIRONMENT="investflow-env"
LOCATION="eastus"

# PostgreSQL Config
POSTGRES_HOST="if-postgres.postgres.database.azure.com"
POSTGRES_PORT="5432"
POSTGRES_DB="if-postgres"
POSTGRES_USER="pgadmin"
POSTGRES_PASSWORD="pass1234!"

# Get dynamic values
echo ""
echo "Step 1: Getting Azure credentials..."
STORAGE_KEY=$(az storage account keys list --account-name investflowadls --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv)
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Generate secrets
SECRET_KEY=$(openssl rand -base64 32)
LAKEKEEPER_ENCRYPTION_KEY=$(openssl rand -base64 32)

echo "  ✓ Storage Key retrieved"
echo "  ✓ ACR credentials retrieved"
echo "  ✓ Secrets generated"

# Step 2: Build and Push Images
echo ""
echo "Step 2: Building and pushing Docker images..."

# Login to ACR
az acr login --name $ACR_NAME

# Build and push Backend
echo "  Building backend..."
cd backend
docker build --platform linux/amd64 -t $ACR_SERVER/investflow-backend:latest .
docker push $ACR_SERVER/investflow-backend:latest
echo "  ✓ Backend image pushed"

# Build and push Frontend
echo "  Building frontend..."
cd ../frontend

# Get Backend URL first (may already exist)
BACKEND_FQDN=$(az containerapp show --name investflow-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv 2>/dev/null || echo "investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io")
echo "  Using backend URL: https://$BACKEND_FQDN"

# Pass the production API URL as build arg so Next.js bakes it in
docker build --platform linux/amd64 \
  --build-arg NEXT_PUBLIC_API_URL=https://$BACKEND_FQDN \
  -t $ACR_SERVER/investflow-frontend:latest .
docker push $ACR_SERVER/investflow-frontend:latest
echo "  ✓ Frontend image pushed"

cd ..

# Step 3: Deploy Lakekeeper
echo ""
echo "Step 3: Deploying Lakekeeper..."

LAKEKEEPER_POSTGRES_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}?sslmode=require"

az containerapp create \
  --name investflow-lakekeeper \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image quay.io/lakekeeper/catalog:latest \
  --target-port 8181 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    "LAKEKEEPER__PG_DATABASE_URL_READ=$LAKEKEEPER_POSTGRES_URL" \
    "LAKEKEEPER__PG_DATABASE_URL_WRITE=$LAKEKEEPER_POSTGRES_URL" \
    "LAKEKEEPER__PG_ENCRYPTION_KEY=$LAKEKEEPER_ENCRYPTION_KEY" \
    "LAKEKEEPER__DEBUG__AUTO_SERVE=true" \
    "LAKEKEEPER__DEBUG__MIGRATE_BEFORE_SERVE=true" \
  2>/dev/null || az containerapp update \
    --name investflow-lakekeeper \
    --resource-group $RESOURCE_GROUP \
    --image quay.io/lakekeeper/catalog:latest

echo "  ✓ Lakekeeper deployed"

# Get Lakekeeper URL
LAKEKEEPER_FQDN=$(az containerapp show --name investflow-lakekeeper --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)
echo "  Lakekeeper URL: https://$LAKEKEEPER_FQDN"

# Step 4: Deploy Backend
echo ""
echo "Step 4: Deploying Backend..."

az containerapp create \
  --name investflow-backend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image $ACR_SERVER/investflow-backend:latest \
  --registry-server $ACR_SERVER \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --env-vars \
    "ENVIRONMENT=production" \
    "SECRET_KEY=$SECRET_KEY" \
    "ALGORITHM=HS256" \
    "ACCESS_TOKEN_EXPIRE_MINUTES=60" \
    "CORS_ORIGINS=*" \
    "LAKEKEEPER__BASE_URI=https://$LAKEKEEPER_FQDN" \
    "LAKEKEEPER__WAREHOUSE_NAME=lakekeeper" \
    "AZURE_STORAGE_ACCOUNT_NAME=investflowadls" \
    "AZURE_STORAGE_ACCOUNT_KEY=$STORAGE_KEY" \
    "AZURE_STORAGE_CONTAINER_NAME=documents" \
    "POSTGRES_HOST=$POSTGRES_HOST" \
    "POSTGRES_PORT=$POSTGRES_PORT" \
    "POSTGRES_DB=$POSTGRES_DB" \
    "POSTGRES_USER=$POSTGRES_USER" \
    "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" \
  2>/dev/null || az containerapp update \
    --name investflow-backend \
    --resource-group $RESOURCE_GROUP \
    --image $ACR_SERVER/investflow-backend:latest

echo "  ✓ Backend deployed"

# Get Backend URL
BACKEND_FQDN=$(az containerapp show --name investflow-backend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)
echo "  Backend URL: https://$BACKEND_FQDN"

# Step 5: Deploy Frontend
echo ""
echo "Step 5: Deploying Frontend..."

az containerapp create \
  --name investflow-frontend \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image $ACR_SERVER/investflow-frontend:latest \
  --registry-server $ACR_SERVER \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 3000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --env-vars \
    "NODE_ENV=production" \
    "NEXT_PUBLIC_API_URL=https://$BACKEND_FQDN" \
  2>/dev/null || az containerapp update \
    --name investflow-frontend \
    --resource-group $RESOURCE_GROUP \
    --image $ACR_SERVER/investflow-frontend:latest

echo "  ✓ Frontend deployed"

# Get Frontend URL
FRONTEND_FQDN=$(az containerapp show --name investflow-frontend --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)

# Summary
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "URLs:"
echo "  Frontend:   https://$FRONTEND_FQDN"
echo "  Backend:    https://$BACKEND_FQDN"
echo "  Lakekeeper: https://$LAKEKEEPER_FQDN"
echo ""
echo "Next steps:"
echo "  1. Visit the frontend URL to test the app"
echo "  2. Check backend health: curl https://$BACKEND_FQDN/api/v1/health"
echo "  3. If needed, sync CDC cache: curl -X POST https://$BACKEND_FQDN/api/v1/health/cache/sync"
echo ""

