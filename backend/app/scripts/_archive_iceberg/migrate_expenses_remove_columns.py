#!/usr/bin/env python3
"""
Migrate expenses table: remove is_planned and created_by_user_id columns
1. Export current expenses to parquet
2. Remove columns: is_planned, created_by_user_id
3. Verify all expenses belong to "501 NE 67th Street" or "316 S 50th Ave"
4. Create new Iceberg table schema
5. Upload data to Iceberg
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import pyarrow as pa

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment
if not os.getenv('LAKEKEEPER__BASE_URI'):
    env_file = backend_dir / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from app.core.iceberg import get_catalog, read_table, load_table, table_exists, append_data
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "expenses"
BACKUP_TABLE_NAME = "expenses_backup"

# Property addresses to verify
ALLOWED_PROPERTY_ADDRESSES = [
    "501 NE 67th Street",
    "316 S 50th Ave"
]

def create_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for expenses table (without is_planned and created_by_user_id)"""
    return pa.schema([
        # STRING fields (in Iceberg order)
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("unit_id", pa.string(), nullable=True),  # UUID as string
        pa.field("description", pa.string(), nullable=False),
        pa.field("vendor", pa.string(), nullable=True),
        pa.field("expense_type", pa.string(), nullable=False),  # enum as string
        pa.field("expense_category", pa.string(), nullable=True),  # enum as string
        pa.field("document_storage_id", pa.string(), nullable=True),  # UUID as string
        pa.field("notes", pa.string(), nullable=True),
        
        # DECIMAL128 fields (in Iceberg order)
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        
        # DATE32 fields (in Iceberg order)
        pa.field("date", pa.date32(), nullable=False),
        
        # TIMESTAMP fields (in Iceberg order)
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])

def verify_property_addresses(df: pd.DataFrame) -> bool:
    """Verify all expenses belong to allowed property addresses"""
    from app.core.iceberg import read_table
    
    # Read properties table to get addresses
    properties_df = read_table(NAMESPACE, "properties")
    
    # Get property IDs for allowed addresses
    allowed_property_ids = set()
    for address in ALLOWED_PROPERTY_ADDRESSES:
        # Match by address_line1
        matching = properties_df[
            properties_df["address_line1"].str.contains(address, case=False, na=False)
        ]
        if len(matching) > 0:
            allowed_property_ids.update(matching["id"].tolist())
            print(f"✅ Found property: {address} -> {matching['id'].tolist()}")
        else:
            print(f"⚠️  Warning: No property found for address: {address}")
    
    if not allowed_property_ids:
        print("❌ ERROR: No allowed properties found!")
        return False
    
    # Check all expenses
    invalid_expenses = df[~df["property_id"].isin(allowed_property_ids)]
    
    if len(invalid_expenses) > 0:
        print(f"\n❌ ERROR: Found {len(invalid_expenses)} expenses that don't belong to allowed properties:")
        print(invalid_expenses[["id", "property_id", "description"]].to_string())
        return False
    
    print(f"✅ All {len(df)} expenses belong to allowed properties")
    return True

