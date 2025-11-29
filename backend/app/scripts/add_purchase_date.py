"""
Add purchase_date column to properties table
"""
import sys
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, table_exists
from app.core.logging import get_logger
from pyiceberg.types import TimestampType

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

logger = get_logger(__name__)


def add_purchase_date():
    """Add purchase_date field to properties table."""
    logger.info("Adding purchase_date to properties table...")
    
    try:
        catalog = get_catalog()
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning("  ⚠️  Properties table doesn't exist yet")
            return
        
        table = catalog.load_table(f"{NAMESPACE[0]}.{TABLE_NAME}")
        current_schema = table.schema()
        field_names = [field.name for field in current_schema.fields]
        
        logger.info(f"  Current schema fields: {field_names}")
        
        with table.update_schema() as update:
            if "purchase_date" not in field_names:
                update.add_column("purchase_date", TimestampType(), required=False)
                logger.info("  ✅ Added purchase_date field")
            else:
                logger.info("  ⚠️  purchase_date field already exists")
        
        logger.info("  ✅ Properties table schema updated successfully!")
        
    except Exception as e:
        logger.error(f"  ❌ Error updating properties schema: {e}")
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Adding purchase_date to properties table")
    print("=" * 70)
    
    try:
        add_purchase_date()
        print("\n✅ Schema update completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

