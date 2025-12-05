# GitHub Secrets Setup for Azure Deployment

This document outlines all GitHub Secrets required for CI/CD deployment to Azure Container Apps.

## Quick Setup

Run this script to get all secret values (requires Azure CLI logged in):

```bash
# Run from project root
./scripts/get-github-secrets.sh
```

Or manually gather secrets using the commands below.

## Required Secrets

### 1. Azure Authentication

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON for Azure login |

```bash
# Create service principal and get JSON credentials
# Replace <SUBSCRIPTION_ID> with your Azure subscription ID
az ad sp create-for-rbac \
  --name "investflow-github-actions" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/investflow-rg \
  --sdk-auth

# Copy the ENTIRE JSON output as the secret value
```

### 2. Azure Container Registry (ACR)

| Secret | Description |
|--------|-------------|
| `ACR_USERNAME` | ACR admin username |
| `ACR_PASSWORD` | ACR admin password |

```bash
# Enable admin user (if not already enabled)
az acr update --name investflowregistry --admin-enabled true

# Get username
az acr credential show --name investflowregistry --query username -o tsv

# Get password
az acr credential show --name investflowregistry --query "passwords[0].value" -o tsv
```

### 3. PostgreSQL Database

| Secret | Description | Example |
|--------|-------------|---------|
| `POSTGRES_HOST` | PostgreSQL server hostname | `if-postgres.postgres.database.azure.com` |
| `POSTGRES_DB` | Database name | `if-postgres` |
| `POSTGRES_USER` | Database username | `pgadmin` |
| `POSTGRES_PASSWORD` | Database password | Your password |
| `POSTGRES_CONNECTION_STRING` | Full connection string for Lakekeeper | See below |

```bash
# Build connection string (for POSTGRES_CONNECTION_STRING secret)
# Format: postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
postgresql://pgadmin:YOUR_PASSWORD@if-postgres.postgres.database.azure.com:5432/if-postgres?sslmode=require
```

### 4. Azure Storage (ADLS Gen2)

| Secret | Description |
|--------|-------------|
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name (`investflowadls`) |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account access key |

```bash
# Get storage account key
az storage account keys list \
  --account-name investflowadls \
  --resource-group investflow-rg \
  --query "[0].value" -o tsv
```

### 5. Application Secrets

| Secret | Description |
|--------|-------------|
| `APP_SECRET_KEY` | JWT signing key (min 32 chars) |
| `LAKEKEEPER_ENCRYPTION_KEY` | Lakekeeper encryption key for secrets |

```bash
# Generate new keys (ONLY for fresh deployments)
# WARNING: Changing LAKEKEEPER_ENCRYPTION_KEY will break existing secrets!
openssl rand -base64 32
```

⚠️ **IMPORTANT**: The `LAKEKEEPER_ENCRYPTION_KEY` must match between local and Azure deployments if sharing the same PostgreSQL database. Check your local `.env` file for the current key.

## Complete Secrets Checklist

Copy this checklist and add each secret to GitHub:

- [ ] `AZURE_CREDENTIALS` - Service principal JSON
- [ ] `ACR_USERNAME` - Container registry username
- [ ] `ACR_PASSWORD` - Container registry password
- [ ] `POSTGRES_HOST` - Database hostname
- [ ] `POSTGRES_DB` - Database name
- [ ] `POSTGRES_USER` - Database username
- [ ] `POSTGRES_PASSWORD` - Database password
- [ ] `POSTGRES_CONNECTION_STRING` - Full PostgreSQL URL for Lakekeeper
- [ ] `AZURE_STORAGE_ACCOUNT_NAME` - Storage account name
- [ ] `AZURE_STORAGE_ACCOUNT_KEY` - Storage account key
- [ ] `APP_SECRET_KEY` - JWT secret key
- [ ] `LAKEKEEPER_ENCRYPTION_KEY` - Lakekeeper encryption key

## How to Add Secrets in GitHub

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Enter the secret name exactly as shown above
5. Paste the secret value
6. Click **"Add secret"**

## Workflow Triggers

The deployment workflow triggers on:

1. **Push to main** - Automatic deployment
2. **Manual trigger** - Go to Actions → "Deploy to Azure" → "Run workflow"

Manual triggers allow you to:
- Deploy only backend or frontend
- Skip CDC cache migration
- Deploy specific services

## Troubleshooting

### "Login failed" errors
- Verify `AZURE_CREDENTIALS` JSON is complete and valid
- Check service principal has Contributor role on the resource group
- Ensure the service principal hasn't expired

### "ACR authentication failed"
- Ensure admin user is enabled on ACR
- Verify `ACR_USERNAME` and `ACR_PASSWORD` are correct
- Try regenerating ACR credentials

### "Database connection failed"
- Check `POSTGRES_HOST` is the full FQDN
- Verify firewall allows Azure services
- Ensure SSL mode is set to `require` in connection string

### "SecretFetchError: Wrong key or corrupt data"
- The `LAKEKEEPER_ENCRYPTION_KEY` doesn't match
- Check your local `.env` for the correct key
- Update the GitHub secret to match

### Frontend shows "localhost:8000" in production
- The `NEXT_PUBLIC_API_URL` build arg wasn't passed correctly
- Re-run the deployment workflow
- Check the backend URL is correct in workflow logs

## Security Best Practices

- ✅ Never commit secrets to the repository
- ✅ Rotate secrets regularly (every 90 days)
- ✅ Use unique passwords for each service
- ✅ Monitor GitHub Actions logs for secret exposure
- ✅ Consider Azure Key Vault for production secrets
