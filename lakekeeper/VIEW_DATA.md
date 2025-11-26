# Viewing Data in Azure Blob Storage and DBeaver

## 1. Viewing Data in Azure Blob Storage

### Location
Your Iceberg table data is stored in Azure Data Lake Storage Gen2 (ADLS Gen2) at:

**Storage Account**: `investflowadls`  
**Container**: `lakekeeper` (or your configured container)  
**Path**: `warehouse/{warehouse-id}/{table-id}/`

### Access via Azure Portal

1. **Go to Azure Portal** → Storage accounts → `investflowadls`
2. **Navigate to Containers** → Select `lakekeeper` container
3. **Browse to warehouse folder**:
   - Path: `warehouse/{warehouse-id}/{table-id}/`
   - Example: `warehouse/019ac0c2-87dd-76f2-8339-e83c29ebd796/019ac0c3-8be5-7552-a382-766a5d0e453a/`

### Table Structure in Blob Storage

Each Iceberg table has:
- **`data/`** - Parquet data files (e.g., `00000-0-*.parquet`)
- **`metadata/`** - Iceberg metadata files (e.g., `*.metadata.json`)
- **`metadata.json`** - Current metadata pointer

### Example Path Structure
```
lakekeeper/
└── warehouse/
    └── {warehouse-id}/
        └── {table-id}/
            ├── data/
            │   └── 00000-0-*.parquet
            └── metadata/
                └── *.metadata.json
```

### Access via Azure Storage Explorer

1. **Download Azure Storage Explorer**: https://azure.microsoft.com/features/storage-explorer/
2. **Connect to your storage account** using:
   - Storage account name: `investflowadls`
   - Account key (from Azure Portal → Access keys)
3. **Navigate to**: `Blob Containers` → `lakekeeper` → `warehouse`

### Access via Azure CLI

```bash
# List containers
az storage container list --account-name investflowadls --account-key <key>

# List files in warehouse
az storage blob list \
  --account-name investflowadls \
  --container-name lakekeeper \
  --prefix warehouse/ \
  --account-key <key>
```

## 2. Viewing Namespaces and Tables in DBeaver

### Connect to PostgreSQL

1. **Open DBeaver**
2. **Create New Connection** → PostgreSQL
3. **Connection Settings**:
   - **Host**: `if-postgres.postgres.database.azure.com` (or your `POSTGRES_HOST`)
   - **Port**: `5432`
   - **Database**: `investflow` (or your `POSTGRES_DB`)
   - **Username**: `pgadmin` (or your `POSTGRES_USER`)
   - **Password**: Your `POSTGRES_PASSWORD`
   - **SSL Mode**: `Require` (Azure PostgreSQL requires SSL)

### Query Namespaces

```sql
-- List all namespaces
SELECT 
    n.namespace_id,
    n.namespace_name,
    w.name as warehouse_name,
    n.created_at,
    n.updated_at
FROM namespace n
JOIN warehouse w ON n.warehouse_id = w.warehouse_id
ORDER BY w.name, n.namespace_name;
```

### Query Tables

```sql
-- List all tables with their namespaces
SELECT 
    t.tabular_id,
    t.name as table_name,
    t.typ as table_type,
    n.namespace_name,
    w.name as warehouse_name,
    t.location,
    t.metadata_location,
    t.created_at,
    t.updated_at
FROM tabular t
JOIN namespace n ON t.namespace_id = n.namespace_id
JOIN warehouse w ON n.warehouse_id = w.warehouse_id
WHERE t.typ = 'table'
ORDER BY w.name, n.namespace_name, t.name;
```

### Query Tables in Specific Namespace

```sql
-- List tables in 'investflow' namespace
SELECT 
    t.name as table_name,
    t.location,
    t.metadata_location,
    t.created_at
FROM tabular t
JOIN namespace n ON t.namespace_id = n.namespace_id
WHERE n.namespace_name = ARRAY['investflow']
  AND t.typ = 'table'
ORDER BY t.name;
```

### Query Warehouse Information

```sql
-- List all warehouses
SELECT 
    warehouse_id,
    name,
    is_active,
    protected,
    created_at,
    updated_at
FROM warehouse
ORDER BY name;
```

### Get Table Metadata

```sql
-- Get detailed table information
SELECT 
    t.tabular_id,
    t.name as table_name,
    n.namespace_name,
    w.name as warehouse_name,
    t.location as table_location,
    t.metadata_location,
    t.created_at,
    t.updated_at,
    -- Table metadata (JSONB)
    table.metadata
FROM tabular t
JOIN namespace n ON t.namespace_id = n.namespace_id
JOIN warehouse w ON n.warehouse_id = w.warehouse_id
LEFT JOIN "table" ON "table".table_id = t.tabular_id
WHERE n.namespace_name = ARRAY['investflow']
  AND t.typ = 'table'
ORDER BY t.name;
```

### Useful Views

Lakekeeper creates some helpful views:

```sql
-- View active tabulars (tables and views)
SELECT * FROM active_tabulars
WHERE namespace_name = ARRAY['investflow']
ORDER BY name;
```

## 3. Quick Reference Queries

### Count Tables per Namespace

```sql
SELECT 
    n.namespace_name,
    COUNT(t.tabular_id) as table_count
FROM namespace n
LEFT JOIN tabular t ON n.namespace_id = t.namespace_id AND t.typ = 'table'
GROUP BY n.namespace_name
ORDER BY n.namespace_name;
```

### Find Table by Name

```sql
-- Find a specific table
SELECT 
    t.name,
    n.namespace_name,
    w.name as warehouse,
    t.location
FROM tabular t
JOIN namespace n ON t.namespace_id = n.namespace_id
JOIN warehouse w ON n.warehouse_id = w.warehouse_id
WHERE t.name ILIKE '%users%'  -- Search pattern
  AND t.typ = 'table';
```

### Get All Namespaces for Your Warehouse

```sql
-- Replace 'lakekeeper' with your warehouse name
SELECT 
    n.namespace_name,
    n.namespace_id,
    COUNT(t.tabular_id) as table_count
FROM namespace n
JOIN warehouse w ON n.warehouse_id = w.warehouse_id
LEFT JOIN tabular t ON n.namespace_id = t.namespace_id AND t.typ = 'table'
WHERE w.name = 'lakekeeper'
GROUP BY n.namespace_name, n.namespace_id
ORDER BY n.namespace_name;
```

## 4. Understanding the Data Structure

### PostgreSQL Tables (Metadata)
- **`warehouse`** - Warehouse definitions
- **`namespace`** - Namespace definitions (like databases)
- **`tabular`** - Table and view metadata
- **`table`** - Additional table metadata (JSONB)

### Azure Blob Storage (Data Files)
- **Parquet files** - Actual table data
- **Metadata files** - Iceberg table metadata
- **Manifest files** - File lists and statistics

## 5. Tips

1. **Namespace names are arrays** - Use `ARRAY['namespace']` in SQL queries
2. **Table locations** - Point to the root directory of the table in ADLS
3. **Metadata locations** - Point to the current metadata.json file
4. **Use ILIKE for case-insensitive search** - PostgreSQL collation is case-insensitive
5. **Check `active_tabulars` view** - Pre-joined view for easier queries

