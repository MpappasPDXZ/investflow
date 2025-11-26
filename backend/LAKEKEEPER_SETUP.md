# Lakekeeper Setup Guide

## Overview

Lakekeeper is a data lake management tool configured to use:
- **Object Store**: Azure Data Lake Storage (ADLS) Gen2
- **Persistence Backend**: **SAME PostgreSQL database as your backend** (shared database)
- **Secret Store**: Same PostgreSQL instance

## Important: Shared PostgreSQL Database

**Lakekeeper uses the SAME PostgreSQL database as your backend application.** This means:
- ✅ Single database to manage
- ✅ Lower costs (one database instead of two)
- ✅ Lakekeeper creates its own tables in the same database
- ✅ All data persisted in one place

The connection strings are automatically constructed from your `POSTGRES_*` environment variables in `docker-compose.yml`.

## Prerequisites

1. **Azure PostgreSQL Database** (version 15+)
   - **Use your existing backend PostgreSQL database**
   - Ensure PostgreSQL version is 15 or higher
   - Ensure firewall rules allow connections from your deployment location

2. **Azure Data Lake Storage Gen2**
   - Storage account: `investflowadls` (already configured)
   - Container/filesystem for Lakekeeper data

3. **Azure App Registration** (for ADLS authentication)
   - Create an App Registration in Azure AD
   - Generate a client secret
   - Assign roles to the App Registration:
     - `Storage Blob Data Contributor`
     - `Storage Blob Delegator`
   - Note the following values:
     - Application (client) ID
     - Client secret value
     - Directory (tenant) ID

## Configuration

### 1. Update `.env` file

Make sure your `.env` file has your PostgreSQL credentials:

```bash
# Your existing PostgreSQL configuration (used by both backend and Lakekeeper)
POSTGRES_HOST=your-postgres-server.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=your_database_name
POSTGRES_USER=your_admin_user
POSTGRES_PASSWORD=your_password

# Lakekeeper Encryption Key (generate a strong random key, min 32 chars)
LAKEKEEPER__PG_ENCRYPTION_KEY=your-secret-encryption-key-here
```

**Note**: The `LAKEKEEPER__PG_DATABASE_URL_READ` and `LAKEKEEPER__PG_DATABASE_URL_WRITE` are automatically constructed from the `POSTGRES_*` variables above in `docker-compose.yml`.

### 2. Enable PostgreSQL Extension (Required for Azure PostgreSQL)

**IMPORTANT**: Azure PostgreSQL requires the `uuid-ossp` extension to be enabled before running migrations.

**Option A: Using Azure Portal (Recommended)**
1. Go to Azure Portal → Your PostgreSQL server
2. Navigate to **"Server parameters"**
3. Search for `azure.extensions`
4. Add `uuid-ossp` to the allow-list
5. **Save and restart the server**
6. Wait for restart to complete

**Option B: Using Azure CLI**
```bash
az postgres flexible-server parameter set \
  --resource-group <your-resource-group> \
  --server-name <your-server-name> \
  --name azure.extensions \
  --value uuid-ossp
```

**Option C: Using psql (if you have admin access)**
Connect to your database and run:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

See `ENABLE_UUID_EXTENSION.sql` for the SQL command.

### 3. Run Database Migrations

After enabling the extension, run Lakekeeper migrations:

```bash
docker-compose run --rm lakekeeper migrate
```

### 4. Start Lakekeeper

```bash
docker-compose up -d lakekeeper
```

### 5. Check Logs

```bash
docker-compose logs -f lakekeeper
```

### 6. Access UI

Open `http://localhost:8181` in your browser.

## Configure ADLS Warehouse

After Lakekeeper is running:

1. **Access the UI**: Navigate to `http://localhost:8181`

2. **Add a Warehouse**:
   - Click "Add Warehouse" or navigate to warehouse configuration
   - Configure with the following:
     - **Warehouse Name**: `adls_warehouse` (or your preferred name)
     - **Storage Type**: `Azure` / `ADLS`
     - **Storage Path**: **MUST start with `abfss://`** (Azure Blob File System Secure)
       - Format: `abfss://container@storageaccount.dfs.core.windows.net/path`
       - Example: `abfss://documents@investflowadls.dfs.core.windows.net/lakekeeper`
     - **Credential Type**: `Client Credentials`
     - **Client ID**: Your Azure App Registration client ID
     - **Client Secret**: Your Azure App Registration client secret
     - **Tenant ID**: Your Azure AD tenant ID
     - **Storage Account Name**: `investflowadls`
     - **Container/Filesystem**: Name of your ADLS container (e.g., `documents`)

3. **Save the configuration**

## Verify Setup

1. **Check health endpoint**:
   ```bash
   curl http://localhost:8181/health
   ```

2. **Verify PostgreSQL connection**: Check logs for successful database connection

3. **Test ADLS connection**: Create a test warehouse and verify connectivity

## Environment Variables Reference

| Variable | Description | Required | Source |
|----------|-------------|----------|--------|
| `POSTGRES_HOST` | PostgreSQL server hostname | Yes | Your backend config |
| `POSTGRES_PORT` | PostgreSQL port (default: 5432) | Yes | Your backend config |
| `POSTGRES_DB` | Database name | Yes | Your backend config |
| `POSTGRES_USER` | PostgreSQL username | Yes | Your backend config |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes | Your backend config |
| `LAKEKEEPER__PG_ENCRYPTION_KEY` | Encryption key for sensitive data (min 32 chars) | Yes | Generate new |
| `LAKEKEEPER__ENABLE_AZURE_SYSTEM_CREDENTIALS` | Use Azure Managed Identity (true/false) | No | Optional |

**Note**: `LAKEKEEPER__PG_DATABASE_URL_READ` and `LAKEKEEPER__PG_DATABASE_URL_WRITE` are automatically constructed from the `POSTGRES_*` variables.

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL version is 15+
- Check firewall rules allow connections
- Verify all `POSTGRES_*` variables are set in `.env`
- Check logs: `docker-compose logs lakekeeper`

### Migration Issues

**Error: "extension uuid-ossp is not allow-listed"**
- This is required for Azure PostgreSQL
- Enable via Azure Portal: Server parameters → `azure.extensions` → Add `uuid-ossp` → Restart server
- Or use Azure CLI: `az postgres flexible-server parameter set --name azure.extensions --value uuid-ossp`
- See `ENABLE_UUID_EXTENSION.sql` for details

**Other migration errors:**
- Run migrations manually: `docker-compose run --rm lakekeeper migrate`
- Check database permissions - user needs CREATE TABLE and CREATE EXTENSION permissions

### ADLS Connection Issues
- Verify App Registration has correct roles assigned
- Check client secret hasn't expired
- Verify storage account name and container name are correct
- **Storage Path MUST start with `abfss://`**

## Next Steps

1. Configure warehouses in Lakekeeper UI
2. Create Iceberg tables via Lakekeeper
3. Integrate with your application (using DuckDB in FastAPI backend)

## Resources

- [Lakekeeper Documentation](https://docs.lakekeeper.io)
- [Lakekeeper GitHub](https://github.com/lakekeeper/lakekeeper)
- [Getting Started Guide](https://docs.lakekeeper.io/getting-started/)
