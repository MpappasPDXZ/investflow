#!/usr/bin/env python3
"""
Migration script to add new fields to existing Iceberg tables.

This script adds:
1. cash_invested field to properties table
2. pet_deposit_total and pet_description fields to leases table
3. Creates new walkthroughs and walkthrough_areas tables

Run this script once to migrate the schema.
"""
import sys
from pathlib import Path
from datetime import date
import pandas as pd
import pyarrow as pa

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, read_table

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)


def create_walkthroughs_schema() -> pa.Schema:
    """Create PyArrow schema for walkthroughs table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("walkthrough_type", pa.string(), nullable=False),  # move_in, move_out, periodic, maintenance
        pa.field("walkthrough_date", pa.date32(), nullable=False),
        pa.field("status", pa.string(), nullable=False),  # draft, pending_signature, completed
        pa.field("inspector_name", pa.string(), nullable=True),
        pa.field("tenant_name", pa.string(), nullable=True),
        pa.field("tenant_signed", pa.bool_(), nullable=False),
        pa.field("tenant_signature_date", pa.date32(), nullable=True),
        pa.field("landlord_signed", pa.bool_(), nullable=False),
        pa.field("landlord_signature_date", pa.date32(), nullable=True),
        pa.field("overall_condition", pa.string(), nullable=False),  # excellent, good, fair, poor
        pa.field("notes", pa.string(), nullable=True),
        pa.field("generated_pdf_blob_name", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def create_walkthrough_areas_schema() -> pa.Schema:
    """Create PyArrow schema for walkthrough_areas table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("walkthrough_id", pa.string(), nullable=False),
        pa.field("floor", pa.string(), nullable=False),  # "Basement", "Floor 1", etc.
        pa.field("area_name", pa.string(), nullable=False),  # "Living Room", "Kitchen", etc.
        pa.field("area_order", pa.int32(), nullable=False),
        pa.field("condition", pa.string(), nullable=False),  # excellent, good, fair, poor
        pa.field("notes", pa.string(), nullable=True),
        pa.field("issues", pa.string(), nullable=True),  # JSON array
        pa.field("photos", pa.string(), nullable=True),  # JSON array
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def add_columns_to_properties():
    """Add cash_invested column to properties table"""
    logger.info("🔄 Migrating properties table...")
    
    try:
        from pyiceberg.schema import Schema
        from pyiceberg.types import NestedField, DecimalType, StringType, TimestampType, BooleanType
        
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, "properties")
        
        if not table_exists(NAMESPACE, "properties"):
            logger.warning("  ⚠️  Properties table doesn't exist, skipping")
            return
        
        # Load table
        table = catalog.load_table(table_identifier)
        current_schema = table.schema()
        
        # Check which fields are missing and need to be added
        existing_fields = {field.name for field in current_schema.fields}
        
        updates_needed = []
        
        if "cash_invested" not in existing_fields:
            updates_needed.append(("cash_invested", DecimalType(12, 2)))
            logger.info("  ➕ Adding cash_invested column")
        
        if "down_payment" not in existing_fields:
            updates_needed.append(("down_payment", DecimalType(12, 2)))
            logger.info("  ➕ Adding down_payment column")
        
        if "purchase_date" not in existing_fields:
            updates_needed.append(("purchase_date", TimestampType()))
            logger.info("  ➕ Adding purchase_date column")
        
        if "current_market_value" not in existing_fields:
            updates_needed.append(("current_market_value", DecimalType(12, 2)))
            logger.info("  ➕ Adding current_market_value column")
        
        if "property_status" not in existing_fields:
            updates_needed.append(("property_status", StringType()))
            logger.info("  ➕ Adding property_status column")
        
        if "vacancy_rate" not in existing_fields:
            updates_needed.append(("vacancy_rate", DecimalType(5, 4)))
            logger.info("  ➕ Adding vacancy_rate column")
        
        # Apply schema updates
        if updates_needed:
            with table.update_schema() as update:
                for field_name, field_type in updates_needed:
                    update.add_column(field_name, field_type, required=False)
            
            logger.info(f"  ✅ Added {len(updates_needed)} column(s) to properties table")
        else:
            logger.info("  ⏭️  Properties table schema already up to date")
        
        logger.info("  ✅ Properties table migrated successfully")
        
    except Exception as e:
        logger.error(f"  ❌ Error migrating properties table: {e}", exc_info=True)
        raise


def add_columns_to_leases():
    """Add pet_deposit_total and pet_description columns to leases table"""
    logger.info("🔄 Migrating leases table...")
    
    try:
        from pyiceberg.types import NestedField, DecimalType, StringType
        
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
        
        updates_needed = []
        
        if "pet_deposit_total" not in existing_fields:
            updates_needed.append(("pet_deposit_total", DecimalType(10, 2)))
            logger.info("  ➕ Adding pet_deposit_total column")
        
        if "pet_description" not in existing_fields:
            updates_needed.append(("pet_description", StringType()))
            logger.info("  ➕ Adding pet_description column")
        
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


def create_walkthrough_tables():
    """Create new walkthrough tables"""
    logger.info("🔄 Creating walkthrough tables...")
    
    try:
        catalog = get_catalog()
        
        # Create walkthroughs table
        if not table_exists(NAMESPACE, "walkthroughs"):
            logger.info("  ➕ Creating walkthroughs table")
            walkthroughs_identifier = (*NAMESPACE, "walkthroughs")
            schema = create_walkthroughs_schema()
            catalog.create_table(
                identifier=walkthroughs_identifier,
                schema=schema
            )
            logger.info("  ✅ Walkthroughs table created")
        else:
            logger.info("  ⏭️  Walkthroughs table already exists")
        
        # Create walkthrough_areas table
        if not table_exists(NAMESPACE, "walkthrough_areas"):
            logger.info("  ➕ Creating walkthrough_areas table")
            areas_identifier = (*NAMESPACE, "walkthrough_areas")
            schema = create_walkthrough_areas_schema()
            catalog.create_table(
                identifier=areas_identifier,
                schema=schema
            )
            logger.info("  ✅ Walkthrough_areas table created")
        else:
            logger.info("  ⏭️  Walkthrough_areas table already exists")
        
    except Exception as e:
        logger.error(f"  ❌ Error creating walkthrough tables: {e}", exc_info=True)
        raise


def main():
    """Run all migrations"""
    logger.info("=" * 80)
    logger.info("🚀 Starting schema migration...")
    logger.info("=" * 80)
    
    try:
        # Step 1: Add columns to properties
        add_columns_to_properties()
        
        # Step 2: Add columns to leases
        add_columns_to_leases()
        
        # Step 3: Create walkthrough tables
        create_walkthrough_tables()
        
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

