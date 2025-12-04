#!/usr/bin/env python3
"""
Migration script to populate the CDC user cache in ADLS.

This script reads from Iceberg tables (users, user_shares) and creates
Parquet cache files in ADLS for fast authentication and sharing lookups.

Usage:
    # From backend directory with venv activated:
    uv run python migrate_user_cache.py
    
    # Or with Docker:
    docker exec backend-local python migrate_user_cache.py

Environment variables required:
    - AZURE_STORAGE_ACCOUNT_NAME or AZURE_STORAGE_CONNECTION_STRING
    - AZURE_STORAGE_ACCOUNT_KEY (if not using connection string)
    - LAKEKEEPER__BASE_URI (for Iceberg catalog)
    - LAKEKEEPER__WAREHOUSE_NAME
"""
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import io
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from azure.storage.blob import BlobServiceClient

from app.core.config import settings
from app.core.iceberg import read_table, table_exists
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
USERS_CACHE_PATH = "cdc/users/users_current.parquet"
SHARES_CACHE_PATH = "cdc/shares/user_shares_current.parquet"

def get_cache_container() -> str:
    """Get the container name for CDC cache (configurable)"""
    if settings.CDC_CACHE_CONTAINER_NAME:
        return settings.CDC_CACHE_CONTAINER_NAME
    return settings.AZURE_STORAGE_CONTAINER_NAME or "documents"


def get_blob_service() -> BlobServiceClient:
    """Initialize Azure Blob client"""
    if settings.AZURE_STORAGE_CONNECTION_STRING:
        return BlobServiceClient.from_connection_string(
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
    elif settings.AZURE_STORAGE_ACCOUNT_NAME and settings.AZURE_STORAGE_ACCOUNT_KEY:
        conn_str = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={settings.AZURE_STORAGE_ACCOUNT_NAME};"
            f"AccountKey={settings.AZURE_STORAGE_ACCOUNT_KEY};"
            f"EndpointSuffix=core.windows.net"
        )
        return BlobServiceClient.from_connection_string(conn_str)
    else:
        raise ValueError("Azure Storage credentials not configured")


def save_parquet_to_adls(blob_service: BlobServiceClient, df: pd.DataFrame, blob_path: str):
    """Save DataFrame as Parquet to ADLS"""
    cache_container = get_cache_container()
    # Ensure container exists
    container_client = blob_service.get_container_client(cache_container)
    if not container_client.exists():
        container_client.create_container()
        logger.info(f"Created container: {cache_container}")
    
    # Add CDC timestamp
    df = df.copy()
    df["_cdc_timestamp"] = pd.Timestamp.now()
    
    # Convert timestamps to microseconds (Parquet requirement)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype('datetime64[us]')
    
    # Convert to parquet bytes
    table = pa.Table.from_pandas(df, preserve_index=False)
    stream = io.BytesIO()
    pq.write_table(table, stream)
    stream.seek(0)
    
    # Upload to ADLS
    blob_client = blob_service.get_blob_client(
        container=cache_container,
        blob=blob_path
    )
    blob_client.upload_blob(stream, overwrite=True)
    
    logger.info(f"✅ Saved {len(df)} rows to {blob_path}")


def migrate_users_cache():
    """Main migration function"""
    print("\n" + "=" * 60)
    print("🚀 CDC User Cache Migration")
    print("=" * 60 + "\n")
    
    # Check Azure configuration
    print("1️⃣  Checking Azure Storage configuration...")
    try:
        blob_service = get_blob_service()
        print(f"   ✅ Azure Storage connected: {settings.AZURE_STORAGE_ACCOUNT_NAME}")
    except Exception as e:
        print(f"   ❌ Azure Storage error: {e}")
        print("\n   Required environment variables:")
        print("   - AZURE_STORAGE_ACCOUNT_NAME")
        print("   - AZURE_STORAGE_ACCOUNT_KEY")
        print("   Or: AZURE_STORAGE_CONNECTION_STRING")
        sys.exit(1)
    
    # Check Iceberg/Lakekeeper configuration
    print("\n2️⃣  Checking Iceberg catalog configuration...")
    print(f"   Lakekeeper URI: {settings.LAKEKEEPER__BASE_URI}")
    print(f"   Warehouse: {settings.LAKEKEEPER__WAREHOUSE_NAME}")
    
    # Load users from Iceberg
    print("\n3️⃣  Loading users from Iceberg...")
    if not table_exists(NAMESPACE, "users"):
        print("   ⚠️  Users table does not exist in Iceberg")
        print("   Creating empty cache files...")
        users_df = pd.DataFrame(columns=[
            "id", "email", "password_hash", "first_name", "last_name",
            "tax_rate", "mortgage_interest_rate", "loc_interest_rate",
            "is_active", "created_at", "updated_at"
        ])
    else:
        users_df = read_table(NAMESPACE, "users")
        print(f"   ✅ Loaded {len(users_df)} users from Iceberg")
        
        # Show sample (without sensitive data)
        if len(users_df) > 0:
            print("\n   Sample users:")
            for _, row in users_df.head(3).iterrows():
                print(f"   - {row['email']} (ID: {row['id'][:8]}...)")
    
    # Load shares from Iceberg
    print("\n4️⃣  Loading shares from Iceberg...")
    if not table_exists(NAMESPACE, "user_shares"):
        print("   ⚠️  User shares table does not exist in Iceberg")
        shares_df = pd.DataFrame(columns=["id", "user_id", "shared_email", "created_at", "updated_at"])
    else:
        shares_df = read_table(NAMESPACE, "user_shares")
        print(f"   ✅ Loaded {len(shares_df)} shares from Iceberg")
        
        # Show sample
        if len(shares_df) > 0:
            print("\n   Sample shares:")
            for _, row in shares_df.head(3).iterrows():
                print(f"   - User {row['user_id'][:8]}... → {row['shared_email']}")
    
    # Save to ADLS
    print("\n5️⃣  Saving cache to ADLS...")
    
    print(f"\n   Saving users cache to: {USERS_CACHE_PATH}")
    save_parquet_to_adls(blob_service, users_df, USERS_CACHE_PATH)
    
    print(f"\n   Saving shares cache to: {SHARES_CACHE_PATH}")
    save_parquet_to_adls(blob_service, shares_df, SHARES_CACHE_PATH)
    
    # Verify
    cache_container = get_cache_container()
    print("\n6️⃣  Verifying cache files...")
    for path in [USERS_CACHE_PATH, SHARES_CACHE_PATH]:
        blob_client = blob_service.get_blob_client(container=cache_container, blob=path)
        if blob_client.exists():
            props = blob_client.get_blob_properties()
            print(f"   ✅ {path}")
            print(f"      Size: {props.size:,} bytes")
            print(f"      Modified: {props.last_modified}")
        else:
            print(f"   ❌ {path} - NOT FOUND")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Migration Complete!")
    print("=" * 60)
    print(f"\nCache Statistics:")
    print(f"  - Users: {len(users_df)}")
    print(f"  - Shares: {len(shares_df)}")
    print(f"  - Container: {cache_container}")
    print(f"\nCache files created:")
    print(f"  - {USERS_CACHE_PATH}")
    print(f"  - {SHARES_CACHE_PATH}")
    print("\nThe backend will now use these cache files for fast authentication.")
    print("To manually refresh, call: POST /api/v1/health/cache/sync")
    print()


if __name__ == "__main__":
    try:
        migrate_users_cache()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)

