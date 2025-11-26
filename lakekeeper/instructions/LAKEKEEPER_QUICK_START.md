# Lakekeeper Quick Start

## Configuration Summary

Lakekeeper is configured with:
- **Object Store**: Azure Data Lake Storage (ADLS) Gen2
- **Persistence Backend**: **SAME PostgreSQL database as your backend** (shared)
- **Secret Store**: Same PostgreSQL instance
- **Authentication**: OAuth2 with Azure AD (required)

## Important: Shared Database

✅ **Lakekeeper uses the SAME PostgreSQL database as your backend**
- Connection strings are automatically built from your `POSTGRES_*` variables
- No separate database needed - saves money!
- Lakekeeper creates its own tables in your existing database

## Prerequisites

1. **Azure AD Tenant** with App Registration permissions
2. **Azure PostgreSQL** (version 15+) with `uuid-ossp` extension enabled
3. **Azure ADLS Gen2** storage account
4. **Docker and Docker Compose** installed

## Quick Setup Steps

### Step 1: Enable PostgreSQL Extension (REQUIRED)

**Before running migrations**, enable the `uuid-ossp` extension in Azure PostgreSQL:

1. Go to **Azure Portal** → Your PostgreSQL server
2. Navigate to **"Server parameters"**
3. Search for `azure.extensions`
4. Add `uuid-ossp` to the allow-list
5. **Save and restart the server**

⚠️ **This must be done BEFORE running migrations!**

### Step 2: Configure Environment Variables

Update `backend/.env` file with your PostgreSQL and Azure ADLS configuration:

```bash
# Your existing PostgreSQL (used by both backend and Lakekeeper)
POSTGRES_HOST=your-postgres-server.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=your_database_name
POSTGRES_USER=your_admin_user
POSTGRES_PASSWORD=your_password

# Azure ADLS Gen2 Configuration
AZURE_STORAGE_ACCOUNT_NAME=investflowadls
AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key
AZURE_STORAGE_CONTAINER_NAME=documents

# Lakekeeper Encryption Key (generate a strong random key, min 32 characters)
LAKEKEEPER__PG_ENCRYPTION_KEY=your-secret-encryption-key-here-min-32-chars

# Lakekeeper Base URI
LAKEKEEPER__BASE_URI=http://localhost:8181

# Default warehouse name
LAKEKEEPER__WAREHOUSE_NAME=lakekeeper
```

**Note**: The `LAKEKEEPER__PG_DATABASE_URL_*` variables are automatically constructed from `POSTGRES_*` variables in docker-compose.yml.

### Step 3: Set Up OAuth2 with Azure AD (REQUIRED)

OAuth2 authentication is **required** for Lakekeeper. Use the interactive configuration script:

```bash
cd lakekeeper
./configure_oauth2.sh
```

This script will guide you through:
1. **Azure AD Tenant ID** - Your Azure AD directory ID
2. **Lakekeeper API App Registration**:
   - Application (client) ID
   - Application ID URI (e.g., `api://lakekeeper`)
3. **Backend Service Account App Registration**:
   - Application (client) ID
   - Client Secret value
4. **Optional: Lakekeeper UI App Registration** (for user login)

The script will automatically:
- Set `LAKEKEEPER__OPENID_PROVIDER_URI` (correct format without `/.well-known/openid-configuration`)
- Set `LAKEKEEPER__OPENID_AUDIENCE` (your API Application ID URI)
- Set `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS` (for Azure AD compatibility: `https://sts.windows.net/{TENANT_ID}/`)
- Set backend OAuth2 credentials for service account authentication

**Manual Configuration** (if not using the script):

```bash
# Lakekeeper OAuth2 Configuration (for validating incoming tokens)
LAKEKEEPER__OPENID_PROVIDER_URI=https://login.microsoftonline.com/{TENANT_ID}/v2.0
LAKEKEEPER__OPENID_AUDIENCE=api://{LAKEKEEPER_API_CLIENT_ID}
LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS=https://sts.windows.net/{TENANT_ID}/

# Backend OAuth2 Configuration (for service account authentication)
LAKEKEEPER__OAUTH2__CLIENT_ID={BACKEND_SERVICE_CLIENT_ID}
LAKEKEEPER__OAUTH2__CLIENT_SECRET={BACKEND_SERVICE_CLIENT_SECRET}
LAKEKEEPER__OAUTH2__TENANT_ID={TENANT_ID}
LAKEKEEPER__OAUTH2__SCOPE=api://{LAKEKEEPER_API_CLIENT_ID}/.default
```

⚠️ **Important**: 
- `LAKEKEEPER__OPENID_PROVIDER_URI` should **NOT** include `/.well-known/openid-configuration` (Lakekeeper adds it automatically)
- `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS` is required for Azure AD token issuer compatibility

