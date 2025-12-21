#!/usr/bin/env python3
"""
Migration script to add holding fee fields to Iceberg leases table.

This script adds:
- include_holding_fee_addendum (bool)
- holding_fee_amount (decimal)
- holding_fee_date (string)

Run: uv run python -m app.scripts.add_holding_fee_fields
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


def add_holding_fee_columns():
    """Add holding fee columns to leases table"""
    logger.info("🔄 Adding holding fee fields to leases table...")
    
    try:
        from pyiceberg.types import DecimalType, StringType, BooleanType
        
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
            ("include_holding_fee_addendum", BooleanType()),
            ("holding_fee_amount", DecimalType(10, 2)),
            ("holding_fee_date", StringType()),
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
            logger.info("  ⏭️  Holding fee columns already exist")
        
        logger.info("  ✅ Holding fee columns added successfully")
        
    except Exception as e:
        logger.error(f"  ❌ Error adding holding fee columns: {e}", exc_info=True)
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
            "include_holding_fee_addendum",
            "holding_fee_amount",
            "holding_fee_date",
        ]
        
        logger.info("  📋 Checking holding fee fields:")
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
    logger.info("🚀 Starting holding fee fields migration...")
    logger.info("=" * 80)
    
    try:
        # Add new columns
        add_holding_fee_columns()
        
        # Verify schema
        verify_schema()
        
        logger.info("=" * 80)
        logger.info("✅ Holding fee migration completed successfully!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Migration failed: {e}")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

