#!/usr/bin/env python3
"""
Migration script to add missing columns to rents table.

This script:
1. Backs up rents data to local parquet file
2. Drops the rents table
3. Recreates the table with new schema (adds user_id, unit_id, rent_period_month, rent_period_year)
4. Restores data from backup (calculates month/year from rent_period_start if needed)
5. Tests the table

New columns added:
- user_id (string, UUID, required) - For multi-tenant support
- unit_id (string, UUID, nullable) - Already used by API
- rent_period_month (int32, 1-12, required) - Store month separately
- rent_period_year (int32, required) - Store year separately

Changes:
- client_id made optional (nullable) instead of required
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table, append_data

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
RENTS_TABLE = "rents"


def create_rents_schema() -> pa.Schema:
    """Create PyArrow schema for rents table WITH all required fields and denormalized text fields"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        # Denormalized user fields (for speed - avoid joins)
        pa.field("user_id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_name", pa.string(), nullable=True),  # Text - denormalized for speed
        # Denormalized property fields (for speed - avoid joins)
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_name", pa.string(), nullable=True),  # Text - denormalized for speed
        # Denormalized unit fields (for speed - avoid joins)
        pa.field("unit_id", pa.string(), nullable=True),  # UUID as string - nullable
        pa.field("unit_name", pa.string(), nullable=True),  # Text - denormalized for speed (unit_number)
        # Denormalized tenant fields (for speed - avoid joins)
        pa.field("tenant_id", pa.string(), nullable=True),  # UUID as string - nullable (was client_id)
        pa.field("tenant_name", pa.string(), nullable=True),  # Text - denormalized for speed
        # Revenue classification
        pa.field("revenue_description", pa.string(), nullable=True),  # Monthly Rent, Partial Month Rent, One Time Pet Fee, One Time Application Fee, Deposit, Other
        pa.field("is_non_irs_revenue", pa.bool_(), nullable=True),  # true for deposits and other non-IRS revenue (doesn't count toward revenue vs cost)
        # Rent period - month/year with overrideable date range, or one-time fee
        pa.field("is_one_time_fee", pa.bool_(), nullable=True),  # true for one-time fees (pet fee, application fee, etc.)
        pa.field("rent_period_month", pa.int32(), nullable=True),  # 1-12 - month the rent is for (null for one-time fees)
        pa.field("rent_period_year", pa.int32(), nullable=True),  # year the rent is for (null for one-time fees)
        pa.field("rent_period_start", pa.date32(), nullable=False),  # start date (defaults to month start, or single date for one-time fee)
        pa.field("rent_period_end", pa.date32(), nullable=False),  # end date (defaults to month end, or same as start for one-time fee)
        # Payment details
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("payment_date", pa.date32(), nullable=False),
        pa.field("payment_method", pa.string(), nullable=True),  # enum as string
        pa.field("transaction_reference", pa.string(), nullable=True),
        pa.field("is_late", pa.bool_(), nullable=True),
        pa.field("late_fee", pa.decimal128(10, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        # Document storage
        pa.field("document_storage_id", pa.string(), nullable=True),  # UUID as string - reference to document_storage table
        # Timestamps
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("created_by_user_id", pa.string(), nullable=True),  # UUID as string
    ])


