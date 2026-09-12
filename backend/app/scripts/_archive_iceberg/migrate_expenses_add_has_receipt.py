#!/usr/bin/env python3
"""
Migrate expenses table: add has_receipt column
1. Write off data to parquet
2. Convert data to new dtypes (add has_receipt boolean)
3. Drop table
4. Recreate table with new schema
5. Upload data back
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

def create_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for expenses table with has_receipt column"""
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
        
        # BOOLEAN fields (in Iceberg order)
        pa.field("has_receipt", pa.bool_(), nullable=True),
        
        # TIMESTAMP fields (in Iceberg order)
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])

def main():
    print("=" * 80)
    print("Migrate Expenses Table - Add has_receipt Column")
    print("=" * 80)
    print()
    
    catalog = get_catalog()
    
    # Step 1: Write off data to parquet
    print("Step 1: Writing off data to parquet...")
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
    
    # Step 2: Convert data to new dtypes (add has_receipt)
    print("Step 2: Converting data to new dtypes...")
    # Set has_receipt to True if document_storage_id is not None/empty, False otherwise
    df['has_receipt'] = df['document_storage_id'].notna() & (df['document_storage_id'] != '') & (df['document_storage_id'] != 'None')
    df['has_receipt'] = df['has_receipt'].astype('boolean')
    
    # Count statistics
    has_receipt_count = df['has_receipt'].sum()
    no_receipt_count = len(df) - has_receipt_count
    print(f"✅ Added has_receipt column")
    print(f"   - Expenses with receipt: {has_receipt_count}")
    print(f"   - Expenses without receipt: {no_receipt_count}")
    print()
    
    # Step 3: Drop table
    print("Step 3: Dropping existing table...")
    table_path = (*NAMESPACE, TABLE_NAME)
    try:
        catalog.drop_table(table_path)
        print(f"✅ Dropped table: {TABLE_NAME}")
    except Exception as e:
        print(f"⚠️  Error dropping table (may not exist): {e}")
    print()
    
    # Step 4: Recreate table with new schema
    print("Step 4: Recreating table with new schema...")
    schema = create_expenses_schema()
    
    # Ensure namespace exists
    try:
        catalog.create_namespace(NAMESPACE)
    except Exception:
        pass  # Namespace may already exist
    
    # Create new table with schema including has_receipt
    catalog.create_table(
        identifier=table_path,
        schema=schema,
        properties={"format-version": "2"}
    )
    print(f"✅ Created new table: {TABLE_NAME} with has_receipt column")
    print()
    
    # Step 5: Prepare data for upload (ensure column order matches schema)
    print("Step 5: Preparing data for upload...")
    # Reorder columns to match schema
    schema_columns = [field.name for field in schema]
    df_upload = df[[col for col in schema_columns if col in df.columns]].copy()
    
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
        elif pa.types.is_boolean(field_type):
            df_upload[col_name] = df_upload[col_name].astype('boolean')
    
    print(f"✅ Prepared {len(df_upload)} rows for upload")
    print()
    
    # Step 6: Upload data back
    print("Step 6: Uploading data to Iceberg...")
    append_data(NAMESPACE, TABLE_NAME, df_upload)
    print(f"✅ Uploaded {len(df_upload)} expenses to Iceberg")
    print()
    
    # Step 7: Verify
    print("Step 7: Verifying upload...")
    verify_df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Verified: {len(verify_df)} expenses in table")
    print(f"✅ Columns: {list(verify_df.columns)}")
    
    # Verify has_receipt values
    if 'has_receipt' in verify_df.columns:
        verify_has_receipt_count = verify_df['has_receipt'].sum()
        verify_no_receipt_count = len(verify_df) - verify_has_receipt_count
        print(f"✅ has_receipt values:")
        print(f"   - Expenses with receipt: {verify_has_receipt_count}")
        print(f"   - Expenses without receipt: {verify_no_receipt_count}")
    print()
    
    print("=" * 80)
    print("✅ Migration completed successfully!")
    print("=" * 80)
    print(f"\nNext steps:")
    print("1. Update Pydantic schema in app/schemas/expense.py to include has_receipt")
    print("2. Update expense service to set has_receipt when creating/updating expenses")
    print("3. Update frontend to display has_receipt status and respect Pydantic model")

if __name__ == "__main__":
    main()

