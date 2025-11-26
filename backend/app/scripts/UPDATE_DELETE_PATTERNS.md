# Update and Delete Patterns for Iceberg Tables

## Overview

This document describes the patterns for updating and deleting records in Iceberg tables using PyIceberg. These patterns are tested in `create_data.py`.

## ⚠️ Important: Iceberg Update Limitations

**Iceberg does NOT support direct row-level updates.** Instead, updates require:
1. Reading the entire table (or filtered subset)
2. Modifying rows in memory
3. Truncating the table
4. Reloading all data

This is **inefficient** but necessary for Iceberg. For production, consider:
- Using Iceberg's merge capabilities
- Partitioning strategies
- Batch updates instead of single-row updates

## Update Pattern

### Step-by-Step Process

```python
async def update_record(pyiceberg, table_name: str, record_id: str, updates: dict):
    """Update a record in an Iceberg table"""
    
    # 1. Read entire table (or filtered subset)
    df = pyiceberg.read_table(NAMESPACE, table_name)
    
    # 2. Find the record to update
    mask = df["id"] == record_id
    if not mask.any():
        return None  # Record not found
    
    # 3. Apply updates
    for key, value in updates.items():
        if key in df.columns:
            df.loc[mask, key] = value
    
    # 4. Update timestamp
    df.loc[mask, "updated_at"] = pd.Timestamp.now()
    
    # 5. Get table schema
    table = pyiceberg.load_table(NAMESPACE, table_name)
    schema = table.schema().as_arrow()
    
    # 6. Truncate and reload
    pyiceberg.truncate_table(NAMESPACE, table_name, schema)
    pyiceberg.append_data(NAMESPACE, table_name, df)
    
    # 7. Verify update
    df_after = pyiceberg.read_table(NAMESPACE, table_name)
    updated_row = df_after[df_after["id"] == record_id].iloc[0]
    return updated_row
```

### Example: Update Property

```python
# Update a property's display_name
df = pyiceberg.read_table(("investflow",), "properties")
mask = df["id"] == property_id
df.loc[mask, "display_name"] = "New Property Name"
df.loc[mask, "updated_at"] = pd.Timestamp.now()

# Truncate and reload
table = pyiceberg.load_table(("investflow",), "properties")
schema = table.schema().as_arrow()
pyiceberg.truncate_table(("investflow",), "properties", schema)
pyiceberg.append_data(("investflow",), "properties", df)
```

### Example: Update Expense

```python
# Update an expense amount and description
df = pyiceberg.read_table(("investflow",), "expenses")
mask = df["id"] == expense_id
df.loc[mask, "amount"] = 1500.00
df.loc[mask, "description"] = "Updated expense description"
df.loc[mask, "updated_at"] = pd.Timestamp.now()

# Truncate and reload
table = pyiceberg.load_table(("investflow",), "expenses")
schema = table.schema().as_arrow()
pyiceberg.truncate_table(("investflow",), "expenses", schema)
pyiceberg.append_data(("investflow",), "expenses", df)
```

## Soft Delete Pattern

### Overview

Soft deletes set `is_active=False` instead of removing the record. This:
- Preserves data for audit trails
- Maintains referential integrity
- Allows recovery if needed

### Step-by-Step Process

```python
async def soft_delete_record(pyiceberg, table_name: str, record_id: str):
    """Soft delete a record (set is_active=False)"""
    
    # 1. Read entire table
    df = pyiceberg.read_table(NAMESPACE, table_name)
    
    # 2. Find the record
    mask = df["id"] == record_id
    if not mask.any():
        return False  # Record not found
    
    # 3. Set is_active=False
    df.loc[mask, "is_active"] = False
    df.loc[mask, "updated_at"] = pd.Timestamp.now()
    
    # 4. Get table schema
    table = pyiceberg.load_table(NAMESPACE, table_name)
    schema = table.schema().as_arrow()
    
    # 5. Truncate and reload
    pyiceberg.truncate_table(NAMESPACE, table_name, schema)
    pyiceberg.append_data(NAMESPACE, table_name, df)
    
    # 6. Verify soft delete
    df_after = pyiceberg.read_table(NAMESPACE, table_name)
    deleted_row = df_after[df_after["id"] == record_id].iloc[0]
    return deleted_row["is_active"] == False
```

