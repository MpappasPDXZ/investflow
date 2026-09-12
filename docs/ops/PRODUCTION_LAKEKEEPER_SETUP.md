# Production Lakekeeper Setup Guide

## The Problem

**Local Lakekeeper**: ✅ Works - has all tables registered in PostgreSQL  
**Production Lakekeeper**: ❌ Broken - catalog is empty (404 errors)

**Why?** The Iceberg data is in Azure ADLS (shared), but the **catalog metadata** (which tables exist, where they are) is stored in **PostgreSQL**, which is **different** between local and production.

## The Solution

You need to **register all your tables** in production Lakekeeper, just like we did locally.

## Step 1: Verify Production Lakekeeper is Bootstrapped

```bash
# Check if Lakekeeper is bootstrapped
curl -H "Authorization: Bearer <your-token>" \
  https://investflow-lakekeeper.yellowsky-ca466dfe.eastus.azurecontainerapps.io/catalog/v1/bootstrap

# If it returns "Catalog is not open for bootstrap", it's already bootstrapped ✅
# If it returns something else, you need to bootstrap it first
```

## Step 2: Create a Script to Register Tables in Production

Create a script that:
1. Connects to production Lakekeeper (with OAuth2)
2. Scans Azure ADLS for all Iceberg tables
3. Registers them in production Lakekeeper

**The script needs:**
- Production Lakekeeper URL
- OAuth2 credentials (same as backend)
- Azure ADLS credentials
- Warehouse name

## Step 3: Run Table Discovery Against Production

You can adapt the local `discover_all_tables.py` script to work against production Lakekeeper.

**Key differences:**
- Use production Lakekeeper URL instead of `http://localhost:8181`
- Use OAuth2 authentication instead of no auth
- Point to the same Azure ADLS (which is already shared)

## Alternative: Copy Catalog from Local PostgreSQL

If you want to copy the catalog metadata directly:

1. **Dump local Lakekeeper PostgreSQL:**
```bash
docker compose exec postgres pg_dump -U pgadmin if-postgres > local_lakekeeper_catalog.sql
```

2. **Restore to production PostgreSQL:**
```bash
# Connect to production PostgreSQL (if-postgres.postgres.database.azure.com)
psql -h if-postgres.postgres.database.azure.com -U pgadmin -d if-postgres < local_lakekeeper_catalog.sql
```

**⚠️ Warning**: This will overwrite production catalog. Make sure production Lakekeeper is stopped first.

## Recommended Approach: Re-discover Tables

**Better approach**: Re-run table discovery against production because:
- ✅ Safer (doesn't overwrite anything)
- ✅ Ensures tables point to correct ADLS paths
- ✅ Works even if production PostgreSQL is different

## Quick Fix Script

I can create a script that:
1. Uses your production OAuth2 credentials
2. Connects to production Lakekeeper
3. Scans ADLS and registers all tables

Would you like me to create this script?

---

## Current Status

✅ **OAuth2 Authentication**: Working (token generation succeeds)  
✅ **Lakekeeper Health**: Running (`/health` returns 200)  
❌ **Catalog Endpoints**: 404 (catalog not initialized or empty)  
❌ **Table Access**: 404 (tables not registered)

**Next Step**: Register all tables in production Lakekeeper catalog.