See `OAUTH2_SETUP.md` for detailed Azure AD App Registration setup instructions.

### Step 4: Run Database Migrations

Create Lakekeeper tables in your PostgreSQL database:

```bash
cd backend
docker-compose run --rm lakekeeper migrate
```

This creates all necessary tables in your shared PostgreSQL database.

### Step 5: Start Lakekeeper

```bash
cd backend
docker-compose up -d lakekeeper
```

### Step 6: Verify OAuth2 Configuration

Check Lakekeeper logs to confirm OAuth2 is configured:

```bash
docker-compose logs lakekeeper | grep -i "oidc\|oauth\|running"
```

You should see:
```
Running with OIDC authentication.
```

If you see errors about OpenID configuration, check:
- `LAKEKEEPER__OPENID_PROVIDER_URI` format (no `/.well-known/openid-configuration`)
- `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS` is set correctly
- Container has network access to Azure AD endpoints

### Step 7: Access Lakekeeper UI

Open `http://localhost:8181` in your browser.

**Note**: If OAuth2 UI is configured, you'll need to authenticate. Otherwise, the API will still work with OAuth2 service account authentication.

### Step 8: Configure ADLS Warehouse

In the Lakekeeper UI or via API:

1. **Create a warehouse** with Azure ADLS Gen2 credentials
2. **Storage Path**: MUST start with `abfss://`
   - Format: `abfss://container@storageaccount.dfs.core.windows.net/path`
   - Example: `abfss://documents@investflowadls.dfs.core.windows.net/lakekeeper`
3. **Storage Account**: Your ADLS Gen2 account name
4. **Container**: Your container name (e.g., `documents`)
5. **Authentication**: Use Azure App Registration with roles:
   - `Storage Blob Data Contributor`
   - `Storage Blob Delegator`

## Backend Integration with PyIceberg

Your FastAPI backend uses **PyIceberg** to interact with Lakekeeper:

```python
from app.services.pyiceberg_service import get_pyiceberg_service

# Get PyIceberg service (automatically configured with OAuth2)
pyiceberg = get_pyiceberg_service()

# Read data
df = pyiceberg.read_table(("namespace",), "table_name")

# Write data
pyiceberg.append_data(("namespace",), "table_name", pandas_dataframe)
```

The backend automatically:
- Acquires OAuth2 tokens from Azure AD using client credentials flow
- Configures PyIceberg REST catalog with OAuth2 authentication
- Handles token refresh automatically

## Important Notes

- **PostgreSQL Version**: Requires PostgreSQL 15 or higher
- **PostgreSQL Extension**: **MUST enable `uuid-ossp` extension** in Azure PostgreSQL before migrations
- **Database**: Uses the SAME database as your backend (shared)
- **OAuth2**: Required for Lakekeeper API access (no "allowall" mode in production)
- **OpenID Provider URI**: Do NOT include `/.well-known/openid-configuration` suffix
- **Additional Issuers**: Required for Azure AD compatibility (`https://sts.windows.net/{TENANT_ID}/`)
- **Azure App Registration**: Required for ADLS authentication
  - Assign roles: `Storage Blob Data Contributor` and `Storage Blob Delegator`
- **Encryption Key**: Must be at least 32 characters, keep it secure

## Troubleshooting

### OAuth2 Configuration Errors

**Error**: `Failed to parse openid configuration. Expected fields: ["jwks_uri", "issuer"]`
- **Fix**: Check `LAKEKEEPER__OPENID_PROVIDER_URI` - it should NOT include `/.well-known/openid-configuration`
- **Fix**: Ensure `LAKEKEEPER__OPENID_ADDITIONAL_ISSUERS` is set for Azure AD

**Error**: `401 Unauthorized` when backend calls Lakekeeper
- **Fix**: Verify backend OAuth2 credentials are set correctly
- **Fix**: Check that backend service account has permission to access Lakekeeper API scope
- **Fix**: Verify token endpoint is accessible from container

### Database Migration Errors

**Error**: `extension "uuid-ossp" does not exist`
- **Fix**: Enable `uuid-ossp` extension in Azure PostgreSQL server parameters before running migrations

### Container Issues

**Error**: Container cannot reach Azure AD endpoints
- **Fix**: Ensure container has internet access
- **Fix**: Check DNS resolution from within container

## Next Steps

- See `OAUTH2_SETUP.md` for detailed Azure AD App Registration setup
- See `LAKEKEEPER_SETUP.md` for advanced configuration options
- Test integration: `docker-compose exec backend uv run python app/scripts/test_table_creation.py`
