# Schema Migration Guide

## Changes Made

This migration adds new fields to existing tables and creates new tables for the walkthrough feature.

### 1. Properties Table
**New Fields:**
- `cash_invested` (Decimal 12,2) - Manual entry for Cash-on-Cash calculation
- `down_payment` (Decimal 12,2) - Down payment amount (if missing)
- `purchase_date` (Timestamp) - Purchase date (if missing)
- `current_market_value` (Decimal 12,2) - Current market value (if missing)
- `property_status` (String) - Property status (if missing)
- `vacancy_rate` (Decimal 5,4) - Vacancy rate (if missing)

### 2. Leases Table
**New Fields:**
- `pet_deposit_total` (Decimal 10,2) - Total pet deposit amount
- `pet_description` (String) - Description of pets (e.g., "2 cats and 1 50lb dog")

### 3. New Tables
**walkthroughs:**
- Property walkthrough inspections (move-in, move-out, periodic, maintenance)
- Tracks inspector, tenant, signatures, overall condition
- Links to generated PDF

**walkthrough_areas:**
- Individual areas within a walkthrough (floor + area name)
- Stores photos (ADLS blob names) and issues as JSON
- Tracks condition per area

## How to Run Migration

### Step 1: Start Docker Containers
```bash
cd /Users/matt/code/property/backend
docker-compose up --build -d
```

### Step 2: Run Migration Script
```bash
cd /Users/matt/code/property/backend
uv run app/scripts/migrate_add_fields.py
```

This script will:
1. Add new columns to `properties` table (preserving existing data)
2. Add new columns to `leases` table (preserving existing data)
3. Create `walkthroughs` and `walkthrough_areas` tables

### Step 3: Verify Migration
Check Lakekeeper catalog to ensure tables have new schema:
```bash
curl -s http://localhost:8181/catalog/v1/investflow/namespaces/investflow/tables
```

## Schema Updates in Code

### Updated Files:
1. `backend/app/models/tables.py` - Added ORM models
2. `backend/app/schemas/property.py` - Added cash_invested field
3. `backend/app/schemas/lease.py` - Added pet_deposit_total and pet_description
4. `backend/app/schemas/walkthrough.py` - New schema file
5. `backend/app/scripts/create_data.py` - Updated schema functions
6. `backend/app/services/financial_performance_service.py` - Updated CoC calculation
7. `backend/app/services/financial_performance_cache_service.py` - Updated CoC calculation
8. `backend/app/api/financial_performance.py` - Updated API to use cash_invested
9. `backend/app/api/units.py` - Fixed unit rent save issue
10. `frontend/app/(dashboard)/properties/[id]/page.tsx` - Added cash_invested UI

## Important Notes

1. **Iceberg Schema Evolution**: Iceberg supports schema evolution, so new columns are added without data loss
2. **Null Values**: New columns start with NULL values for existing records
3. **Backward Compatible**: Old code will continue to work, new fields are optional
4. **ADLS**: All data remains in ADLS, only metadata changes in Lakekeeper/PostgreSQL

## Rollback (if needed)

If migration fails:
1. Restore from ADLS backup: `documents/backup/YYYYMMDD_HHMMSS/`
2. Use `restore_all_data.py` script to reload tables
3. Check logs: `docker-compose logs backend --tail=100`

## Testing After Migration

1. **Properties**: Edit a property and set `cash_invested`, verify CoC calculation
2. **Units**: Edit unit rent, ensure it saves correctly
3. **Leases**: Create a lease with pet details, verify fields are stored
4. **Walkthroughs**: Will be tested once API endpoints are implemented

## CoC Calculation Changes

**Old Formula:**
```python
cash_invested = current_market_value - purchase_price
```

**New Formula:**
```python
# Use manual cash_invested if available, else fallback to down_payment
investment_amount = cash_invested or down_payment
cash_on_cash = (annual_profit_loss / investment_amount) * 100
```

This allows you to manually enter the actual cash out of pocket, accounting for:
- Down payment
- Cash rehab expenses (rehab that wasn't financed)
- Closing costs
- Any other upfront cash

## Next Steps

After migration:
1. Test all fixed issues locally
2. Implement walkthrough API endpoints
3. Build walkthrough frontend forms
4. Create walkthrough PDF generator service
5. Deploy to Azure

