#!/usr/bin/env python3
"""
Migrate leases_full table to cleaned schema.

This script:
1. Backs up 4 active leases with cleaned columns
2. Drops the existing leases_full table
3. Creates new leases_full table with cleaned schema (only LaTeX-used + System columns)
4. Restores the 4 active leases
5. Sets metadata cleanup properties
"""
import sys
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, load_table, append_data
from app.scripts.create_data import create_leases_schema
from app.scripts.backup_leases_4_active import main as backup_leases
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

def drop_table():
    """Drop the existing leases_full table"""
    logger.info("🗑️  Dropping existing leases_full table...")
    try:
        catalog = get_catalog()
        catalog.drop_table(identifier=(*NAMESPACE, TABLE_NAME))
        logger.info("  ✅ Table dropped successfully")
    except Exception as e:
        # Table might not exist, which is fine
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            logger.info("  ℹ️  Table does not exist (already dropped or never created)")
        else:
            logger.error(f"  ❌ Error dropping table: {e}")
            raise

def create_table():
    """Create new leases_full table with cleaned schema"""
    logger.info("")
    logger.info("🏗️  Creating new leases_full table with cleaned schema...")
    
    schema = create_leases_schema()
    catalog = get_catalog()
    
    # Create table
    catalog.create_table(
        identifier=(*NAMESPACE, TABLE_NAME),
        schema=schema,
        properties={
            "write.metadata.delete-after-commit.enabled": "true",
            "write.metadata.previous-versions-max": "4"
        }
    )
    
    logger.info(f"  ✅ Table created with {len(schema)} columns")
    
    # Verify table properties
    table = load_table(NAMESPACE, TABLE_NAME)
    props = table.properties
    logger.info(f"  📊 Metadata cleanup: {props.get('write.metadata.delete-after-commit.enabled', 'not set')}")
    logger.info(f"  📊 Version retention: {props.get('write.metadata.previous-versions-max', 'not set')}")

def restore_data(timestamp: str):
    """Restore data from backup"""
    logger.info("")
    logger.info("📥 Restoring data from backup...")
    
    # Load backup file
    backup_file = f"/tmp/leases_4_active_{timestamp}.parquet"
    logger.info(f"  📖 Loading backup from {backup_file}...")
    
    df = pd.read_parquet(backup_file)
    logger.info(f"  ✅ Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Get new schema to check for missing columns
    table = load_table(NAMESPACE, TABLE_NAME)
    new_schema = table.schema()
    new_columns = {field.name for field in new_schema.fields}
    
    # Check for columns in backup that aren't in new schema
    backup_columns = set(df.columns)
    missing_in_schema = backup_columns - new_columns
    if missing_in_schema:
        logger.warning(f"  ⚠️  Dropping {len(missing_in_schema)} columns from backup that aren't in new schema: {sorted(missing_in_schema)}")
        df = df.drop(columns=list(missing_in_schema))
    
    # Check for columns in new schema that aren't in backup
    missing_in_backup = new_columns - backup_columns
    if missing_in_backup:
        logger.info(f"  ℹ️  New schema has {len(missing_in_backup)} columns not in backup (will be null): {sorted(missing_in_backup)}")
    
    # Append data
    logger.info("")
    logger.info("  💾 Appending data to table...")
    append_data(NAMESPACE, TABLE_NAME, df)
    logger.info(f"  ✅ Restored {len(df)} rows")

def main():
    """Run full migration"""
    logger.info("=" * 70)
    logger.info("LEASE SCHEMA MIGRATION")
    logger.info("=" * 70)
    logger.info("")
    logger.info("This will:")
    logger.info("  1. Backup 4 active leases")
    logger.info("  2. Drop existing leases_full table")
    logger.info("  3. Create new table with cleaned schema")
    logger.info("  4. Restore the 4 active leases")
    logger.info("")
    
    response = input("⚠️  Type 'YES' to proceed: ")
    if response != "YES":
        logger.info("❌ Migration cancelled")
        return
    
    try:
        # Step 1: Backup
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 1: BACKUP")
        logger.info("=" * 70)
        timestamp, local_file = backup_leases()
        
        # Step 2: Drop table
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 2: DROP TABLE")
        logger.info("=" * 70)
        drop_table()
        
        # Step 3: Create table
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 3: CREATE TABLE")
        logger.info("=" * 70)
        create_table()
        
        # Step 4: Restore data
        logger.info("")
        logger.info("=" * 70)
        logger.info("STEP 4: RESTORE DATA")
        logger.info("=" * 70)
        restore_data(timestamp)
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ MIGRATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"  Backup timestamp: {timestamp}")
        logger.info(f"  Backup file: {local_file}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ MIGRATION FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("⚠️  You may need to restore from backup manually")
        raise

if __name__ == "__main__":
    main()

