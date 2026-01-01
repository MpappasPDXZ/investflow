#!/usr/bin/env python3
"""
Quick script to verify lease schema fields are present
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases"

def verify_schema():
    """Verify the required fields are in the schema"""
    logger.info("🔍 Verifying leases table schema...")
    
    try:
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("  ❌ Leases table doesn't exist!")
            return False
        
        catalog = get_catalog()
        table = catalog.load_table((*NAMESPACE, TABLE_NAME))
        current_schema = table.schema()
        
        existing_fields = {field.name for field in current_schema.fields}
        
        # Fields we need to verify
        required_fields = [
            "garage_back_door_keys",
            "utilities_provided_by_owner_city",
            "has_garage_door_opener",
            "garage_door_opener_fee"
        ]
        
        logger.info(f"\n📋 Checking for required fields:")
        all_present = True
        for field_name in required_fields:
            if field_name in existing_fields:
                # Get the field type
                field = next(f for f in current_schema.fields if f.name == field_name)
                logger.info(f"  ✅ {field_name}: {field.field_type}")
            else:
                logger.error(f"  ❌ {field_name}: MISSING!")
                all_present = False
        
        if all_present:
            logger.info("\n✅ All required fields are present in the schema!")
        else:
            logger.error("\n❌ Some required fields are missing!")
        
        return all_present
        
    except Exception as e:
        logger.error(f"  ❌ Error verifying schema: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)


