#!/usr/bin/env python3
"""
Migration script to add areas_json column to walkthroughs table.

This stores all areas as JSON in the walkthrough table instead of separate table,
which will make updates MUCH faster (one upsert instead of 16+).
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table
from pyiceberg.types import StringType

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "walkthroughs"


def add_areas_json_column():
    """Add areas_json column to walkthroughs table"""
    logger.info("🔄 Adding areas_json column to walkthroughs table...")
    
    try:
        catalog = get_catalog()
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"  ❌ Table {TABLE_NAME} does not exist!")
            return False
        
        table = load_table(NAMESPACE, TABLE_NAME)
        current_schema = table.schema()
        
        # Check if column already exists
        existing_fields = {field.name for field in current_schema.fields}
        if "areas_json" in existing_fields:
            logger.info("  ⏭️  areas_json column already exists")
            return True
        
        # Add the column
        logger.info("  ➕ Adding areas_json column...")
        with table.update_schema() as update:
            update.add_column("areas_json", StringType(), required=False)
        
        logger.info("  ✅ areas_json column added successfully")
        return True
        
    except Exception as e:
        logger.error(f"  ❌ Error adding areas_json column: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        success = add_areas_json_column()
        if success:
            logger.info("\n✅ Migration complete!")
        else:
            logger.info("\n❌ Migration failed!")
    except Exception as e:
        logger.error(f"\n❌ Migration error: {e}", exc_info=True)
        sys.exit(1)

