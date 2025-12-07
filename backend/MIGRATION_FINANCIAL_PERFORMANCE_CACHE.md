# Financial Performance Cache Migration

## Overview

The financial performance cache is now stored as **parquet files in Azure Blob Storage** (ADLS) for fast lookups, similar to the `users` and `shares` caches.

This provides:
- ⚡ **Fast O(1) lookups** from in-memory cache
- 📦 **Parquet storage** in ADLS at `cdc/financial_performance/financial_performance_current.parquet`
- 🔄 **Async updates** when expenses or rent are added (non-blocking)
- 🚀 **No slowdown** on expense/rent screens

## Migration Steps

### 1. Deploy the New Code

The code has been deployed and containers rebuilt with:
- `financial_performance_cache_service.py` - ADLS parquet cache service
- `migrate_populate_financial_performance_cache.py` - One-time migration script

### 2. Run the Migration Script (ONE TIME ONLY)

**In the deployed backend container**, run:

```bash
# SSH into the container or run via docker-compose
docker-compose exec backend python migrate_populate_financial_performance_cache.py

# OR if running with uv:
docker-compose exec backend uv run migrate_populate_financial_performance_cache.py
```

This will:
1. Read all properties from Iceberg
2. Calculate P&L (rent - expenses excluding rehab) for each property
3. Store results as parquet in ADLS: `documents/cdc/financial_performance/financial_performance_current.parquet`
4. Load cache into memory for fast lookups

### 3. Verify the Cache

After running the migration, you should see the parquet file in Azure Storage Explorer:

**Path:** `documents/cdc/financial_performance/financial_performance_current.parquet`

The file will contain columns:
- `property_id`, `unit_id`
- `ytd_rent`, `ytd_expenses`, `ytd_profit_loss`
- `ytd_piti`, `ytd_utilities`, `ytd_maintenance`, `ytd_capex`, etc.
- `cumulative_rent`, `cumulative_expenses`, `cumulative_profit_loss`
- `cumulative_piti`, `cumulative_utilities`, etc.
- `cash_on_cash`, `last_calculated_at`

## How It Works

### On Startup
1. Backend loads parquet file from ADLS into memory
2. Builds in-memory cache for O(1) lookups by property_id

### On API Request
1. Financial performance API checks cache first (FAST PATH)
2. If cache hit: return immediately
3. If cache miss: calculate from scratch (SLOW PATH)

### On Expense/Rent Changes
1. Expense or rent is added/updated/deleted
2. Triggers **async background recalculation** (non-blocking)
3. Updates in-memory cache
4. Persists entire cache back to ADLS parquet

## Performance Benefits

- **Before:** Every dashboard load calculated P&L from scratch (slow)
- **After:** Dashboard loads read from in-memory cache (instant)
- **Updates:** Happen in parallel background threads (no UI slowdown)

## Cache Location

```
Azure Blob Storage Container: documents (or CDC_CACHE_CONTAINER_NAME env var)
Path: cdc/financial_performance/financial_performance_current.parquet
Format: Parquet (columnar, compressed)
```

## Monitoring

Check cache status via backend logs:
```
[FP-CACHE] Cache HIT for property {id}     # Fast path used
[FP-CACHE] Cache MISS for property {id}    # Slow path, triggers recalculation
[FP-CACHE] Recalculating for property {id} # Background update started
[FP-CACHE] Updated property {id}           # Cache refreshed
```

## Troubleshooting

### Cache not loading
- Check AZURE_STORAGE_CONNECTION_STRING env var is set
- Verify parquet file exists in ADLS
- Check backend logs for errors

### Slow performance
- Run migration script to populate cache
- Check that async updates are working (look for background thread logs)

### Cache out of sync
- Delete parquet file and re-run migration script
- Or manually trigger recalculation by adding/removing a dummy expense

