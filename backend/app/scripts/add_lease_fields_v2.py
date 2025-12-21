#!/usr/bin/env python3
"""
Migration script to add new lease form fields to Iceberg.

This script adds:
- lease_duration_months (int)
- show_prorated_rent (bool)
- prorated_rent_amount (decimal)
- prorated_rent_language (string)
- num_children (int)
- pet_fee (decimal)
- include_keys_clause (bool)
- has_front_door (bool)
- has_back_door (bool)

Run: uv run python -m app.scripts.add_lease_fields_v2
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


def add_new_lease_columns():
    """Add new columns to leases table for form fields"""
    logger.info("🔄 Migrating leases table with new form fields...")
    
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
            # Lease Duration
            ("lease_duration_months", IntegerType()),
            
            # Prorated Rent
            ("show_prorated_rent", BooleanType()),
            ("prorated_rent_amount", DecimalType(10, 2)),
            ("prorated_rent_language", StringType()),
            
            # Occupancy
            ("num_children", IntegerType()),
            
            # Pet Fee
            ("pet_fee", DecimalType(10, 2)),
            
            # Pets as JSON array
            ("pets", StringType()),
            
            # Parking
            ("garage_spaces", IntegerType()),
            ("offstreet_parking_spots", IntegerType()),
            
            # Keys Clause
            ("include_keys_clause", BooleanType()),
            ("has_front_door", BooleanType()),
            ("has_back_door", BooleanType()),
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
            logger.info("  ⏭️  Leases table schema already up to date")
        
        logger.info("  ✅ Leases table migrated successfully")
        
    except Exception as e:
        logger.error(f"  ❌ Error migrating leases table: {e}", exc_info=True)
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
        
        logger.info("  📋 Current leases schema fields:")
        for field in current_schema.fields:
            logger.info(f"     - {field.name}: {field.field_type}")
        
        # Check for our new fields
        existing_fields = {field.name for field in current_schema.fields}
        expected_fields = [
            "lease_duration_months",
            "show_prorated_rent",
            "prorated_rent_amount",
            "prorated_rent_language",
            "num_children",
            "pet_fee",
            "pets",
            "garage_spaces",
            "offstreet_parking_spots",
            "include_keys_clause",
            "has_front_door",
            "has_back_door",
        ]
        
        missing = [f for f in expected_fields if f not in existing_fields]
        if missing:
            logger.warning(f"  ⚠️  Missing fields: {missing}")
        else:
            logger.info("  ✅ All new fields present in schema")
        
    except Exception as e:
        logger.error(f"  ❌ Error verifying schema: {e}", exc_info=True)
        raise


def main():
    """Run migration"""
    logger.info("=" * 80)
    logger.info("🚀 Starting lease form fields migration...")
    logger.info("=" * 80)
    
    try:
        # Add new columns
        add_new_lease_columns()
        
        # Verify schema
        verify_schema()
        
        logger.info("=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ Migration failed: {e}")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

