#!/usr/bin/env python3
"""
Update Iceberg table schemas for units support.

This script adds the units table and updates the properties table schema
to support multi-unit properties (multi-family/duplex).
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, table_exists
from app.core.logging import setup_logging, get_logger
from pyiceberg.schema import Schema
from pyiceberg.types import (
    StringType, BooleanType, IntegerType, DecimalType, TimestampType, NestedField
)

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)


def create_units_table():
    """Create the units table for multi-family/duplex properties"""
    logger.info("Creating units table...")
    
    try:
        catalog = get_catalog()
        
        # Check if table already exists
        if table_exists(NAMESPACE, "units"):
            logger.info("  ⚠️  Units table already exists, skipping creation")
            return
        
        # Define schema
        schema = Schema(
            NestedField(1, "id", StringType(), required=True),
            NestedField(2, "property_id", StringType(), required=True),
            NestedField(3, "unit_number", StringType(), required=True),
            NestedField(4, "bedrooms", IntegerType(), required=False),
            NestedField(5, "bathrooms", DecimalType(3, 1), required=False),
            NestedField(6, "square_feet", IntegerType(), required=False),
            NestedField(7, "current_monthly_rent", DecimalType(10, 2), required=False),
            NestedField(8, "notes", StringType(), required=False),
            NestedField(9, "created_at", TimestampType(), required=False),
            NestedField(10, "updated_at", TimestampType(), required=False),
            NestedField(11, "is_active", BooleanType(), required=False),
        )
        
        # Create table
        catalog.create_table(
            identifier=f"{NAMESPACE[0]}.units",
            schema=schema
        )
        
        logger.info("  ✅ Units table created successfully!")
        
    except Exception as e:
        logger.error(f"  ❌ Error creating units table: {e}")
        raise


def update_properties_schema():
    """
    Update properties table schema to add has_units and unit_count fields.
    
    Note: PyIceberg supports schema evolution, so we can add columns to existing tables.
    """
    logger.info("Updating properties table schema...")
    
    try:
        catalog = get_catalog()
        
        # Check if properties table exists
        if not table_exists(NAMESPACE, "properties"):
            logger.warning("  ⚠️  Properties table doesn't exist yet")
            return
        
        # Load the table
        table = catalog.load_table(f"{NAMESPACE[0]}.properties")
        
        # Check if fields already exist
        current_schema = table.schema()
        field_names = [field.name for field in current_schema.fields]
        
        if "has_units" in field_names and "unit_count" in field_names:
            logger.info("  ⚠️  Properties schema already has has_units and unit_count fields")
            return
        
        # Add new fields using schema evolution
        with table.update_schema() as update:
            if "has_units" not in field_names:
                update.add_column("has_units", BooleanType(), required=False)
                logger.info("  ✅ Added has_units field")
            
            if "unit_count" not in field_names:
                update.add_column("unit_count", IntegerType(), required=False)
                logger.info("  ✅ Added unit_count field")
        
        logger.info("  ✅ Properties table schema updated successfully!")
        
    except Exception as e:
        logger.error(f"  ❌ Error updating properties schema: {e}")
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Update Iceberg Schemas for Units Support")
    print("=" * 70)
    print()
    
    try:
        # Step 1: Create units table
        print("Step 1: Creating units table...")
        create_units_table()
        print()
        
        # Step 2: Update properties schema
        print("Step 2: Updating properties table schema...")
        update_properties_schema()
        print()
        
        print("=" * 70)
        print("✅ Schema updates completed successfully!")
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Error: {e}")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()