### Example: Soft Delete Property

```python
# Soft delete a property
df = pyiceberg.read_table(("investflow",), "properties")
mask = df["id"] == property_id
df.loc[mask, "is_active"] = False
df.loc[mask, "updated_at"] = pd.Timestamp.now()

# Truncate and reload
table = pyiceberg.load_table(("investflow",), "properties")
schema = table.schema().as_arrow()
pyiceberg.truncate_table(("investflow",), "properties", schema)
pyiceberg.append_data(("investflow",), "properties", df)
```

### Querying Active Records

Always filter by `is_active=True` when querying:

```python
# List only active properties
df = pyiceberg.read_table(("investflow",), "properties")
active_properties = df[df["is_active"] == True]
```

## Hard Delete Pattern (Not Recommended)

### ⚠️ Warning

Hard deletes (removing records entirely) are **not recommended** because:
- They break referential integrity
- They lose audit trail
- They're irreversible

### If You Must Hard Delete

```python
async def hard_delete_record(pyiceberg, table_name: str, record_id: str):
    """Hard delete a record (remove entirely)"""
    
    # 1. Read entire table
    df = pyiceberg.read_table(NAMESPACE, table_name)
    
    # 2. Remove the record
    df = df[df["id"] != record_id]
    
    # 3. Get table schema
    table = pyiceberg.load_table(NAMESPACE, table_name)
    schema = table.schema().as_arrow()
    
    # 4. Truncate and reload
    pyiceberg.truncate_table(NAMESPACE, table_name, schema)
    pyiceberg.append_data(NAMESPACE, table_name, df)
```

## Performance Considerations

### Current Approach (Inefficient)

- **Read**: Full table scan
- **Update**: In-memory modification
- **Write**: Full table rewrite
- **Time Complexity**: O(n) where n = total rows

### Optimization Strategies

1. **Partitioning**: Partition tables by `user_id` or date to reduce scan size
2. **Batch Updates**: Update multiple records in one operation
3. **Merge Operations**: Use Iceberg's merge capabilities (if available in PyIceberg)
4. **Caching**: Cache frequently accessed data

### Example: User-Scoped Update (More Efficient)

```python
# Only read and rewrite user's data, not entire table
df = pyiceberg.read_table(("investflow",), "properties")
user_df = df[df["user_id"] == str(user_id)].copy()  # Filter first

# Update in user's subset
mask = user_df["id"] == property_id
user_df.loc[mask, "display_name"] = "New Name"

# Get all other users' data
other_df = df[df["user_id"] != str(user_id)]

# Combine and reload
combined_df = pd.concat([user_df, other_df], ignore_index=True)

# Truncate and reload
table = pyiceberg.load_table(("investflow",), "properties")
schema = table.schema().as_arrow()
pyiceberg.truncate_table(("investflow",), "properties", schema)
pyiceberg.append_data(("investflow",), "properties", combined_df)
```

## Testing

The patterns are tested in `create_data.py`:

1. **`test_update_property()`**: Updates a property's display_name
2. **`test_update_expense()`**: Updates an expense amount and description
3. **`test_soft_delete_property()`**: Soft deletes a property
4. **`test_soft_delete_client()`**: Soft deletes a client

Run tests:
```bash
docker-compose exec backend uv run python app/scripts/create_data.py
```

## Service Layer Implementation

See `backend/app/services/property_service.py` for production-ready implementations:

- `update_property()`: Updates a property
- `delete_property()`: Soft deletes a property (calls update with `is_active=False`)

## Key Takeaways

1. ✅ **Always use soft deletes** (`is_active=False`)
2. ✅ **Filter by `is_active=True`** when querying
3. ✅ **Update `updated_at` timestamp** on modifications
4. ⚠️ **Updates are expensive** - batch when possible
5. ⚠️ **Read entire table** before updating (or filtered subset)
6. ⚠️ **Truncate and reload** after modifications

## References

- PyIceberg Service: `backend/app/services/pyiceberg_service.py`
- Property Service: `backend/app/services/property_service.py`
- Test Script: `backend/app/scripts/create_data.py`