def migrate_rents_table():
    """Migrate rents table to add missing columns"""
    logger.info("🔄 Starting migration to add columns to rents table...")
    
    try:
        catalog = get_catalog()
        
        # Check if table exists
        if not table_exists(NAMESPACE, RENTS_TABLE):
            logger.warning(f"  ⚠️  Table {RENTS_TABLE} does not exist - creating new table...")
            schema = create_rents_schema()
            catalog.create_table(identifier=(*NAMESPACE, RENTS_TABLE), schema=schema)
            logger.info(f"  ✅ Created new {RENTS_TABLE} table with complete schema")
            return True
        
        # Step 1: Backup rents data to parquet
        logger.info("  💾 Step 1: Backing up rents data to parquet...")
        rents_df = read_table(NAMESPACE, RENTS_TABLE)
        logger.info(f"  ✅ Found {len(rents_df)} rent payments")
        
        if len(rents_df) == 0:
            logger.info("  ℹ️  Table is empty - no data to migrate")
            # Still need to recreate table with new schema
            logger.info("  🔄 Dropping and recreating table with new schema...")
            catalog.drop_table((*NAMESPACE, RENTS_TABLE))
            schema = create_rents_schema()
            catalog.create_table(identifier=(*NAMESPACE, RENTS_TABLE), schema=schema)
            logger.info("  ✅ Created new table with complete schema")
            return True
        
        backup_file = f"/tmp/rents_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        rents_df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_file}")
        
        # Step 2: Calculate missing fields from existing data
        logger.info("  🔄 Step 2: Calculating missing fields from existing data...")
        
        # Calculate rent_period_month and rent_period_year from rent_period_start if missing
        if "rent_period_month" not in rents_df.columns or "rent_period_year" not in rents_df.columns:
            logger.info("  📅 Calculating rent_period_month and rent_period_year from rent_period_start...")
            if "rent_period_start" in rents_df.columns:
                rents_df["rent_period_start"] = pd.to_datetime(rents_df["rent_period_start"])
                rents_df["rent_period_month"] = rents_df["rent_period_start"].dt.month
                rents_df["rent_period_year"] = rents_df["rent_period_start"].dt.year
                logger.info("  ✅ Calculated month/year from rent_period_start")
            else:
                logger.warning("  ⚠️  rent_period_start not found - setting defaults")
                rents_df["rent_period_month"] = 1
                rents_df["rent_period_year"] = datetime.now().year
        
        # Add user_id if missing (required field)
        if "user_id" not in rents_df.columns:
            logger.warning("  ⚠️  user_id not found - this is required!")
            logger.warning("  ⚠️  Setting user_id to 'MIGRATION_NEEDED' - you'll need to update these manually")
            rents_df["user_id"] = "MIGRATION_NEEDED"
        
        # Add unit_id if missing (nullable, so can be None)
        if "unit_id" not in rents_df.columns:
            logger.info("  ℹ️  unit_id not found - setting to None (nullable)")
            rents_df["unit_id"] = None
        
        # Make client_id nullable if it's currently required
        if "client_id" in rents_df.columns:
            # Replace any empty strings or invalid values with None
            rents_df["client_id"] = rents_df["client_id"].replace("", None)
            rents_df["client_id"] = rents_df["client_id"].where(pd.notna(rents_df["client_id"]), None)
        
        # Step 3: Drop the table
        logger.info("  🔄 Step 3: Dropping rents table...")
        rents_identifier = (*NAMESPACE, RENTS_TABLE)
        
        try:
            catalog.drop_table(rents_identifier)
            logger.info("  ✅ Dropped existing table")
        except Exception as e:
            logger.error(f"  ❌ Could not drop table: {e}")
            return False
        
        # Step 4: Recreate table with new schema
        logger.info("  🔄 Step 4: Recreating rents table with new schema...")
        schema = create_rents_schema()
        catalog.create_table(identifier=rents_identifier, schema=schema)
        logger.info("  ✅ Created new table with complete schema")
        
        # Step 5: Restore data from backup
        logger.info("  🔄 Step 5: Restoring data from backup...")
        
        # Read backup
        backup_df = pd.read_parquet(backup_file)
        logger.info(f"  ✅ Loaded {len(backup_df)} rent payments from backup")
        
        # Ensure all required columns are present
        required_cols = [
            "id", "user_id", "user_name", "property_id", "property_name",
            "unit_id", "unit_name", "tenant_id", "tenant_name",
            "revenue_description", "is_non_irs_revenue", "is_one_time_fee",
            "amount", "rent_period_month", "rent_period_year",
            "rent_period_start", "rent_period_end", "payment_date",
            "payment_method", "transaction_reference", "is_late", "late_fee", "notes",
            "created_at", "updated_at", "created_by_user_id"
        ]
        
        # Add missing columns with defaults
        # Handle tenant_id (rename from client_id if needed)
        if "tenant_id" not in backup_df.columns and "client_id" in backup_df.columns:
            logger.info("  ℹ️  Renaming 'client_id' to 'tenant_id'.")
            backup_df["tenant_id"] = backup_df["client_id"]
        
        for col in required_cols:
            if col not in backup_df.columns:
                if col == "user_id":
                    backup_df[col] = "MIGRATION_NEEDED"  # Will need manual update
                elif col in ["user_name", "property_name", "unit_name", "tenant_name"]:
                    backup_df[col] = None  # Denormalized fields - will be populated on new records
                elif col in ["unit_id", "tenant_id"]:
                    backup_df[col] = None
                elif col == "is_one_time_fee":
                    backup_df[col] = False  # All existing records are regular rent
                elif col == "revenue_description":
                    backup_df[col] = None  # Will be populated on new records
                elif col == "is_non_irs_revenue":
                    backup_df[col] = False  # Default to False for existing records
                elif col == "revenue_description":
                    backup_df[col] = None  # Will be populated on new records
                elif col == "is_non_irs_revenue":
                    backup_df[col] = False  # Default to False for existing records
                elif col == "rent_period_month":
                    if "rent_period_start" in backup_df.columns:
                        backup_df["rent_period_start"] = pd.to_datetime(backup_df["rent_period_start"])
                        backup_df[col] = backup_df["rent_period_start"].dt.month
                    else:
                        backup_df[col] = 1
                elif col == "rent_period_year":
                    if "rent_period_start" in backup_df.columns:
                        backup_df["rent_period_start"] = pd.to_datetime(backup_df["rent_period_start"])
                        backup_df[col] = backup_df["rent_period_start"].dt.year
                    else:
                        backup_df[col] = datetime.now().year
                elif col in ["is_late"]:
                    backup_df[col] = False
                elif col in ["payment_method", "transaction_reference", "notes", "late_fee", "created_by_user_id"]:
                    backup_df[col] = None
                else:
                    logger.warning(f"  ⚠️  Missing required column: {col}")
        
        # Select only the columns that match the schema
        schema_columns = [field.name for field in schema]
        backup_df = backup_df.reindex(columns=schema_columns, fill_value=None)
        
        # Convert dates to proper format
        date_columns = ["rent_period_start", "rent_period_end", "payment_date"]
        for col in date_columns:
            if col in backup_df.columns:
                backup_df[col] = pd.to_datetime(backup_df[col]).dt.date
        
        # Append restored data
        append_data(NAMESPACE, RENTS_TABLE, backup_df)
        logger.info(f"  ✅ Restored {len(backup_df)} rent payments")
        
        # Step 6: Verify the migration
        logger.info("  🔄 Step 6: Verifying migration...")
        verify_df = read_table(NAMESPACE, RENTS_TABLE)
        logger.info(f"  ✅ Verified: {len(verify_df)} rent payments in table")
        
        # Check for required columns
        required_cols_check = [
            "user_id", "user_name", "property_name", "unit_id", "unit_name",
            "tenant_id", "tenant_name", "revenue_description", "is_non_irs_revenue",
            "is_one_time_fee", "rent_period_month", "rent_period_year"
        ]
        missing_cols = [col for col in required_cols_check if col not in verify_df.columns]
        if missing_cols:
            logger.error(f"  ❌ Missing columns after migration: {missing_cols}")
            return False
        else:
            logger.info(f"  ✅ All required columns present: {required_cols_check}")
        
        # Check for MIGRATION_NEEDED user_ids
        if "user_id" in verify_df.columns:
            migration_needed = verify_df[verify_df["user_id"] == "MIGRATION_NEEDED"]
            if len(migration_needed) > 0:
                logger.warning(f"  ⚠️  {len(migration_needed)} rent payments have user_id='MIGRATION_NEEDED'")
                logger.warning(f"  ⚠️  These need to be updated manually with correct user_id values")
        
        logger.info("  ✅ Migration completed successfully!")
        logger.info(f"  💾 Backup file: {backup_file}")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Migration failed: {e}", exc_info=True)
        return False


