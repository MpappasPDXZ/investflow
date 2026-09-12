#!/usr/bin/env python3
"""
Migration script to remove user_id, tenant_signed, and landlord_signed from walkthroughs table.

This script:
1. Backs up walkthroughs data to local parquet file
2. Drops the walkthroughs table
3. Recreates the table without user_id, tenant_signed, landlord_signed columns
4. Restores data from backup (excluding removed columns)
5. Tests the table
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
WALKTHROUGHS_TABLE = "walkthroughs"


def create_walkthroughs_schema() -> pa.Schema:
    """Create PyArrow schema for walkthroughs table WITHOUT user_id, tenant_signed, landlord_signed"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("property_display_name", pa.string(), nullable=True),
        pa.field("unit_number", pa.string(), nullable=True),
        pa.field("walkthrough_type", pa.string(), nullable=False),
        pa.field("walkthrough_date", pa.date32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("inspector_name", pa.string(), nullable=True),
        pa.field("tenant_name", pa.string(), nullable=True),
        pa.field("tenant_signature_date", pa.date32(), nullable=True),
        pa.field("landlord_signature_date", pa.date32(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("generated_pdf_blob_name", pa.string(), nullable=True),
        pa.field("areas_json", pa.string(), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=False),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def migrate_walkthroughs():
    """Remove user_id, tenant_signed, landlord_signed columns from walkthroughs table"""
    logger.info("🔄 Starting migration to remove user_id, tenant_signed, landlord_signed columns...")
    
    try:
        catalog = get_catalog()
        
        # Step 1: Backup walkthroughs data to parquet (or use existing backup)
        backup_file = None
        if table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            logger.info("  💾 Step 1: Backing up walkthroughs data to parquet...")
            walkthroughs_df = read_table(NAMESPACE, WALKTHROUGHS_TABLE)
            logger.info(f"  ✅ Found {len(walkthroughs_df)} walkthroughs")
            
            backup_file = f"/tmp/walkthroughs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
            walkthroughs_df.to_parquet(backup_file, index=False)
            logger.info(f"  ✅ Backup saved to: {backup_file}")
        else:
            # Table doesn't exist - look for most recent backup
            import glob
            backup_files = glob.glob("/tmp/walkthroughs_backup_*.parquet")
            if backup_files:
                backup_file = max(backup_files, key=lambda x: Path(x).stat().st_mtime)
                logger.info(f"  💾 Step 1: Table doesn't exist, using existing backup: {backup_file}")
            else:
                logger.error(f"  ❌ Table {WALKTHROUGHS_TABLE} does not exist and no backup found!")
                return False
        
        # Step 2: Drop the table (if it exists)
        logger.info("  🔄 Step 2: Dropping walkthroughs table (if exists)...")
        walkthroughs_identifier = (*NAMESPACE, WALKTHROUGHS_TABLE)
        
        if table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            try:
                catalog.drop_table(walkthroughs_identifier)
                logger.info("  ✅ Dropped existing table")
            except Exception as e:
                logger.error(f"  ❌ Could not drop table: {e}")
                return False
        else:
            logger.info("  ℹ️  Table doesn't exist, skipping drop")
        
        # Step 3: Recreate table with new schema (without user_id, tenant_signed, landlord_signed)
        logger.info("  🔄 Step 3: Recreating walkthroughs table without user_id, tenant_signed, landlord_signed...")
        schema = create_walkthroughs_schema()
        from pyiceberg.partitioning import PartitionSpec
        partition_spec = PartitionSpec()
        catalog.create_table(identifier=walkthroughs_identifier, schema=schema, partition_spec=partition_spec)
        logger.info("  ✅ Created new table without removed columns")
        
        # Step 4: Restore data from backup (excluding removed columns)
        logger.info("  🔄 Step 4: Restoring data from backup...")
        
        # Read backup
        backup_df = pd.read_parquet(backup_file)
        logger.info(f"  ✅ Loaded {len(backup_df)} walkthroughs from backup")
        
        # Remove columns that no longer exist
        columns_to_remove = ["user_id", "tenant_signed", "landlord_signed"]
        for col in columns_to_remove:
            if col in backup_df.columns:
                backup_df = backup_df.drop(columns=[col])
                logger.info(f"  ✅ Removed {col} column from backup data")
        
        # Load the new table to get schema
        new_table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        schema_fields = {field.name for field in new_table.schema().fields}
        
        # Ensure all columns match the new schema
        backup_columns = set(backup_df.columns)
        missing_columns = schema_fields - backup_columns
        extra_columns = backup_columns - schema_fields
        
        if missing_columns:
            logger.warning(f"  ⚠️  Missing columns in backup: {missing_columns}")
            for col in missing_columns:
                # Set default values based on column name
                if col == "is_active":
                    backup_df[col] = True
                else:
                    backup_df[col] = None
        
        if extra_columns:
            logger.warning(f"  ⚠️  Extra columns in backup (will be dropped): {extra_columns}")
            backup_df = backup_df.drop(columns=list(extra_columns))
        
        # Reorder columns to match schema
        schema_columns = [field.name for field in new_table.schema().fields]
        backup_df = backup_df.reindex(columns=schema_columns, fill_value=None)
        
        # Convert data types to match schema
        for field in new_table.schema().fields:
            col_name = field.name
            if col_name in backup_df.columns:
                field_type = field.field_type if hasattr(field, 'field_type') else None
                if field_type:
                    type_str = str(field_type)
                    if 'bool' in type_str.lower():
                        backup_df[col_name] = backup_df[col_name].astype(bool).fillna(False)
                    elif 'date32' in type_str.lower() or 'date' in type_str.lower():
                        # Convert to date
                        backup_df[col_name] = pd.to_datetime(backup_df[col_name]).dt.date
                    elif 'timestamp' in type_str.lower():
                        # Convert to datetime
                        backup_df[col_name] = pd.to_datetime(backup_df[col_name])
        
        # Append data to new table
        append_data(NAMESPACE, WALKTHROUGHS_TABLE, backup_df)
        logger.info(f"  ✅ Restored {len(backup_df)} walkthroughs to new table")
        
        # Step 5: Test the table
        logger.info("  🧪 Step 5: Testing the table...")
        test_df = read_table(NAMESPACE, WALKTHROUGHS_TABLE)
        logger.info(f"  ✅ Table test successful - found {len(test_df)} walkthroughs")
        
        # Verify removed columns are not in schema
        test_table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        schema_fields = {field.name for field in test_table.schema().fields}
        removed_columns = ["user_id", "tenant_signed", "landlord_signed"]
        for col in removed_columns:
            if col in schema_fields:
                logger.error(f"  ❌ {col} column still exists in schema!")
                return False
        
        logger.info("  ✅ Verified: user_id, tenant_signed, landlord_signed columns removed from schema")
        
        logger.info("  ✅ Migration completed successfully!")
        logger.info(f"  💾 Backup file: {backup_file}")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Migration failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = migrate_walkthroughs()
    sys.exit(0 if success else 1)

