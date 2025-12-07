#!/usr/bin/env python3
"""
Delete all tables in the investflow namespace.
"""
import sys
import asyncio
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)


async def main():
    """Delete all tables"""
    print("=" * 70)
    print("Delete All Tables in investflow Namespace")
    print("=" * 70)
    print()
    
    pyiceberg = get_pyiceberg_service()
    catalog = pyiceberg.get_catalog()
    
    # List all tables
    try:
        tables = catalog.list_tables(NAMESPACE)
        table_names = [t[-1] for t in tables]
        
        if not table_names:
            print("✅ No tables found in investflow namespace")
            return
        
        print(f"Found {len(table_names)} tables:")
        for table_name in table_names:
            print(f"  - {table_name}")
        
        print("\nDeleting tables...")
        for table_name in table_names:
            try:
                pyiceberg.drop_table(NAMESPACE, table_name)
                print(f"  ✅ Deleted: {table_name}")
            except Exception as e:
                print(f"  ❌ Failed to delete {table_name}: {e}")
        
        print("\n" + "=" * 70)
        print("✅ All tables deleted")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())







