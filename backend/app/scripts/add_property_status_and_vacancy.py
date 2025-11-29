"""
Add property_status and vacancy_rate columns to properties table
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, table_exists
from app.core.logging import get_logger
from pyiceberg.types import StringType, DecimalType, DateType

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

logger = get_logger(__name__)


def add_property_status_and_vacancy():
    """
    Add property_status, vacancy_rate, purchase_date and other fields to properties table.
    """
    logger.info("Adding property_status, vacancy_rate, purchase_date, etc. to properties table...")
    
    try:
        catalog = get_catalog()
        
        # Check if properties table exists
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.warning("  ⚠️  Properties table doesn't exist yet")
            return
        
        # Load the table
        table = catalog.load_table(f"{NAMESPACE[0]}.{TABLE_NAME}")
        
        # Check if fields already exist
        current_schema = table.schema()
        field_names = [field.name for field in current_schema.fields]
        
        logger.info(f"  Current schema fields: {field_names}")
        
        # Add new fields using schema evolution
        with table.update_schema() as update:
            if "property_status" not in field_names:
                update.add_column("property_status", StringType(), required=False)
                logger.info("  ✅ Added property_status field")
            else:
                logger.info("  ⚠️  property_status field already exists")
            
            if "vacancy_rate" not in field_names:
                update.add_column("vacancy_rate", DecimalType(5, 4), required=False)
                logger.info("  ✅ Added vacancy_rate field")
            else:
                logger.info("  ⚠️  vacancy_rate field already exists")
            
            if "down_payment" not in field_names:
                update.add_column("down_payment", DecimalType(12, 2), required=False)
                logger.info("  ✅ Added down_payment field")
            else:
                logger.info("  ⚠️  down_payment field already exists")
            
            if "current_market_value" not in field_names:
                update.add_column("current_market_value", DecimalType(12, 2), required=False)
                logger.info("  ✅ Added current_market_value field")
            else:
                logger.info("  ⚠️  current_market_value field already exists")
            
            if "purchase_date" not in field_names:
                update.add_column("purchase_date", DateType(), required=False)
                logger.info("  ✅ Added purchase_date field")
            else:
                logger.info("  ⚠️  purchase_date field already exists")
        
        logger.info("  ✅ Properties table schema updated successfully!")
        
        # Display updated schema
        table = catalog.load_table(f"{NAMESPACE[0]}.{TABLE_NAME}")
        updated_schema = table.schema()
        updated_field_names = [field.name for field in updated_schema.fields]
        logger.info(f"  Updated schema fields: {updated_field_names}")
        
    except Exception as e:
        logger.error(f"  ❌ Error updating properties schema: {e}")
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Adding property_status, vacancy_rate, purchase_date to properties table")
    print("=" * 70)
    
    try:
        add_property_status_and_vacancy()
        print("\n✅ Schema update completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

