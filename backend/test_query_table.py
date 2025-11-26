import sys
import os
import logging

# Add the current directory to sys.path to allow importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.duckdb_client import duckdb_client

# Configuration
# You might need to set these if they aren't picked up from the environment
# os.environ["AZURE_STORAGE_ACCOUNT_NAME"] = "..."
# os.environ["AZURE_STORAGE_ACCOUNT_KEY"] = "..."

def query_test():
    print("Initializing DuckDB...")
    conn = duckdb_client.get_connection()
    
    # The Iceberg table location from the previous test output
    # We need the full "metadata.json" location or the table root path
    # Lakekeeper returns the warehouse location + table path
    
    # Construct the Iceberg table path for DuckDB
    # Format: iceberg_scan('abfss://<container>@<account>.dfs.core.windows.net/<path>', allow_moved_paths=true)
    # Or if using REST catalog integration in DuckDB (newer feature), but simple scan is easier.
    
    # However, DuckDB's iceberg extension usually scans the metadata JSON file directly.
    # We need to know the metadata location. 
    # Since I can't easily get the exact metadata JSON path without querying Lakekeeper again,
    # I'll fetch the table info first.
    
    import requests
    CATALOG_URL = "http://lakekeeper:8181/catalog/v1"
    # Use the valid Warehouse ID 
    WAREHOUSE_NAME = "af71b84e-c908-11f0-ab2e-8f29848a7d96" 
    NAMESPACE = "test_schema"
    TABLE = "test_table"
    
    print(f"Fetching table metadata for {NAMESPACE}.{TABLE}...")
    try:
        resp = requests.get(f"{CATALOG_URL}/{WAREHOUSE_NAME}/namespaces/{NAMESPACE}/tables/{TABLE}")
        if resp.status_code != 200:
            print(f"❌ Failed to get table info: {resp.status_code} - {resp.text}")
            return
            
        table_info = resp.json()
        metadata_location = table_info.get("metadata-location")
        print(f"📍 Metadata Location: {metadata_location}")
        
        if not metadata_location:
            print("❌ Could not find metadata-location in response")
            return

        # Query using DuckDB
        print("\n📊 Querying table with DuckDB...")
        query = f"SELECT * FROM iceberg_scan('{metadata_location}', allow_moved_paths=true)"
        
        # Execute
        result = conn.execute(query).fetchall()
        
        print(f"✅ Found {len(result)} rows:")
        for row in result:
            print(row)
            
        # Let's insert some dummy data if empty? 
        # DuckDB read-support for Iceberg is mature; write-support is limited/experimental.
        # We usually write using PyIceberg or Spark/Trino. 
        # For now, we just verify READ access.
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Simple logging setup
    logging.basicConfig(level=logging.INFO)
    query_test()

