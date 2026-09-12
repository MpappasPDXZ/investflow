#!/usr/bin/env python3
"""
Migration script to add new fields to leases table:
1. garage_back_door_keys - for 3rd door (garage back door)
2. utilities_provided_by_owner_city - text field for utilities provided by owner or city
3. has_garage_door_opener - boolean for garage door opener
4. garage_door_opener_fee - fee for garage door opener replacement

Run this script once to migrate the schema.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)


def add_lease_utilities_doors_columns():
    """Add new columns to leases table for utilities, doors, and garage door opener"""
    logger.info("🔄 Migrating leases table with utilities, doors, and garage door opener fields...")
    
    try:
        from pyiceberg.types import IntegerType, DecimalType, StringType, BooleanType
        
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, "leases")
        
        if not table_exists(NAMESPACE, "leases"):
            logger.warning("  ⚠️  Leases table doesn't exist, skipping")
            return
        
        # Load table
        table = catalog.load_table(table_identifier)
        current_schema = table.schema()
        
        # Check which fields are missing
        existing_fields = {field.name for field in current_schema.fields}
        
        # Define new fields to add
        new_fields = [
            # Garage back door (3rd door)
            ("garage_back_door_keys", IntegerType()),
            
            # Utilities provided by owner or city (text field)
            ("utilities_provided_by_owner_city", StringType()),
            
            # Garage door opener
            ("has_garage_door_opener", BooleanType()),
            ("garage_door_opener_fee", DecimalType(10, 2)),
        ]
        
        updates_needed = []
        
        for field_name, field_type in new_fields:
            if field_name not in existing_fields:
                updates_needed.append((field_name, field_type))
                logger.info(f"  ➕ Will add: {field_name}")
            else:
                logger.info(f"  ✓ Already exists: {field_name}")
        
        # Apply schema updates
        if updates_needed:
            with table.update_schema() as update:
                for field_name, field_type in updates_needed:
                    update.add_column(field_name, field_type, required=False)
            
            logger.info(f"  ✅ Added {len(updates_needed)} column(s) to leases table")
        else:
            logger.info("  ✅ All fields already exist, no migration needed")
        
    except Exception as e:
        logger.error(f"  ❌ Error migrating leases table: {e}", exc_info=True)
        raise


def main():
    """Run the migration"""
    logger.info("=" * 60)
    logger.info("Starting lease utilities, doors, and garage door opener migration")
    logger.info("=" * 60)
    
    try:
        add_lease_utilities_doors_columns()
        logger.info("=" * 60)
        logger.info("✅ Migration completed successfully")
        logger.info("=" * 60)
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