def main():
    print("=" * 80)
    print("Migrate Expenses Table - Remove is_planned and created_by_user_id")
    print("=" * 80)
    print()
    
    catalog = get_catalog()
    
    # Step 1: Export current expenses to parquet
    print("Step 1: Exporting current expenses to parquet...")
    if not table_exists(NAMESPACE, TABLE_NAME):
        print(f"❌ Table {TABLE_NAME} does not exist!")
        return
    
    df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Loaded {len(df)} expenses")
    
    # Save backup to /tmp (writable in Docker)
    backup_file = Path(f"/tmp/expenses_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
    df.to_parquet(backup_file, index=False)
    print(f"✅ Backup saved to: {backup_file}")
    print()
    
    # Step 2: Remove columns
    print("Step 2: Removing columns (is_planned, created_by_user_id)...")
    columns_to_remove = ["is_planned", "created_by_user_id"]
    existing_columns = [col for col in columns_to_remove if col in df.columns]
    
    if existing_columns:
        df_cleaned = df.drop(columns=existing_columns)
        print(f"✅ Removed columns: {existing_columns}")
    else:
        df_cleaned = df.copy()
        print("⚠️  Columns not found in data (may have already been removed)")
    
    print(f"✅ Cleaned data: {len(df_cleaned)} rows, {len(df_cleaned.columns)} columns")
    print()
    
    # Step 3: Verify property addresses
    print("Step 3: Verifying all expenses belong to allowed properties...")
    if not verify_property_addresses(df_cleaned):
        print("❌ Verification failed! Aborting migration.")
        return
    print()
    
    # Step 4: Save cleaned data to parquet
    print("Step 4: Saving cleaned data to parquet...")
    output_file = Path("/tmp/expenses_cleaned.parquet")
    df_cleaned.to_parquet(output_file, index=False)
    print(f"✅ Saved to: {output_file}")
    print()
    
    # Step 5: Create new table schema
    print("Step 5: Creating new table schema...")
    schema = create_expenses_schema()
    
    # Ensure namespace exists
    try:
        catalog.create_namespace(NAMESPACE)
    except Exception:
        pass  # Namespace may already exist
    
    # Create table if it doesn't exist, or recreate if it does
    table_path = (*NAMESPACE, TABLE_NAME)
    try:
        table = catalog.load_table(table_path)
        print(f"⚠️  Table {TABLE_NAME} already exists. Dropping and recreating...")
        # Drop the existing table
        catalog.drop_table(table_path)
        print(f"✅ Dropped existing table")
    except Exception:
        pass  # Table doesn't exist, which is fine
    
    # Create new table with clean schema
    catalog.create_table(
        identifier=table_path,
        schema=schema,
        properties={"format-version": "2"}
    )
    print(f"✅ Created new table: {TABLE_NAME} with clean schema")
    print()
    
    # Step 6: Prepare data for upload (ensure column order matches schema)
    print("Step 6: Preparing data for upload...")
    # Reorder columns to match schema
    schema_columns = [field.name for field in schema]
    df_upload = df_cleaned[[col for col in schema_columns if col in df_cleaned.columns]].copy()
    
    # Ensure data types match schema
    for field in schema:
        col_name = field.name
        if col_name not in df_upload.columns:
            continue
        
        field_type = field.type
        if pa.types.is_string(field_type):
            df_upload[col_name] = df_upload[col_name].astype(str)
        elif pa.types.is_decimal128(field_type):
            from decimal import Decimal
            df_upload[col_name] = df_upload[col_name].apply(lambda x: Decimal(str(x)) if pd.notna(x) else None)
        elif pa.types.is_date32(field_type):
            df_upload[col_name] = pd.to_datetime(df_upload[col_name]).dt.date
        elif pa.types.is_timestamp(field_type):
            df_upload[col_name] = pd.to_datetime(df_upload[col_name])
    
    print(f"✅ Prepared {len(df_upload)} rows for upload")
    print()
    
    # Step 7: Upload to Iceberg
    print("Step 7: Uploading data to Iceberg...")
    append_data(NAMESPACE, TABLE_NAME, df_upload)
    print(f"✅ Uploaded {len(df_upload)} expenses to Iceberg")
    print()
    
    # Step 8: Verify
    print("Step 8: Verifying upload...")
    verify_df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Verified: {len(verify_df)} expenses in table")
    print(f"✅ Columns: {list(verify_df.columns)}")
    print()
    
    print("=" * 80)
    print("✅ Migration completed successfully!")
    print("=" * 80)
    print(f"\nNext steps:")
    print("1. Update Pydantic schema in app/schemas/expense.py")
    print("2. Update expense service to remove is_planned and created_by_user_id")
    print("3. Update frontend to filter by single property_id")

if __name__ == "__main__":
    main()

