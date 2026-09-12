#!/usr/bin/env python3
"""
Script to check columns in walkthroughs table
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
WALKTHROUGHS_TABLE = "walkthroughs"


def check_columns():
    """Check columns in walkthroughs table"""
    try:
        catalog = get_catalog()
        
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            logger.error(f"❌ Table {WALKTHROUGHS_TABLE} does not exist!")
            return False
        
        table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
        schema = table.schema()
        
        print("\n" + "=" * 80)
        print(f"COLUMNS IN '{WALKTHROUGHS_TABLE}' TABLE")
        print("=" * 80)
        print()
        
        field_names = {field.name for field in schema.fields}
        
        for i, field in enumerate(schema.fields, 1):
            nullable = "NULL" if not field.required else "NOT NULL"
            field_type = str(field.field_type) if hasattr(field, 'field_type') else str(type(field))
            
            # Highlight overall_condition if it exists
            marker = " ⚠️  [TO REMOVE]" if field.name == "overall_condition" else ""
            print(f"{i:2d}. {field.name:35s} | {field_type:20s} | {nullable:10s}{marker}")
        
        print()
        print("=" * 80)
        print(f"TOTAL COLUMNS: {len(schema.fields)}")
        print("=" * 80)
        
        # Check specifically for overall_condition
        if "overall_condition" in field_names:
            print("\n⚠️  WARNING: 'overall_condition' column EXISTS and needs to be removed")
        else:
            print("\n✅ 'overall_condition' column does NOT exist")
        print()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking columns: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = check_columns()
    sys.exit(0 if success else 1)

