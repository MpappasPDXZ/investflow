#!/usr/bin/env python3
"""
Migration script to rename the 'leases' table to 'comps'

This script:
1. Creates a new 'comps' table with the same schema as 'leases'
2. Copies all data from 'leases' to 'comps'
3. Drops the 'leases' table

IMPORTANT: Run this inside Docker:
    docker-compose exec backend python3 app/scripts/rename_leases_to_comps.py
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, read_table, load_table, table_exists
from app.core.logging import setup_logging, get_logger
from app.api.comparables import get_comparable_schema

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
OLD_TABLE_NAME = "leases"
NEW_TABLE_NAME = "comps"


def main():
    """Rename leases table to comps"""
    try:
        catalog = get_catalog()
        
        # Check if old table exists
        if not table_exists(NAMESPACE, OLD_TABLE_NAME):
            logger.info(f"❌ Table {OLD_TABLE_NAME} does not exist. Nothing to migrate.")
            return
        
        # Check if new table already exists - drop it if it does
        if table_exists(NAMESPACE, NEW_TABLE_NAME):
            logger.warning(f"⚠️  Table {NEW_TABLE_NAME} already exists. Dropping it first...")
            catalog.drop_table(f"{NAMESPACE[0]}.{NEW_TABLE_NAME}")
            logger.info(f"  ✅ Dropped existing {NEW_TABLE_NAME} table")
        
        logger.info(f"🔄 Starting migration: {OLD_TABLE_NAME} -> {NEW_TABLE_NAME}")
        
        # Step 1: Read all data from old table
        logger.info(f"📖 Step 1: Reading data from {OLD_TABLE_NAME}...")
        old_table = load_table(NAMESPACE, OLD_TABLE_NAME)
        df = read_table(NAMESPACE, OLD_TABLE_NAME)
        
        if df is None or df.empty:
            logger.info(f"  ℹ️  {OLD_TABLE_NAME} table is empty. Creating empty {NEW_TABLE_NAME} table.")
        else:
            logger.info(f"  ✅ Read {len(df)} rows from {OLD_TABLE_NAME}")
        
        # Step 2: Create new table with same schema
        logger.info(f"📝 Step 2: Creating {NEW_TABLE_NAME} table...")
        schema = get_comparable_schema()
        catalog.create_table(
            identifier=f"{NAMESPACE[0]}.{NEW_TABLE_NAME}",
            schema=schema
        )
        logger.info(f"  ✅ Created {NEW_TABLE_NAME} table")
        
        # Step 3: Copy data to new table
        if df is not None and not df.empty:
            logger.info(f"📋 Step 3: Copying data to {NEW_TABLE_NAME}...")
            new_table = load_table(NAMESPACE, NEW_TABLE_NAME)
            table_schema = new_table.schema().as_arrow()
            
            # Convert types to match schema (same logic as migration script)
            from datetime import date
            from decimal import Decimal
            import pandas as pd
            
            # Convert timestamp columns to microseconds (required, non-nullable)
            for col in ['created_at', 'updated_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                    df[col] = df[col].dt.floor('us')
                    df[col] = df[col].fillna(pd.Timestamp.now().floor('us'))
            
            # Convert date columns
            for col in ['date_listed', 'date_rented']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.date
                    if col == 'date_listed':
                        df[col] = df[col].fillna(date.today())
            
            # Convert integer columns
            int_cols = ['bedrooms', 'square_feet', 'contacts', 'last_rented_year']
            for col in int_cols:
                if col in df.columns:
                    if col in ['bedrooms', 'square_feet']:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                    else:
                        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
            
            # Convert boolean columns (required fields must not be nullable)
            bool_cols = ['is_subject_property', 'is_active']
            for col in bool_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(False).astype(bool)
            
            # Convert string columns (required fields must not be nullable)
            string_cols = ['id', 'property_id', 'address']
            for col in string_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str)
                    df[col] = df[col].fillna('')
            
            # Convert decimal columns with proper precision
            if 'bathrooms' in df.columns:
                df['bathrooms'] = df['bathrooms'].apply(
                    lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) else Decimal('0')
                )
            
            if 'asking_price' in df.columns:
                df['asking_price'] = df['asking_price'].apply(
                    lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else Decimal('0')
                )
            
            if 'last_rented_price' in df.columns:
                df['last_rented_price'] = df['last_rented_price'].apply(
                    lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else None
                )
            
            if 'garage_spaces' in df.columns:
                df['garage_spaces'] = df['garage_spaces'].apply(
                    lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) and x is not None else None
                )
            
            # Convert DataFrame to PyArrow table with explicit schema casting
            import pyarrow as pa
            arrow_table = pa.Table.from_pandas(df)
            arrow_table = arrow_table.cast(table_schema)
            new_table.append(arrow_table)
            logger.info(f"  ✅ Copied {len(df)} rows to {NEW_TABLE_NAME}")
        
        # Step 4: Drop old table
        logger.info(f"🗑️  Step 4: Dropping {OLD_TABLE_NAME} table...")
        catalog.drop_table(f"{NAMESPACE[0]}.{OLD_TABLE_NAME}")
        logger.info(f"  ✅ Dropped {OLD_TABLE_NAME} table")
        
        logger.info(f"✅ Migration complete: {OLD_TABLE_NAME} -> {NEW_TABLE_NAME}")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

