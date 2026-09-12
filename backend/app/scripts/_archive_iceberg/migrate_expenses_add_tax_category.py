#!/usr/bin/env python3
"""
Migration script to add tax_category column to expenses table.

This script:
1. Backs up expenses data to local parquet file
2. Drops the expenses table
3. Recreates the table with new schema (adds tax_category)
4. Restores data from backup with auto-mapped tax_category values
5. Tests the table

New column:
- tax_category (string, nullable) - IRS Schedule E line item classification

Auto-mapping from expense_type:
- insurance -> insurance
- tax -> taxes
- utilities -> utilities
- property_management -> management_fees
- pandi -> mortgage_interest
- capex -> capital_improvement
- maintenance, rehab, other -> repairs
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from datetime import datetime

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table, append_data

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
EXPENSES_TABLE = "expenses"

EXPENSE_TYPE_TO_TAX_CATEGORY = {
    "insurance": "insurance",
    "tax": "taxes",
    "utilities": "utilities",
    "property_management": "management_fees",
    "pandi": "mortgage_interest",
    "capex": "capital_improvement",
    "maintenance": "repairs",
    "rehab": "repairs",
    "other": "repairs",
}


def create_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for expenses table WITH tax_category"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("description", pa.string(), nullable=False),
        pa.field("date", pa.date32(), nullable=False),
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("vendor", pa.string(), nullable=True),
        pa.field("expense_type", pa.string(), nullable=False),
        pa.field("expense_category", pa.string(), nullable=True),
        pa.field("tax_category", pa.string(), nullable=True),
        pa.field("document_storage_id", pa.string(), nullable=True),
        pa.field("is_planned", pa.bool_(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("created_by_user_id", pa.string(), nullable=True),
    ])


def migrate_expenses_table():
    """Migrate expenses table to add tax_category column"""
    logger.info("🔄 Starting migration to add tax_category to expenses table...")

    try:
        catalog = get_catalog()

        if not table_exists(NAMESPACE, EXPENSES_TABLE):
            logger.warning(f"  ⚠️  Table {EXPENSES_TABLE} does not exist - creating new table...")
            schema = create_expenses_schema()
            catalog.create_table(identifier=(*NAMESPACE, EXPENSES_TABLE), schema=schema)
            logger.info(f"  ✅ Created new {EXPENSES_TABLE} table with tax_category column")
            return True

        # Step 1: Backup
        logger.info("  💾 Step 1: Backing up expenses data to parquet...")
        expenses_df = read_table(NAMESPACE, EXPENSES_TABLE)
        logger.info(f"  ✅ Found {len(expenses_df)} expenses")

        if len(expenses_df) == 0:
            logger.info("  ℹ️  Table is empty - no data to migrate")
            logger.info("  🔄 Dropping and recreating table with new schema...")
            catalog.drop_table((*NAMESPACE, EXPENSES_TABLE))
            schema = create_expenses_schema()
            catalog.create_table(identifier=(*NAMESPACE, EXPENSES_TABLE), schema=schema)
            logger.info("  ✅ Created new table with tax_category column")
            return True

        backup_file = f"/tmp/expenses_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        expenses_df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_file}")

        # Step 2: Add tax_category column with auto-mapping
        logger.info("  🔄 Step 2: Adding tax_category column with auto-mapping...")

        if "tax_category" not in expenses_df.columns:
            expenses_df["tax_category"] = expenses_df["expense_type"].map(
                EXPENSE_TYPE_TO_TAX_CATEGORY
            ).fillna("repairs")
            logger.info("  ✅ Mapped expense_type -> tax_category")

            mapping_counts = expenses_df.groupby(["expense_type", "tax_category"]).size()
            for (exp_type, tax_cat), count in mapping_counts.items():
                logger.info(f"    {exp_type} -> {tax_cat}: {count} expenses")
        else:
            logger.info("  ℹ️  tax_category column already exists")

        # Step 3: Drop the table
        logger.info("  🔄 Step 3: Dropping expenses table...")
        expenses_identifier = (*NAMESPACE, EXPENSES_TABLE)

        try:
            catalog.drop_table(expenses_identifier)
            logger.info("  ✅ Dropped existing table")
        except Exception as e:
            logger.error(f"  ❌ Could not drop table: {e}")
            return False

        # Step 4: Recreate table with new schema
        logger.info("  🔄 Step 4: Recreating expenses table with new schema...")
        schema = create_expenses_schema()
        catalog.create_table(identifier=expenses_identifier, schema=schema)
        logger.info("  ✅ Created new table with tax_category column")

        # Step 5: Restore data from backup
        logger.info("  🔄 Step 5: Restoring data from backup...")

        backup_df = pd.read_parquet(backup_file)
        logger.info(f"  ✅ Loaded {len(backup_df)} expenses from backup")

        # Re-apply tax_category mapping to backup data
        if "tax_category" not in backup_df.columns:
            backup_df["tax_category"] = backup_df["expense_type"].map(
                EXPENSE_TYPE_TO_TAX_CATEGORY
            ).fillna("repairs")

        # Ensure all schema columns exist
        schema_columns = [field.name for field in schema]
        for col in schema_columns:
            if col not in backup_df.columns:
                logger.info(f"  ℹ️  Adding missing column '{col}' with null values")
                backup_df[col] = None

        backup_df = backup_df.reindex(columns=schema_columns, fill_value=None)

        # Convert dates
        if "date" in backup_df.columns:
            backup_df["date"] = pd.to_datetime(backup_df["date"]).dt.date

        append_data(NAMESPACE, EXPENSES_TABLE, backup_df)
        logger.info(f"  ✅ Restored {len(backup_df)} expenses")

        # Step 6: Verify
        logger.info("  🔄 Step 6: Verifying migration...")
        verify_df = read_table(NAMESPACE, EXPENSES_TABLE)
        logger.info(f"  ✅ Verified: {len(verify_df)} expenses in table")

        if "tax_category" not in verify_df.columns:
            logger.error("  ❌ tax_category column missing after migration!")
            return False

        tax_category_counts = verify_df["tax_category"].value_counts()
        logger.info(f"  ✅ tax_category distribution:")
        for cat, count in tax_category_counts.items():
            logger.info(f"    {cat}: {count}")

        null_count = verify_df["tax_category"].isna().sum()
        if null_count > 0:
            logger.warning(f"  ⚠️  {null_count} expenses have null tax_category")

        logger.info("  ✅ Migration completed successfully!")
        logger.info(f"  💾 Backup file: {backup_file}")
        return True

    except Exception as e:
        logger.error(f"  ❌ Migration failed: {e}", exc_info=True)
        return False


def main():
    """Run the migration"""
    logger.info("=" * 70)
    logger.info("EXPENSES TABLE MIGRATION - Add tax_category")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This will:")
    logger.info("  1. Backup existing expenses data")
    logger.info("  2. Add tax_category column (auto-mapped from expense_type)")
    logger.info("  3. Drop the expenses table")
    logger.info("  4. Recreate table with new schema")
    logger.info("  5. Restore data from backup")
    logger.info("  6. Verify the migration")
    logger.info("")
    logger.info("⚠️  WARNING: This will temporarily delete all data!")
    logger.info("")

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

    success = migrate_expenses_table()

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
