"""
Test script to create an Iceberg table and append records
Uses Lakekeeper API for table creation and PyIceberg for writing/reading data
"""
import asyncio
import sys
import os
import pandas as pd
import pyarrow as pa

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../backend'))
from app.services.lakekeeper_service import get_lakekeeper_service
from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.config import settings

# Configuration
NAMESPACE = "test_namespace"
TABLE_NAME = "test_table"
WAREHOUSE_NAME = settings.LAKEKEEPER__WAREHOUSE_NAME


async def main():
    """Main test function"""
    print("=" * 70)
    print("Iceberg Table Creation and Data Append Test (PyIceberg)")
    print("=" * 70)
    
    # Get services
    lakekeeper = get_lakekeeper_service()
    pyiceberg = get_pyiceberg_service()
    
    # Step 1: Get warehouse ID
    print(f"\n1. Getting warehouse '{WAREHOUSE_NAME}'...")
    warehouse_id = await lakekeeper.get_warehouse_id(WAREHOUSE_NAME)
    if not warehouse_id:
        print(f"❌ Warehouse '{WAREHOUSE_NAME}' not found!")
        return
    print(f"✅ Warehouse ID: {warehouse_id}")
    
    # Step 2: Create namespace
    print(f"\n2. Creating namespace '{NAMESPACE}'...")
    namespace_list = [NAMESPACE]
    try:
        await lakekeeper.create_namespace(warehouse_id, namespace_list)
        print(f"✅ Namespace '{NAMESPACE}' created")
    except Exception as e:
        if "409" in str(e) or "already exists" in str(e).lower():
            print(f"⚠️  Namespace '{NAMESPACE}' already exists (continuing...)")
        else:
            print(f"❌ Failed to create namespace: {e}")
            return
    
    # Step 3: Define table schema
    print(f"\n3. Defining table schema...")
    table_schema = {
        "type": "struct",
        "schema-id": 0,
        "fields": [
            {"id": 1, "name": "id", "type": "int", "required": True},
            {"id": 2, "name": "name", "type": "string", "required": False},
            {"id": 3, "name": "value", "type": "double", "required": False},
            {"id": 4, "name": "created_at", "type": "timestamp", "required": False}
        ]
    }
    print("✅ Schema defined with fields: id, name, value, created_at")
    
    # Step 4: Create table
    print(f"\n4. Creating table '{NAMESPACE}.{TABLE_NAME}'...")
    try:
        table_info = await lakekeeper.create_table(
            warehouse_id,
            namespace_list,
            TABLE_NAME,
            table_schema
        )
        metadata_location = table_info.get("metadata-location")
        print(f"✅ Table created successfully!")
        print(f"   Metadata location: {metadata_location}")
    except Exception as e:
        if "409" in str(e) or "already exists" in str(e).lower():
            print(f"⚠️  Table already exists, getting metadata...")
            table_info = await lakekeeper.get_table(warehouse_id, namespace_list, TABLE_NAME)
            metadata_location = table_info.get("metadata-location")
        else:
            print(f"❌ Failed to create table: {e}")
            return
    
    # Step 5: Write data using PyIceberg
    print(f"\n5. Writing data to table using PyIceberg...")
    try:
        # Create sample data
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "value": [10.5, 20.3, 30.7, 40.2, 50.9],
            "created_at": [pd.Timestamp.now()] * 5
        })
        
        namespace_tuple = (NAMESPACE,)
        pyiceberg.append_data(namespace_tuple, TABLE_NAME, df)
        print(f"✅ Successfully inserted {len(df)} records using PyIceberg!")
        
    except Exception as e:
        print(f"❌ Failed to write data: {e}")
        import traceback
        traceback.print_exc()
        # Continue anyway to test reading
    
    # Step 6: Read data using PyIceberg
    print(f"\n6. Reading data from table using PyIceberg...")
    try:
        namespace_tuple = (NAMESPACE,)
        result_df = pyiceberg.read_table(namespace_tuple, TABLE_NAME)
        
        print(f"✅ Successfully read {len(result_df)} records:")
        print(result_df.to_string(index=False))
            
    except Exception as e:
        print(f"❌ Failed to read data: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 7: Append more records using PyIceberg
    print(f"\n7. Appending additional records using PyIceberg...")
    try:
        df2 = pd.DataFrame({
            "id": [6, 7, 8],
            "name": ["Frank", "Grace", "Henry"],
            "value": [60.1, 70.5, 80.3],
            "created_at": [pd.Timestamp.now()] * 3
        })
        
        namespace_tuple = (NAMESPACE,)
        pyiceberg.append_data(namespace_tuple, TABLE_NAME, df2)
        print(f"✅ Successfully appended {len(df2)} more records!")
        
        # Read again to verify
        result_df = pyiceberg.read_table(namespace_tuple, TABLE_NAME)
        print(f"\n✅ Total records in table: {len(result_df)}")
        print(result_df.to_string(index=False))
        
    except Exception as e:
        print(f"❌ Failed to append additional records: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
