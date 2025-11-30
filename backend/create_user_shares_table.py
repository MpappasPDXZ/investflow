#!/usr/bin/env python3
"""
Create only the user_shares Iceberg table
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)


def create_user_shares_schema() -> pa.Schema:
    """Create PyArrow schema for user_shares table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("shared_email", pa.string(), nullable=False),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def main():
    print("🚀 Creating user_shares Iceberg table...")
    
    try:
        catalog = get_catalog()
        table_identifier = f"{'.'.join(NAMESPACE)}.user_shares"
        
        # Check if table already exists
        try:
            existing_table = catalog.load_table(table_identifier)
            print(f"✅ Table {table_identifier} already exists")
            print(f"   Schema: {existing_table.schema()}")
            return
        except Exception:
            print(f"📝 Table {table_identifier} does not exist, creating...")
        
        # Create the table
        schema = create_user_shares_schema()
        catalog.create_table(table_identifier, schema=schema)
        
        print(f"✅ Successfully created table: {table_identifier}")
        print(f"   Schema: {schema}")
        
        # Verify we can read from it
        table = catalog.load_table(table_identifier)
        print(f"✅ Verified table can be loaded")
        print(f"\n💡 You can now use the share properties feature!")
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

