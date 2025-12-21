#!/usr/bin/env python3
"""
Migration script to add lawn/snow maintenance responsibility fields to Iceberg leases table.

This script adds:
- tenant_lawn_mowing (bool) - Tenant is responsible for lawn mowing
- tenant_snow_removal (bool) - Tenant is responsible for snow removal
- tenant_lawn_care (bool) - Tenant is responsible for lawn care (sprinkler, seeding, etc.)

Run: uv run python -m app.scripts.add_maintenance_fields
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


def add_maintenance_columns():
    """Add lawn/snow maintenance responsibility columns to leases table"""
    logger.info("🔄 Adding maintenance responsibility fields to leases table...")
    
    try:
        from pyiceberg.types import BooleanType
        
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
        # Default: tenant handles mowing and snow, landlord handles lawn care
        new_fields = [
            ("tenant_lawn_mowing", BooleanType()),      # Tenant mows the lawn
            ("tenant_snow_removal", BooleanType()),     # Tenant removes snow
            ("tenant_lawn_care", BooleanType()),        # Tenant handles lawn care (sprinkler, seeding, etc.)
        ]
        
        updates_needed = []
        
        for field_name, field_type in new_fields:
            if field_name not in existing_fields:
                updates_needed.append((field_name, field_type))
                logger.info(f"  ➕ Adding {field_name} column")
            else:
                logger.info(f"  ⏭️  {field_name} column already exists")
        
        # Apply schema updates
        if updates_needed:
            with table.update_schema() as update:
                for field_name, field_type in updates_needed:
                    update.add_column(field_name, field_type, required=False)
            
            logger.info(f"  ✅ Added {len(updates_needed)} column(s) to leases table")
        else:
            logger.info("  ⏭️  Maintenance columns already exist")
        
        logger.info("  ✅ Maintenance columns added successfully")
        
    except Exception as e:
        logger.error(f"  ❌ Error adding maintenance columns: {e}", exc_info=True)
        raise


def verify_schema():
    """Verify the schema after migration"""
    logger.info("🔍 Verifying leases table schema...")
    
    try:
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, "leases")
        
        if not table_exists(NAMESPACE, "leases"):
            logger.warning("  ⚠️  Leases table doesn't exist")
            return
        
        table = catalog.load_table(table_identifier)
        current_schema = table.schema()
        
        # Check for our new fields
        existing_fields = {field.name for field in current_schema.fields}
        expected_fields = [
            "tenant_lawn_mowing",
            "tenant_snow_removal",
            "tenant_lawn_care",
        ]
        
        logger.info("  📋 Checking maintenance responsibility fields:")
        for field_name in expected_fields:
            if field_name in existing_fields:
                logger.info(f"     ✅ {field_name}")
            else:
                logger.warning(f"     ❌ {field_name} MISSING")
        
    except Exception as e:
        logger.error(f"  ❌ Error verifying schema: {e}", exc_info=True)
        raise


def main():
    """Run migration"""
    logger.info("=" * 80)
    logger.info("🚀 Starting maintenance responsibility fields migration...")
    logger.info("=" * 80)
    
    try:
        # Add new columns
        add_maintenance_columns()
        
        # Verify schema
        verify_schema()
        
        logger.info("=" * 80)
        logger.info("✅ Maintenance fields migration completed successfully!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Migration failed: {e}")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

