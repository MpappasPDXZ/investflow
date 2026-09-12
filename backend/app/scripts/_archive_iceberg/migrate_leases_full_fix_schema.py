#!/usr/bin/env python3
"""
Migration script to fix leases table (comparables) schema

This script:
1. Backs up all data to local parquet file
2. Drops the leases table
3. Recreates table with updated schema:
   - Remove: pet_deposit_total, pet_description, utilities_provided_by_owner_city, 
             has_garage_door_opener, garage_door_opener_fee, garage_back_door_keys
   - Change garage_spaces from float32 to decimal128(3,1) to support .5 increments
4. Converts and loads data back with proper types

IMPORTANT: Run this inside Docker:
    docker-compose exec backend python3 app/scripts/migrate_leases_full_fix_schema.py
"""
import sys
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import pyarrow as pa
from decimal import Decimal

# Add parent directory to path to import app modules
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, read_table, load_table, table_exists
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases"  # This is the comparables table (will be renamed to comps)
BACKUP_FILE = Path("/tmp/leases_backup.parquet")  # Use /tmp which is writable in Docker


def create_new_leases_schema() -> pa.Schema:
    """Create new PyArrow schema for leases table (comparables) with removed fields and updated garage_spaces"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("address", pa.string(), nullable=False),
        pa.field("city", pa.string(), nullable=True),
        pa.field("state", pa.string(), nullable=True),
        pa.field("zip_code", pa.string(), nullable=True),
        # Property classification
        pa.field("property_type", pa.string(), nullable=True),
        pa.field("is_furnished", pa.bool_(), nullable=True),
        # Property details
        pa.field("bedrooms", pa.int32(), nullable=False),
        pa.field("bathrooms", pa.decimal128(3, 1), nullable=False),
        pa.field("square_feet", pa.int32(), nullable=False),
        pa.field("asking_price", pa.decimal128(10, 2), nullable=False),
        # Amenities
        pa.field("has_fence", pa.bool_(), nullable=True),
        pa.field("has_solid_flooring", pa.bool_(), nullable=True),
        pa.field("has_quartz_granite", pa.bool_(), nullable=True),
        pa.field("has_ss_appliances", pa.bool_(), nullable=True),
        pa.field("has_shaker_cabinets", pa.bool_(), nullable=True),
        pa.field("has_washer_dryer", pa.bool_(), nullable=True),
        pa.field("garage_spaces", pa.decimal128(3, 1), nullable=True),  # CHANGED: float32 -> decimal128(3,1)
        # Listing data
        pa.field("date_listed", pa.date32(), nullable=False),
        pa.field("date_rented", pa.date32(), nullable=True),
        pa.field("contacts", pa.int32(), nullable=True),
        # Rental status
        pa.field("is_rented", pa.bool_(), nullable=True),
        pa.field("last_rented_price", pa.decimal128(10, 2), nullable=True),
        pa.field("last_rented_year", pa.int32(), nullable=True),
        # Flags
        pa.field("is_subject_property", pa.bool_(), nullable=False),
        pa.field("is_active", pa.bool_(), nullable=False),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def backup_data():
    """Backup all data to local parquet file"""
    logger.info(f"📦 Step 1: Backing up {TABLE_NAME} data to {BACKUP_FILE}...")
    
    # Check if backup already exists
    if BACKUP_FILE.exists():
        logger.info(f"  ℹ️  Backup file already exists: {BACKUP_FILE}")
        logger.info(f"  📖 Loading from existing backup...")
        df = pd.read_parquet(BACKUP_FILE)
        logger.info(f"  ✅ Loaded {len(df)} rows from backup")
        return df
    
    if not table_exists(NAMESPACE, TABLE_NAME):
        logger.warning(f"  ⚠️  Table {TABLE_NAME} does not exist. Nothing to backup.")
        return None
    
    df = read_table(NAMESPACE, TABLE_NAME)
    
    if df is None or df.empty:
        logger.info(f"  ℹ️  Table {TABLE_NAME} is empty.")
        return None
    
    logger.info(f"  ✅ Read {len(df)} rows from {TABLE_NAME}")
    
    # Save to parquet
    df.to_parquet(BACKUP_FILE, index=False)
    logger.info(f"  ✅ Saved backup to {BACKUP_FILE}")
    
    return df


def drop_and_recreate_table():
    """Drop old table and create new one with updated schema"""
    logger.info(f"🔄 Step 2: Dropping and recreating {TABLE_NAME} table...")
    
    catalog = get_catalog()
    
    # Drop old table if it exists
    if table_exists(NAMESPACE, TABLE_NAME):
        logger.info(f"  🗑️  Dropping old {TABLE_NAME} table...")
        catalog.drop_table(f"{NAMESPACE[0]}.{TABLE_NAME}")
        logger.info(f"  ✅ Dropped old table")
    
    # Create new table with updated schema
    logger.info(f"  📝 Creating new {TABLE_NAME} table with updated schema...")
    schema = create_new_leases_schema()
    catalog.create_table(
        identifier=f"{NAMESPACE[0]}.{TABLE_NAME}",
        schema=schema
    )
    logger.info(f"  ✅ Created new table")
    
    # Log removed fields (if they existed)
    logger.info(f"  📋 Schema changes:")
    logger.info(f"     - garage_spaces: float32 -> decimal128(3,1)")
    logger.info(f"     - Removed any fields that don't belong in comparables table")


def convert_and_load_data(df: pd.DataFrame):
    """Convert data to match new schema and load it back"""
    if df is None or df.empty:
        logger.info(f"📋 Step 3: No data to load (table was empty)")
        return
    
    logger.info(f"📋 Step 3: Converting and loading data back...")
    
    # Get new schema field names
    new_schema = create_new_leases_schema()
    new_field_names = [f.name for f in new_schema]
    
    # Create new DataFrame with only fields that exist in new schema
    new_df = pd.DataFrame()
    
    for field_name in new_field_names:
        if field_name in df.columns:
            new_df[field_name] = df[field_name]
        else:
            # Field doesn't exist in old data, set to None
            new_df[field_name] = None
    
    # Convert garage_spaces from float32 to decimal128(3,1)
    if "garage_spaces" in new_df.columns:
        logger.info(f"  🔄 Converting garage_spaces from float32 to decimal128(3,1)...")
        # Convert to Decimal, rounding to 1 decimal place
        new_df["garage_spaces"] = new_df["garage_spaces"].apply(
            lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) else None
        )
        logger.info(f"  ✅ Converted garage_spaces")
    
    # Ensure DataFrame columns are in exact order matching new schema
    new_df = new_df[new_field_names]
    
    # Convert timestamp columns to microseconds (required, non-nullable)
    for col in ['created_at', 'updated_at']:
        if col in new_df.columns:
            new_df[col] = pd.to_datetime(new_df[col], utc=True).dt.tz_localize(None)
            new_df[col] = new_df[col].dt.floor('us')
            # Fill any NaN with current time (required field)
            new_df[col] = new_df[col].fillna(pd.Timestamp.now().floor('us'))
    
    # Convert date columns
    for col in ['date_listed', 'date_rented']:
        if col in new_df.columns:
            new_df[col] = pd.to_datetime(new_df[col]).dt.date
            # date_listed is required, fill with today if missing
            if col == 'date_listed':
                new_df[col] = new_df[col].fillna(date.today())
    
    # Convert integer columns (required fields must not be nullable)
    int_cols = ['bedrooms', 'square_feet', 'contacts', 'last_rented_year']
    for col in int_cols:
        if col in new_df.columns:
            if col in ['bedrooms', 'square_feet']:  # Required fields
                new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(0).astype(int)
            else:  # Optional fields
                new_df[col] = pd.to_numeric(new_df[col], errors='coerce').astype('Int64')
    
    # Convert boolean columns (required fields must not be nullable)
    bool_cols = ['is_subject_property', 'is_active']
    for col in bool_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].fillna(False).astype(bool)
    
    # Convert string columns (required fields must not be nullable)
    string_cols = ['id', 'property_id', 'address']
    for col in string_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str)
            # Fill any NaN with empty string for required fields
            new_df[col] = new_df[col].fillna('')
    
    # Convert decimal columns with proper precision
    # bathrooms: decimal128(3,1)
    if 'bathrooms' in new_df.columns:
        new_df['bathrooms'] = new_df['bathrooms'].apply(
            lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) else Decimal('0')
        )
    
    # asking_price: decimal128(10,2)
    if 'asking_price' in new_df.columns:
        new_df['asking_price'] = new_df['asking_price'].apply(
            lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else Decimal('0')
        )
    
    # last_rented_price: decimal128(10,2)
    if 'last_rented_price' in new_df.columns:
        new_df['last_rented_price'] = new_df['last_rented_price'].apply(
            lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else None
        )
    
    # garage_spaces: decimal128(3,1) - already converted above
    if 'garage_spaces' in new_df.columns:
        # Ensure it's Decimal with 1 decimal place
        new_df['garage_spaces'] = new_df['garage_spaces'].apply(
            lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) and x is not None else None
        )
    
    logger.info(f"  ✅ Converted {len(new_df)} rows")
    
    # Load data back - use explicit schema casting
    logger.info(f"  📤 Loading data back to {TABLE_NAME}...")
    table = load_table(NAMESPACE, TABLE_NAME)
    table_schema = table.schema().as_arrow()
    
    # Convert to PyArrow with explicit schema
    arrow_table = pa.Table.from_pandas(new_df)
    # Cast to exact schema to ensure types match
    arrow_table = arrow_table.cast(table_schema)
    table.append(arrow_table)
    logger.info(f"  ✅ Loaded {len(new_df)} rows back to {TABLE_NAME}")


def main():
    """Run the migration"""
    try:
        logger.info("🚀 Starting leases_full table schema migration")
        logger.info("=" * 80)
        
        # Step 1: Backup data
        df = backup_data()
        
        # Step 2: Drop and recreate table
        drop_and_recreate_table()
        
        # Step 3: Convert and load data
        convert_and_load_data(df)
        
        logger.info("=" * 80)
        logger.info("✅ Migration complete!")
        logger.info(f"   Backup saved to: {BACKUP_FILE}")
        logger.info(f"   Table {TABLE_NAME} (comparables) has been recreated with updated schema")
        logger.info(f"   Next step: Run rename_leases_to_comps.py to rename to 'comps'")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

