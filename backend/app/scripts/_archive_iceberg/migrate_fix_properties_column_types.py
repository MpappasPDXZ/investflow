#!/usr/bin/env python3
"""
Migration script to fix column types in properties table.

This script fixes:
1. bedrooms: float64 -> int32
2. year_built: float64 -> int32
3. unit_count: float64 -> int32
4. bathrooms: float64 -> decimal128(3,1) (optional improvement)

This script:
1. Backs up properties data to local parquet file
2. Reads the table and converts columns to correct types
3. Rewrites the table with the corrected schema
4. Verifies the migration
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from decimal import Decimal as PythonDecimal
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"


def create_properties_schema() -> pa.Schema:
    """Create PyArrow schema for properties table with correct types"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),  # UUID as string
        pa.field("display_name", pa.string(), nullable=True),
        pa.field("purchase_price", pa.int64(), nullable=False),  # FIXED: int64 (dollars)
        pa.field("down_payment", pa.int64(), nullable=True),  # FIXED: int64 (dollars)
        pa.field("cash_invested", pa.int64(), nullable=True),  # FIXED: int64 (dollars)
        pa.field("current_market_value", pa.int64(), nullable=True),  # FIXED: int64 (dollars)
        pa.field("property_status", pa.string(), nullable=True),
        pa.field("vacancy_rate", pa.float64(), nullable=True),  # FIXED: float64
        pa.field("purchase_date", pa.date32(), nullable=True),  # FIXED: date32 (not timestamp)
        pa.field("monthly_rent_to_income_ratio", pa.decimal128(4, 2), nullable=True),
        pa.field("address_line1", pa.string(), nullable=True),
        pa.field("address_line2", pa.string(), nullable=True),
        pa.field("city", pa.string(), nullable=True),
        pa.field("state", pa.string(), nullable=True),
        pa.field("zip_code", pa.string(), nullable=True),
        pa.field("property_type", pa.string(), nullable=True),
        pa.field("has_units", pa.bool_(), nullable=True),
        pa.field("unit_count", pa.int64(), nullable=True),  # FIXED: int64
        pa.field("bedrooms", pa.int64(), nullable=True),  # FIXED: int64
        pa.field("bathrooms", pa.float64(), nullable=True),  # FIXED: float64 (allows one decimal place)
        pa.field("square_feet", pa.int64(), nullable=True),
        pa.field("year_built", pa.int64(), nullable=True),  # FIXED: int64
        pa.field("current_monthly_rent", pa.float64(), nullable=True),  # FIXED: float64
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def migrate_properties_table():
    """Migrate properties table to fix column types"""
    logger.info("=" * 80)
    logger.info("🔄 Migrating properties table: fixing column types")
    logger.info("=" * 80)
    
    try:
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, TABLE_NAME)
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning(f"  ⚠️  {TABLE_NAME} table doesn't exist, skipping")
            return
        
        # Step 1: Load table
        logger.info(f"📖 Step 1: Loading {TABLE_NAME} table...")
        table = catalog.load_table(table_identifier)
        current_schema = table.schema()
        
        # Check current column types
        logger.info("  📊 Current column types:")
        for field in current_schema.fields:
            if field.name in ["bedrooms", "year_built", "unit_count", "bathrooms"]:
                logger.info(f"    {field.name}: {field.field_type}")
        
        # Step 2: Backup data
        logger.info(f"💾 Step 2: Backing up {TABLE_NAME} data...")
        backup_dir = Path("/tmp/iceberg_migrations")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{TABLE_NAME}_backup_{timestamp}.parquet"
        
        df = read_table(NAMESPACE, TABLE_NAME)
        df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_file}")
        logger.info(f"  📊 Rows: {len(df)}")
        
        # Step 3: Convert integer columns (bedrooms, year_built, unit_count, down_payment, cash_invested, current_market_value)
        logger.info(f"🔄 Step 3: Converting integer columns to int64...")
        
        int_columns = ["bedrooms", "year_built", "unit_count", "purchase_price", "down_payment", "cash_invested", "current_market_value", "square_feet"]
        for col in int_columns:
            if col in df.columns:
                def to_int64(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        # Convert decimal/float to int64 (handles NaN and float values)
                        # For money columns (purchase_price, down_payment, cash_invested, current_market_value), 
                        # convert from decimal to int64 in dollars (rounded)
                        if col in ["purchase_price", "down_payment", "cash_invested", "current_market_value"]:
                            # Convert from decimal to int64 in dollars
                            val = float(x)
                            if pd.isna(val):
                                return None
                            return int(round(val))  # Round to nearest dollar, then convert to int64
                        else:
                            # Regular integer conversion to int64
                            val = float(x)
                            if pd.isna(val):
                                return None
                            return int(val)
                    except (ValueError, TypeError, OverflowError):
                        return None
                
                before_type = df[col].dtype
                df[col] = df[col].apply(to_int64)
                after_type = df[col].dtype
                logger.info(f"  ✅ {col}: {before_type} -> {after_type}")
                
                # Show sample values
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    sample = non_null.head(3).tolist()
                    if col in ["down_payment", "cash_invested", "current_market_value"]:
                        # Show in dollars for readability
                        sample_dollars = [f"${s}" for s in sample]
                        logger.info(f"    Sample values: {sample} ({', '.join(sample_dollars)})")
                    else:
                        logger.info(f"    Sample values: {sample}")
        
        # Step 4: Convert float columns (vacancy_rate, current_monthly_rent, bathrooms)
        logger.info(f"🔄 Step 4: Converting float columns...")
        
        float_columns = ["vacancy_rate", "current_monthly_rent", "bathrooms"]
        for col in float_columns:
            if col in df.columns:
                def to_float64(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        val = float(x)
                        if pd.isna(val):
                            return None
                        return val
                    except (ValueError, TypeError, OverflowError):
                        return None
                
                before_type = df[col].dtype
                df[col] = df[col].apply(to_float64)
                after_type = df[col].dtype
                logger.info(f"  ✅ {col}: {before_type} -> {after_type}")
                
                # Show sample values
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    logger.info(f"    Sample values: {non_null.head(3).tolist()}")
        
        # Step 4b: Convert purchase_date to date32
        logger.info(f"🔄 Step 4b: Converting purchase_date to date32...")
        if "purchase_date" in df.columns:
            before_type = df["purchase_date"].dtype
            
            # Convert to date - handle various input types
            def to_date(x):
                if pd.isna(x) or x is None:
                    return None
                try:
                    # If already a date, return as-is
                    if isinstance(x, (pd.Timestamp, datetime)):
                        return x.date() if hasattr(x, 'date') else x
                    elif isinstance(x, str):
                        # Parse string to date
                        parsed = pd.to_datetime(x, errors='coerce')
                        if pd.isna(parsed):
                            return None
                        return parsed.date() if hasattr(parsed, 'date') else parsed
                    else:
                        return None
                except (ValueError, TypeError, OverflowError):
                    return None
            
            # Apply conversion
            df["purchase_date"] = df["purchase_date"].apply(to_date)
            
            # Convert to pandas date type (will be converted to date32 by PyArrow)
            # Keep as date objects for now, PyArrow will handle the conversion
            after_type = df["purchase_date"].dtype
            logger.info(f"  ✅ purchase_date: {before_type} -> {after_type}")
            
            # Show sample values
            non_null = df["purchase_date"].dropna()
            if len(non_null) > 0:
                logger.info(f"    Sample values: {[str(d) for d in non_null.head(3).tolist()]}")
        
        # Step 5: Get target schema
        target_schema = create_properties_schema()
        
        # Step 6: Ensure all columns match schema
        logger.info(f"🔧 Step 5: Aligning DataFrame with target schema...")
        schema_field_names = {field.name for field in target_schema}
        
        # Add missing columns with None
        for field in target_schema:
            if field.name not in df.columns:
                df[field.name] = None
                logger.info(f"  ➕ Added missing column: {field.name}")
        
        # Remove extra columns (shouldn't happen, but be safe)
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            logger.warning(f"  ⚠️  Removing columns not in schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Reorder columns to match schema
        schema_column_order = [field.name for field in target_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Step 7: Convert remaining decimal columns to Python Decimal objects
        logger.info(f"💰 Step 6: Converting remaining decimal columns...")
        decimal_columns = [
            "monthly_rent_to_income_ratio"
        ]
        for col in decimal_columns:
            if col in df.columns:
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(x))
                    except (ValueError, TypeError):
                        return None
                df[col] = df[col].apply(to_decimal)
        
        # Step 8: Convert timestamps (excluding purchase_date which is now date)
        logger.info(f"🕐 Step 7: Converting timestamp columns...")
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors='coerce').dt.tz_localize(None).dt.floor('us')
        
        # Step 9: Drop and recreate table with new schema
        logger.info(f"🔄 Step 8: Dropping and recreating table with corrected schema...")
        
        # Drop existing table
        logger.info(f"  🗑️  Dropping existing table...")
        try:
            catalog.drop_table(table_identifier)
            logger.info(f"  ✅ Table dropped")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not drop table (may not exist): {e}")
        
        # Create new table with target schema
        logger.info(f"  🔨 Creating new table with corrected schema...")
        try:
            catalog.create_table(
                identifier=table_identifier,
                schema=target_schema
            )
            logger.info(f"  ✅ Table created with corrected schema")
        except Exception as e:
            logger.error(f"  ❌ Failed to create table: {e}", exc_info=True)
            raise
        
        # Reload table
        table = catalog.load_table(table_identifier)
        
        # Step 10: Convert to PyArrow and append data
        logger.info(f"💾 Step 9: Inserting converted data...")
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        
        # Cast to target schema
        arrow_table = arrow_table.cast(target_schema)
        
        # Append the data
        table.append(arrow_table)
        
        logger.info(f"  ✅ Successfully rewrote {len(df)} rows with corrected column types")
        
        # Step 11: Verify
        logger.info(f"✅ Step 10: Verifying migration...")
        verify_table = catalog.load_table(table_identifier)
        verify_schema = verify_table.schema()
        
        # Check corrected column types
        logger.info("  📊 Verified column types:")
        check_columns = [
            "bedrooms", "year_built", "unit_count", "bathrooms",
            "down_payment", "cash_invested", "current_market_value",
            "vacancy_rate", "current_monthly_rent", "purchase_date"
        ]
        for field in verify_schema.fields:
            if field.name in check_columns:
                from pyiceberg.types import IntegerType, DecimalType, DateType, FloatType
                if isinstance(field.field_type, IntegerType):
                    logger.info(f"    ✅ {field.name}: int64")
                elif isinstance(field.field_type, DecimalType):
                    logger.info(f"    ✅ {field.name}: decimal128({field.field_type.precision},{field.field_type.scale})")
                elif isinstance(field.field_type, DateType):
                    logger.info(f"    ✅ {field.name}: date32")
                elif isinstance(field.field_type, FloatType):
                    logger.info(f"    ✅ {field.name}: float64")
                else:
                    logger.warning(f"    ⚠️  {field.name}: {field.field_type}")
        
        verify_df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"  ✅ Verification: Table has {len(verify_df)} rows")
        logger.info(f"  ✅ Columns: {len(verify_df.columns)}")
        
        # Show corrected dtypes
        logger.info("  📊 Corrected dtypes:")
        for col in check_columns:
            if col in verify_df.columns:
                logger.info(f"    {col}: {verify_df[col].dtype}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ Migration completed successfully!")
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"❌ Error migrating {TABLE_NAME}: {e}", exc_info=True)
        raise


def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("Migration: Fix properties table column types")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This migration fixes the following column types:")
    logger.info("  - bedrooms: float64 -> int64")
    logger.info("  - year_built: float64 -> int64")
    logger.info("  - unit_count: float64 -> int64")
    logger.info("  - square_feet: -> int64")
    logger.info("  - purchase_price: decimal128 -> int64 (dollars)")
    logger.info("  - down_payment: decimal128 -> int64 (dollars)")
    logger.info("  - cash_invested: decimal128 -> int64 (dollars)")
    logger.info("  - current_market_value: decimal128 -> int64 (dollars)")
    logger.info("  - vacancy_rate: decimal128 -> float64")
    logger.info("  - current_monthly_rent: decimal128 -> float64")
    logger.info("  - bathrooms: -> float64 (allows one decimal place precision)")
    logger.info("  - purchase_date: timestamp -> date32")
    logger.info("")
    
    migrate_properties_table()
    
    logger.info("=" * 80)
    logger.info("✅ Migration completed successfully!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

