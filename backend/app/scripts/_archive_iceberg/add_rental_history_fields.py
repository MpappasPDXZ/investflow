#!/usr/bin/env python3
"""Add rental history fields to tenants table"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog
from app.core.logging import setup_logging, get_logger
from pyiceberg.types import StringType, BooleanType

setup_logging()
logger = get_logger(__name__)

def main():
    logger.info("Adding rental history fields to tenants table...")
    
    try:
        catalog = get_catalog()
        table = catalog.load_table(("investflow", "tenants"))
        
        # Check existing schema
        existing_fields = {field.name for field in table.schema().fields}
        
        with table.update_schema() as update:
            if "has_evictions" not in existing_fields:
                update.add_column("has_evictions", BooleanType(), required=False)
                logger.info("  ➕ Added has_evictions")
            
            if "eviction_details" not in existing_fields:
                update.add_column("eviction_details", StringType(), required=False)
                logger.info("  ➕ Added eviction_details")
            
            if "previous_landlord_name" not in existing_fields:
                update.add_column("previous_landlord_name", StringType(), required=False)
                logger.info("  ➕ Added previous_landlord_name")
            
            if "previous_landlord_phone" not in existing_fields:
                update.add_column("previous_landlord_phone", StringType(), required=False)
                logger.info("  ➕ Added previous_landlord_phone")
            
            if "previous_landlord_contacted" not in existing_fields:
                update.add_column("previous_landlord_contacted", BooleanType(), required=False)
                logger.info("  ➕ Added previous_landlord_contacted")
            
            if "previous_landlord_reference" not in existing_fields:
                update.add_column("previous_landlord_reference", StringType(), required=False)
                logger.info("  ➕ Added previous_landlord_reference")
        
        logger.info("✅ Rental history fields added successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

