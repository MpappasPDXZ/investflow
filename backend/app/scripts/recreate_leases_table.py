#!/usr/bin/env python3
"""
Drop and recreate leases_full table with metadata cleanup enabled.

This script:
1. Drops the existing leases_full table
2. Creates a new leases_full table with the same schema
3. Configures metadata cleanup (4 versions)
4. Verifies table creation

WARNING: This will delete all data in the table!
Make sure you've run backup_leases_table.py first!
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, load_table, table_exists
from app.core.logging import setup_logging, get_logger
from app.scripts.create_data import create_leases_schema
import pyarrow as pa

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

def main():
    """Drop and recreate leases table"""
    logger.info("=" * 70)
    logger.info("DROP AND RECREATE LEASES TABLE")
    logger.info("=" * 70)
    logger.info("⚠️  WARNING: This will DELETE all data in the table!")
    logger.info("⚠️  Make sure you've run backup_leases_table.py first!")
    logger.info("")
    
    # Safety check
    response = input("Type 'YES' to continue with drop/recreate: ")
    if response != "YES":
        logger.info("❌ Aborted")
        sys.exit(0)
    
    try:
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, TABLE_NAME)
        
        # Step 1: Check if table exists
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning(f"⚠️  Table {TABLE_NAME} does not exist, will create new table")
        else:
            # Step 2: Drop existing table
            logger.info(f"🗑️  Dropping existing table {TABLE_NAME}...")
            try:
                catalog.drop_table(table_identifier)
                logger.info(f"  ✅ Table {TABLE_NAME} dropped")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not drop table (may not exist): {e}")
        
        # Step 3: Create new table with schema
        logger.info(f"🔨 Creating new table {TABLE_NAME}...")
        schema = create_leases_schema()
        
        try:
            catalog.create_table(
                identifier=table_identifier,
                schema=schema,
                properties={
                    "write.metadata.delete-after-commit.enabled": "true",
                    "write.metadata.previous-versions-max": "4"
                }
            )
            logger.info(f"  ✅ Table {TABLE_NAME} created with metadata cleanup enabled")
        except Exception as e:
            logger.error(f"  ❌ Failed to create table: {e}", exc_info=True)
            raise
        
        # Step 4: Verify table exists and is empty
        logger.info("🔍 Verifying table...")
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"  ❌ Table {TABLE_NAME} does not exist after creation!")
            sys.exit(1)
        
        table = load_table(NAMESPACE, TABLE_NAME)
        current_schema = table.schema()
        logger.info(f"  ✅ Table exists with {len(current_schema.fields)} columns")
        
        # Verify metadata cleanup is configured
        props = table.properties  # properties is a property, not a method
        if props.get("write.metadata.delete-after-commit.enabled") == "true":
            logger.info(f"  ✅ Metadata cleanup enabled")
        else:
            logger.warning(f"  ⚠️  Metadata cleanup not enabled")
        
        if props.get("write.metadata.previous-versions-max") == "4":
            logger.info(f"  ✅ Version retention set to 4")
        else:
            logger.warning(f"  ⚠️  Version retention not set correctly")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ TABLE RECREATED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info(f"  Table: {TABLE_NAME}")
        logger.info(f"  Schema: {len(current_schema.fields)} columns")
        logger.info(f"  Metadata cleanup: Enabled (4 versions)")
        logger.info("")
        logger.info("Next step: Run restore_leases_table.py to restore data")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Failed to recreate table: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

