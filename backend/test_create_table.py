import requests
import json
import os

# Lakekeeper configuration
# In docker-compose, lakekeeper is accessible at http://lakekeeper:8181
CATALOG_URL = "http://lakekeeper:8181/catalog/v1"

# Use the valid Warehouse ID found via /management/v1/warehouse
WAREHOUSE_NAME = "af71b84e-c908-11f0-ab2e-8f29848a7d96"  # ID of 'lakekeeper' warehouse

def create_table_test():
    print(f"Testing connection to Lakekeeper at {CATALOG_URL}...")
    
    # 1. Create Namespace
    namespace = "test_schema"
    print(f"\n1. Creating namespace '{namespace}'...")
    
    ns_url = f"{CATALOG_URL}/{WAREHOUSE_NAME}/namespaces"
    payload = {"namespace": [namespace]}
    
    try:
        response = requests.post(ns_url, json=payload)
        if response.status_code == 200:
            print("✅ Namespace created successfully")
        elif response.status_code == 409:
            print("⚠️  Namespace already exists (this is fine)")
        else:
            print(f"❌ Failed to create namespace: {response.status_code} - {response.text}")
            # Continue anyway to try table creation
    except Exception as e:
        print(f"❌ Error connecting to Lakekeeper: {e}")
        print("   Are you running this from inside the backend container?")
        return

    # 2. Create Table
    table_name = "test_table"
    print(f"\n2. Creating table '{namespace}.{table_name}'...")
    
    table_url = f"{CATALOG_URL}/{WAREHOUSE_NAME}/namespaces/{namespace}/tables"
    
    # Simplified payload according to Iceberg REST Spec
    table_payload = {
        "name": table_name,
        "schema": {
            "type": "struct",
            "fields": [
                {"id": 1, "name": "id", "type": "int", "required": True},
                {"id": 2, "name": "message", "type": "string", "required": False}
            ]
        }
        # Removed empty partition-spec and write-order
    }
    
    response = requests.post(table_url, json=table_payload)
    
    if response.status_code == 200:
        print("✅ Table created successfully!")
        print(json.dumps(response.json(), indent=2))
    elif response.status_code == 409:
        print("⚠️  Table already exists")
        
        # Optional: Drop and recreate to prove we can
        print("   Dropping existing table...")
        del_url = f"{CATALOG_URL}/{WAREHOUSE_NAME}/namespaces/{namespace}/tables/{table_name}"
        requests.delete(del_url)
        
        print("   Recreating table...")
        response = requests.post(table_url, json=table_payload)
        if response.status_code == 200:
            print("✅ Table dropped and recreated successfully!")
        else:
            print(f"❌ Failed to recreate table: {response.status_code} - {response.text}")
    else:
        print(f"❌ Failed to create table: {response.status_code} - {response.text}")

if __name__ == "__main__":
    create_table_test()
