#!/bin/bash
# Script to gather all GitHub Secrets for InvestFlow deployment
# Run this from project root: ./scripts/get-github-secrets.sh

set -e

echo "========================================"
echo "  InvestFlow GitHub Secrets Setup"
echo "========================================"
echo ""

# Check if logged in to Azure
if ! az account show &>/dev/null; then
    echo "❌ Not logged in to Azure CLI"
    echo "   Run: az login"
    exit 1
fi

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
RESOURCE_GROUP="investflow-rg"

echo "📍 Subscription: $SUBSCRIPTION_ID"
echo "📍 Resource Group: $RESOURCE_GROUP"
echo ""

echo "========================================"
echo "  Copy these values to GitHub Secrets"
echo "========================================"
echo ""

# ACR Credentials
echo "🔐 ACR_USERNAME:"
az acr credential show --name investflowregistry --query username -o tsv 2>/dev/null || echo "ERROR: Could not get ACR username"
echo ""

echo "🔐 ACR_PASSWORD:"
az acr credential show --name investflowregistry --query "passwords[0].value" -o tsv 2>/dev/null || echo "ERROR: Could not get ACR password"
echo ""

# Storage
echo "🔐 AZURE_STORAGE_ACCOUNT_NAME:"
echo "investflowadls"
echo ""

echo "🔐 AZURE_STORAGE_ACCOUNT_KEY:"
az storage account keys list --account-name investflowadls --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv 2>/dev/null || echo "ERROR: Could not get storage key"
echo ""

# PostgreSQL
echo "🔐 POSTGRES_HOST:"
echo "if-postgres.postgres.database.azure.com"
echo ""

echo "🔐 POSTGRES_DB:"
echo "if-postgres"
echo ""

echo "🔐 POSTGRES_USER:"
echo "pgadmin"
echo ""

echo "🔐 POSTGRES_PASSWORD:"
echo "[Enter your PostgreSQL password]"
echo ""

echo "🔐 POSTGRES_CONNECTION_STRING:"
echo "postgresql://pgadmin:YOUR_PASSWORD@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require"
echo "(Replace YOUR_PASSWORD with actual password)"
echo ""

# App secrets
echo "🔐 APP_SECRET_KEY (generate new or use existing):"
if [ -f "backend/.env" ]; then
    grep "^SECRET_KEY=" backend/.env 2>/dev/null | cut -d'=' -f2 || openssl rand -base64 32
else
    openssl rand -base64 32
fi
echo ""

echo "🔐 LAKEKEEPER_ENCRYPTION_KEY (use existing from local .env!):"
if [ -f "backend/.env" ]; then
    grep "^LAKEKEEPER__PG_ENCRYPTION_KEY=" backend/.env 2>/dev/null | cut -d'=' -f2 || echo "[Check your backend/.env file]"
else
    echo "[Check your backend/.env file]"
fi
echo "⚠️  WARNING: Must match local .env if sharing database!"
echo ""

# Azure Credentials
echo "🔐 AZURE_CREDENTIALS:"
echo "Run this command and copy the ENTIRE JSON output:"
echo ""
echo "az ad sp create-for-rbac \\"
echo "  --name \"investflow-github-actions\" \\"
echo "  --role contributor \\"
echo "  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \\"
echo "  --sdk-auth"
echo ""

echo "========================================"
echo "  Add Secrets at:"
echo "  https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions"
echo "========================================"

