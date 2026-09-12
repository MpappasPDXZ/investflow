#!/usr/bin/env python3
"""
Migrate rents table: remove user_id and user_name columns
1. Write off data to parquet
2. Convert data to new dtypes (remove user_id, user_name)
3. Drop table
4. Recreate table with new schema (ordered by dtype)
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
TABLE_NAME = "rents"

def create_rents_schema() -> pa.Schema:
    """Create PyArrow schema for rents table WITHOUT user_id and user_name, ordered by dtype"""
    return pa.schema([
        # STRING fields (in Iceberg order)
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_name", pa.string(), nullable=True),  # Text - denormalized for speed
        pa.field("unit_id", pa.string(), nullable=True),  # UUID as string - nullable
        pa.field("unit_name", pa.string(), nullable=True),  # Text - denormalized for speed (unit_number)
        pa.field("tenant_id", pa.string(), nullable=True),  # UUID as string - nullable (was client_id)
        pa.field("tenant_name", pa.string(), nullable=True),  # Text - denormalized for speed
        pa.field("revenue_description", pa.string(), nullable=True),  # Monthly Rent, Partial Month Rent, One Time Pet Fee, One Time Application Fee, Deposit, Other
        pa.field("payment_method", pa.string(), nullable=True),  # enum as string
        pa.field("transaction_reference", pa.string(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("document_storage_id", pa.string(), nullable=True),  # UUID as string - reference to document_storage table
        pa.field("created_by_user_id", pa.string(), nullable=True),  # UUID as string
        
        # DECIMAL128 fields (in Iceberg order)
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("late_fee", pa.decimal128(10, 2), nullable=True),
        
        # INT32 fields (in Iceberg order)
        pa.field("rent_period_month", pa.int32(), nullable=True),  # 1-12 - month the rent is for (null for one-time fees)
        pa.field("rent_period_year", pa.int32(), nullable=True),  # year the rent is for (null for one-time fees)
        
        # DATE32 fields (in Iceberg order)
        pa.field("rent_period_start", pa.date32(), nullable=False),  # start date (defaults to month start, or single date for one-time fee)
        pa.field("rent_period_end", pa.date32(), nullable=False),  # end date (defaults to month end, or same as start for one-time fee)
        pa.field("payment_date", pa.date32(), nullable=False),
        
        # BOOLEAN fields (in Iceberg order)
        pa.field("is_non_irs_revenue", pa.bool_(), nullable=True),  # true for deposits and other non-IRS revenue (doesn't count toward revenue vs cost)
        pa.field("is_one_time_fee", pa.bool_(), nullable=True),  # true for one-time fees (pet fee, application fee, etc.)
        pa.field("is_late", pa.bool_(), nullable=True),
        
        # TIMESTAMP fields (in Iceberg order)
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])

def main():
    print("=" * 80)
    print("Migrate Rents Table - Remove user_id and user_name Columns")
    print("=" * 80)
    print()
    
    catalog = get_catalog()
    
    # Step 1: Write off data to parquet
    print("Step 1: Writing off data to parquet...")
    if not table_exists(NAMESPACE, TABLE_NAME):
        print(f"❌ Table {TABLE_NAME} does not exist!")
        return
    
    df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Loaded {len(df)} rent payments")
    
    # Save backup to /tmp (writable in Docker)
    backup_file = Path(f"/tmp/rents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
    df.to_parquet(backup_file, index=False)
    print(f"✅ Backup saved to: {backup_file}")
    print()
    
    # Step 2: Convert data to new dtypes (remove user_id, user_name)
    print("Step 2: Converting data to new dtypes...")
    # Drop user_id and user_name columns if they exist
    columns_to_drop = []
    if 'user_id' in df.columns:
        columns_to_drop.append('user_id')
        print(f"  📝 Removing user_id column")
    if 'user_name' in df.columns:
        columns_to_drop.append('user_name')
        print(f"  📝 Removing user_name column")
    
    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)
        print(f"✅ Removed columns: {', '.join(columns_to_drop)}")
    else:
        print("✅ No user_id or user_name columns found (already removed)")
    
    # Ensure all required columns exist with proper types
    schema = create_rents_schema()
    expected_columns = {field.name for field in schema}
    existing_columns = set(df.columns)
    
    # Add missing columns with default values
    for field in schema:
        if field.name not in df.columns:
            if field.nullable:
                df[field.name] = None
            else:
                if pa.types.is_string(field.type):
                    df[field.name] = ""
                elif pa.types.is_decimal128(field.type):
                    df[field.name] = 0.0
                elif pa.types.is_int32(field.type):
                    df[field.name] = 0
                elif pa.types.is_date32(field.type):
                    df[field.name] = pd.Timestamp('1970-01-01').date()
                elif pa.types.is_bool_(field.type):
                    df[field.name] = False
                elif pa.types.is_timestamp(field.type):
                    df[field.name] = None
            print(f"  ➕ Added missing column: {field.name}")
    
    # Reorder columns to match schema
    df = df[[field.name for field in schema if field.name in df.columns]]
    print(f"✅ Data prepared with {len(df)} rows and {len(df.columns)} columns")
    print()
    
    # Step 3: Drop table
    print("Step 3: Dropping existing table...")
    catalog.drop_table((*NAMESPACE, TABLE_NAME))
    print("✅ Table dropped")
    print()
    
    # Step 4: Recreate table with new schema
    print("Step 4: Recreating table with new schema...")
    catalog.create_table(identifier=(*NAMESPACE, TABLE_NAME), schema=schema)
    print("✅ Table recreated with new schema (user_id and user_name removed)")
    print()
    
    # Step 5: Prepare data for upload
    print("Step 5: Preparing data for upload...")
    print(f"✅ Prepared {len(df)} rows for upload")
    print()
    
    # Step 6: Upload data to Iceberg
    print("Step 6: Uploading data to Iceberg...")
    append_data(NAMESPACE, TABLE_NAME, df)
    print("✅ Data uploaded successfully")
    print()
    
    # Step 7: Verify upload
    print("Step 7: Verifying upload...")
    verify_df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Verified: {len(verify_df)} rent payments in table")
    print(f"✅ Columns: {', '.join(verify_df.columns)}")
    
    # Verify user_id and user_name are gone
    if 'user_id' in verify_df.columns:
        print("❌ WARNING: user_id column still exists!")
    else:
        print("✅ Confirmed: user_id column removed")
    
    if 'user_name' in verify_df.columns:
        print("❌ WARNING: user_name column still exists!")
    else:
        print("✅ Confirmed: user_name column removed")
    
    print()
    print("=" * 80)
    print("✅ Migration completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()