def main():
    """Run the migration"""
    logger.info("=" * 70)
    logger.info("RENTS TABLE MIGRATION")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This will:")
    logger.info("  1. Backup existing rents data")
    logger.info("  2. Drop the rents table")
    logger.info("  3. Recreate table with new schema (adds user_id, unit_id, rent_period_month, rent_period_year)")
    logger.info("  4. Restore data from backup")
    logger.info("  5. Verify the migration")
    logger.info("")
    logger.info("⚠️  WARNING: This will temporarily delete all data!")
    logger.info("")
    
    # Check for --yes flag to skip confirmation
    import sys
    skip_confirmation = '--yes' in sys.argv or '--force' in sys.argv
    
    if not skip_confirmation:
        try:
            response = input("Type 'YES' to proceed: ")
            if response != "YES":
                logger.info("❌ Migration cancelled")
                return
        except EOFError:
            logger.warning("⚠️  No input available. Use --yes flag to run non-interactively.")
            logger.info("❌ Migration cancelled")
            return
    else:
        logger.info("✅ Running in non-interactive mode (--yes flag detected)")
    
    success = migrate_rents_table()
    
    if success:
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ MIGRATION COMPLETE")
        logger.info("=" * 70)
    else:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ MIGRATION FAILED")
        logger.error("=" * 70)
        logger.error("⚠️  You may need to restore from backup manually")
        sys.exit(1)


if __name__ == "__main__":
    main()

