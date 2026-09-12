#!/usr/bin/env python3
"""
Migration script to add date_rented to leases table and populate it for comparables.

This script:
1. Backs up all leases table data to parquet
2. Reads all data
3. For comparables with last_rented_price > 0, sets date_rented = date_listed + 30 days
4. Rewrites the table with all data (ensuring all parquet files have the new column)

CRITICAL: This preserves all data - both actual leases and comparables.
"""
import sys
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import pyarrow as pa
from decimal import Decimal

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)
TABLE_NAME = "leases"


def is_comparable(row: pd.Series) -> bool:
    """Check if a row is a comparable (not an actual lease)"""
    # Comparables have asking_price and date_listed
    # Actual leases have monthly_rent and commencement_date
    has_asking_price = pd.notna(row.get('asking_price')) and row.get('asking_price', 0) > 0
    has_date_listed = pd.notna(row.get('date_listed'))
    has_monthly_rent = pd.notna(row.get('monthly_rent')) and row.get('monthly_rent', 0) > 0
    
    # If it has asking_price and date_listed, it's a comparable
    # If it has monthly_rent, it's an actual lease
    return has_asking_price and has_date_listed and not has_monthly_rent


def main():
    logger.info("=" * 80)
    logger.info("🚀 Starting leases table migration: Add date_rented column")
    logger.info("=" * 80)
    
    try:
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, TABLE_NAME)
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("  ❌ Leases table doesn't exist!")
            sys.exit(1)
        
        # Step 1: Read all existing data
        logger.info("📖 Step 1: Reading all leases table data...")
        table = catalog.load_table(table_identifier)
        df = table.scan().to_pandas()
        
        if df.empty:
            logger.warning("  ⚠️  Leases table is empty, nothing to migrate")
            return
        
        total_rows = len(df)
        logger.info(f"  ✅ Read {total_rows} rows")
        
        # Step 2: Backup to parquet
        logger.info("💾 Step 2: Creating backup...")
        backup_path = f"/tmp/leases_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        df.to_parquet(backup_path, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_path}")
        logger.info(f"  📊 Backup has {len(df)} rows and {len(df.columns)} columns")
        
        # Step 3: Identify comparables and update date_rented
        logger.info("🔄 Step 3: Processing comparables...")
        
        # Add date_rented column if it doesn't exist
        if 'date_rented' not in df.columns:
            df['date_rented'] = None
        
        comparables_updated = 0
        comparables_found = 0
        
        for idx, row in df.iterrows():
            if is_comparable(row):
                comparables_found += 1
                
                # Check if this comparable has last_rented_price > 0
                last_rented_price = row.get('last_rented_price')
                date_listed = row.get('date_listed')
                current_date_rented = row.get('date_rented')
                
                # Only update if:
                # 1. last_rented_price > 0
                # 2. date_listed exists
                # 3. date_rented is not already set
                if (pd.notna(last_rented_price) and 
                    float(last_rented_price) > 0 and 
                    pd.notna(date_listed) and 
                    pd.isna(current_date_rented)):
                    
                    # Convert date_listed to date if needed
                    if isinstance(date_listed, pd.Timestamp):
                        date_listed_date = date_listed.date()
                    elif isinstance(date_listed, date):
                        date_listed_date = date_listed
                    elif isinstance(date_listed, str):
                        from datetime import datetime
                        date_listed_date = datetime.strptime(date_listed, "%Y-%m-%d").date()
                    else:
                        date_listed_date = date_listed
                    
                    # Set date_rented = date_listed + 30 days
                    date_rented_value = date_listed_date + timedelta(days=30)
                    df.at[idx, 'date_rented'] = date_rented_value
                    comparables_updated += 1
        
        logger.info(f"  ✅ Found {comparables_found} comparables")
        logger.info(f"  ✅ Updated {comparables_updated} comparables with date_rented")
        
        # Step 4: Prepare data for rewrite
        logger.info("🔄 Step 4: Preparing data for rewrite...")
        
        # Get table schema
        schema = table.schema()
        arrow_schema = schema.as_arrow()
        
        # Ensure all schema columns exist in DataFrame
        for field in arrow_schema:
            if field.name not in df.columns:
                df[field.name] = None
        
        # Remove any extra columns not in schema
        schema_field_names = {field.name for field in arrow_schema}
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            logger.warning(f"  ⚠️  Removing columns not in schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Reorder columns to match schema
        schema_column_order = [field.name for field in arrow_schema]
        df = df[schema_column_order]
        
        # Convert date columns
        for col in ['date_listed', 'date_rented']:
            if col in df.columns:
                def to_date(x):
                    if pd.isna(x) or x is None:
                        return None
                    if isinstance(x, pd.Timestamp):
                        return x.date()
                    if isinstance(x, date):
                        return x
                    if isinstance(x, str):
                        from datetime import datetime
                        try:
                            return datetime.strptime(x, "%Y-%m-%d").date()
                        except:
                            return None
                    return None
                df[col] = df[col].apply(to_date)
        
        # Convert decimal columns
        from decimal import Decimal as PythonDecimal
        decimal_cols = ['bathrooms', 'asking_price', 'last_rented_price']
        for col in decimal_cols:
            if col in df.columns:
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(round(float(x), 2)))
                    except:
                        return None
                df[col] = df[col].apply(to_decimal)
        
        # Convert integer columns
        int_cols = ['bedrooms', 'square_feet', 'contacts', 'last_rented_year']
        for col in int_cols:
            if col in df.columns:
                def to_int(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return int(x)
                    except:
                        return None
                df[col] = df[col].apply(to_int)
        
        # Convert timestamps
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Step 5: Convert to PyArrow and overwrite
        logger.info("💾 Step 5: Rewriting table with updated data...")
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        arrow_table = arrow_table.cast(arrow_schema)
        
        # Overwrite the table (this creates new parquet files with full schema)
        table.overwrite(arrow_table)
        
        logger.info(f"  ✅ Successfully rewrote {len(df)} rows")
        
        # Step 6: Verify
        logger.info("✅ Step 6: Verifying migration...")
        verify_df = table.scan().to_pandas()
        logger.info(f"  ✅ Verification: Table now has {len(verify_df)} rows")
        logger.info(f"  ✅ Columns: {len(verify_df.columns)} (including date_rented)")
        
        if 'date_rented' in verify_df.columns:
            date_rented_count = verify_df['date_rented'].notna().sum()
            logger.info(f"  ✅ date_rented populated in {date_rented_count} rows")
        
        logger.info("=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        logger.info(f"📦 Backup location: {backup_path}")
        logger.info(f"📊 Total rows migrated: {total_rows}")
        logger.info(f"🔄 Comparables updated: {comparables_updated}")
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        logger.error("=" * 80)
        logger.error("⚠️  Your data is safe in the backup file")
        sys.exit(1)


if __name__ == "__main__":
    main()

