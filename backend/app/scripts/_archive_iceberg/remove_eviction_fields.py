#!/usr/bin/env python3
"""
Remove eviction fields from tenants table.
These fields were added but are not being used.
"""

import logging
from app.core.iceberg import get_catalog

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

NAMESPACE = ("investflow",)

def remove_eviction_fields():
    """Remove has_evictions and eviction_details fields from tenants table."""
    logger.info("🔄 Removing eviction fields from tenants table...")
    
    try:
        catalog = get_catalog()
        table = catalog.load_table(f"{NAMESPACE[0]}.tenants")
        
        current_schema = table.schema()
        fields_to_remove = [
            "has_evictions",
            "eviction_details"
        ]
        
        # Check and remove each field
        field_names = [field.name for field in current_schema.fields]
        for field_name in fields_to_remove:
            if field_name in field_names:
                table.update_schema().delete_column(field_name).commit()
                logger.info(f"  ➖ Removed {field_name}")
            else:
                logger.info(f"  ⏭️  {field_name} not found (already removed)")
        
        logger.info("✅ Eviction fields removed successfully!")
        
    except Exception as e:
        logger.error(f"  ❌ Error removing eviction fields: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    remove_eviction_fields()

