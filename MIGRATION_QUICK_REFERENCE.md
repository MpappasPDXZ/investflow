# Schema Migration Quick Reference

## When to Run Migrations

Run migrations when you:
- ✅ Add new columns to existing tables
- ✅ Create new tables
- ✅ Change column types (with care)
- ✅ Add indexes or constraints

## Local Development

```bash
# 1. Start containers
cd backend
docker-compose up --build -d

# 2. Run migration inside container
docker-compose exec backend uv run app/scripts/migrate_add_fields.py

# 3. Verify
curl -s http://localhost:8181/catalog/v1/investflow/namespaces/investflow/tables | jq
docker-compose logs backend --tail=50

# 4. Test in UI
open http://localhost:3000
```

## Production Deployment

```bash
# 1. Test locally FIRST (see above)

# 2. Build and push images
cd frontend
docker build --platform linux/amd64 -t investflowregistry.azurecr.io/investflow-frontend:latest .
az acr login --name investflowregistry
docker push investflowregistry.azurecr.io/investflow-frontend:latest

cd ../backend
docker build --platform linux/amd64 -t investflowregistry.azurecr.io/investflow-backend:latest .
docker push investflowregistry.azurecr.io/investflow-backend:latest

# 3. Update container apps
az containerapp update --name investflow-backend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-backend:latest
az containerapp update --name investflow-frontend --resource-group investflow-rg --image investflowregistry.azurecr.io/investflow-frontend:latest

# 4. Run migration in production
az containerapp exec \
  --name investflow-backend \
  --resource-group investflow-rg \
  --command "uv run app/scripts/migrate_add_fields.py"

# 5. Verify
az containerapp logs show --name investflow-backend --resource-group investflow-rg --tail 100
```

## Why Container Required?

Migration scripts need:
- 🔐 **OAuth2 credentials** (Lakekeeper authentication)
- 🔐 **ADLS credentials** (Azure storage access)
- 🌐 **Network access** (Lakekeeper, PostgreSQL)
- 📦 **Python dependencies** (PyIceberg, PyArrow, etc.)

All of these are pre-configured in the container environment.

## Common Commands

### Check Lakekeeper Catalog
```bash
# Local
curl -s http://localhost:8181/catalog/v1/investflow/namespaces/investflow/tables | jq

# List all tables
curl -s http://localhost:8181/catalog/v1/investflow/namespaces/investflow/tables | jq '.tables[].name'
```

### View Container Logs
```bash
# Local
docker-compose logs backend --tail=100 --follow

# Production
az containerapp logs show --name investflow-backend --resource-group investflow-rg --tail 100
```

### Backup Before Migration
```bash
# Local
docker-compose exec backend uv run backup_iceberg_tables.py

# Production
az containerapp exec \
  --name investflow-backend \
  --resource-group investflow-rg \
  --command "uv run backup_iceberg_tables.py"
```

## Migration Safety

✅ **Safe:**
- Adding new columns (NULL values)
- Creating new tables
- Running migration multiple times (idempotent)

⚠️ **Caution:**
- Dropping columns (data loss)
- Changing column types (potential data loss)
- Renaming columns (breaks existing code)

🛑 **Always:**
- Test locally first
- Backup before major changes
- Have rollback plan ready

## Rollback

If migration fails:

1. Check ADLS backup: `documents/backup/YYYYMMDD_HHMMSS/`
2. Use restore script:
   ```bash
   docker-compose exec backend uv run app/scripts/restore_all_data.py
   ```
3. Or restore specific table:
   ```bash
   # Download from ADLS, then append to Iceberg
   ```

## Current Migration (Dec 2025)

Adds:
- `properties.cash_invested` - Manual CoC entry
- `properties.down_payment` - Down payment (if missing)
- `properties.purchase_date` - Purchase date (if missing)
- `properties.current_market_value` - Current value (if missing)
- `properties.property_status` - Status (if missing)
- `properties.vacancy_rate` - Vacancy rate (if missing)
- `leases.pet_deposit_total` - Total pet deposit
- `leases.pet_description` - Pet description text
- `walkthroughs` table - New walkthrough inspections
- `walkthrough_areas` table - New areas with photos/issues

