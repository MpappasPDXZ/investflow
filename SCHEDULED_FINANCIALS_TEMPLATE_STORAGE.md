# Scheduled Financials Template Storage in ADLS

## Overview
All scheduled financials templates are stored in **Azure Data Lake Storage (ADLS)** as Parquet files. This ensures persistence, scalability, and fast access for auto-applying templates to new properties.

## ADLS Storage Location

**Container**: `documents` (or `CDC_CACHE_CONTAINER_NAME` if configured)

**Paths**:
```
cdc/scheduled_financials_template/
├── metadata.parquet      # Template property characteristics (price, beds, baths, sqft)
├── expenses.parquet      # Scheduled expenses from the template property
└── revenue.parquet       # Scheduled revenue from the template property
```

## Template Structure

### Metadata (`metadata.parquet`)
Stores the reference property's characteristics for intelligent scaling:
- `template_property_id` (UUID)
- `purchase_price` (decimal)
- `bedrooms` (int)
- `bathrooms` (decimal)
- `square_feet` (decimal)
- `created_at` (timestamp)

### Expenses (`expenses.parquet`)
Contains all scheduled expenses from the template property:
- CapEx items with depreciation schedules
- Maintenance costs
- Property taxes, insurance (PTI)
- Principal & Interest (PI)

### Revenue (`revenue.parquet`)
Contains all scheduled revenue from the template property:
- Rent income
- Appreciation projections
- Principal paydown
- Value-added revenue

## How It Works

### 1. Save Template from Property
```bash
POST /api/v1/scheduled-financials/save-template/{property_id}
```
- Reads property's scheduled_expenses and scheduled_revenue from Iceberg
- Saves property characteristics (price, beds, baths, sqft) as metadata
- Writes three Parquet files to ADLS
- Cache is reloaded automatically

### 2. Auto-Load on Backend Startup
The template cache is initialized when the FastAPI backend starts:
```python
# In app/main.py
@app.on_event("startup")
async def startup_event():
    scheduled_financials_template.initialize()
```

This reads the Parquet files from ADLS and loads them into memory for fast access.

### 3. Apply Template to New Property
```bash
POST /api/v1/scheduled-financials/apply-template/{property_id}
```
- Calculates scaling ratios based on target property vs template property:
  - **Price ratio**: `target_price / template_price`
  - **Beds ratio**: `target_beds / template_beds`
  - **Baths ratio**: `target_baths / template_baths`
  - **Square feet ratio**: `target_sqft / template_sqft`
- Applies intelligent scaling to each expense/revenue item:
  - CapEx: scales with price × sqft
  - Maintenance: scales with price × sqft
  - PTI: scales with price × sqft
  - P&I: scales with price (loan amount)
  - Appreciation: uses target property value
  - Principal Paydown: scales with price
  - Value-added: scales with price
- Inserts scaled items into Iceberg tables

## Benefits

✅ **Persistent Storage**: Templates survive backend restarts
✅ **Fast Access**: Loaded into memory on startup
✅ **Scalable**: ADLS handles any template size
✅ **Version Control**: Parquet files include `_cdc_timestamp`
✅ **Intelligent Scaling**: Multi-factor scaling based on property characteristics
✅ **Zero Configuration**: Works automatically with existing ADLS setup

## Current Template

**Template Property**: `316 S 50th Ave` (ID: `00b1f6e9-174f-40a3-b2e9-af1518c6c69a`)
- **28 scheduled expenses**
- **3 scheduled revenue items**

Stored in ADLS at: `cdc/scheduled_financials_template/*.parquet`

## Verifying ADLS Storage

To verify the template files in ADLS:
```bash
# Check if template is loaded
docker-compose exec backend python -c "
from app.services.scheduled_financials_template_service import scheduled_financials_template
scheduled_financials_template.initialize()
print(f'Expenses: {len(scheduled_financials_template._expenses_template)}')
print(f'Revenue: {len(scheduled_financials_template._revenue_template)}')
print(f'Metadata: {scheduled_financials_template._template_metadata}')
"
```

## Future Enhancements

- Support multiple templates (different property types)
- Template versioning and rollback
- Template comparison and analytics
- Export/import templates between environments

