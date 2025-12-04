#!/usr/bin/env python3
"""
View the contents of the CDC user cache in ADLS.

This script reads the Parquet cache files and displays their contents
for debugging and verification purposes.

Usage:
    # From backend directory with venv activated:
    uv run python view_user_cache.py
    
    # Or with Docker:
    docker exec backend-local python view_user_cache.py
"""
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import io
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime
from azure.storage.blob import BlobServiceClient

from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

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


def read_parquet_from_adls(blob_service: BlobServiceClient, blob_path: str, cache_container: str) -> pd.DataFrame:
    """Read Parquet file from ADLS"""
    blob_client = blob_service.get_blob_client(
        container=cache_container,
        blob=blob_path
    )
    
    if not blob_client.exists():
        return None
    
    stream = io.BytesIO()
    blob_client.download_blob().readinto(stream)
    stream.seek(0)
    
    return pq.read_table(stream).to_pandas()


def view_cache():
    """View cache contents"""
    print("\n" + "=" * 60)
    print("📊 CDC User Cache Viewer")
    print("=" * 60 + "\n")
    
    cache_container = get_cache_container()
    
    # Check Azure configuration
    print("Connecting to Azure Storage...")
    try:
        blob_service = get_blob_service()
        print(f"✅ Connected to: {settings.AZURE_STORAGE_ACCOUNT_NAME}\n")
    except Exception as e:
        print(f"❌ Azure Storage error: {e}")
        sys.exit(1)
    
    # Check container
    container_client = blob_service.get_container_client(cache_container)
    if not container_client.exists():
        print(f"❌ Container '{cache_container}' does not exist")
        print("   Run migrate_user_cache.py first to create the cache")
        sys.exit(1)
    
    # View users cache
    print("=" * 40)
    print("👤 USERS CACHE")
    print("=" * 40)
    print(f"Path: {cache_container}/{USERS_CACHE_PATH}\n")
    
    users_df = read_parquet_from_adls(blob_service, USERS_CACHE_PATH, cache_container)
    if users_df is None:
        print("❌ Users cache file not found")
    else:
        blob_client = blob_service.get_blob_client(container=cache_container, blob=USERS_CACHE_PATH)
        props = blob_client.get_blob_properties()
        print(f"File size: {props.size:,} bytes")
        print(f"Last modified: {props.last_modified}")
        print(f"Total users: {len(users_df)}\n")
        
        if len(users_df) > 0:
            # Show columns
            print("Columns:", list(users_df.columns))
            print()
            
            # Show users (hide sensitive data)
            print("Users (password_hash hidden):")
            print("-" * 40)
            display_cols = [c for c in users_df.columns if c != 'password_hash']
            for i, (_, row) in enumerate(users_df.iterrows()):
                print(f"\n[{i+1}] {row['email']}")
                print(f"    ID: {row['id']}")
                print(f"    Name: {row.get('first_name', 'N/A')} {row.get('last_name', 'N/A')}")
                print(f"    Tax Rate: {row.get('tax_rate', 'N/A')}")
                print(f"    Active: {row.get('is_active', 'N/A')}")
                if '_cdc_timestamp' in row:
                    print(f"    CDC Timestamp: {row['_cdc_timestamp']}")
    
    # View shares cache
    print("\n" + "=" * 40)
    print("🔗 SHARES CACHE")
    print("=" * 40)
    print(f"Path: {cache_container}/{SHARES_CACHE_PATH}\n")
    
    shares_df = read_parquet_from_adls(blob_service, SHARES_CACHE_PATH, cache_container)
    if shares_df is None:
        print("❌ Shares cache file not found")
    else:
        blob_client = blob_service.get_blob_client(container=cache_container, blob=SHARES_CACHE_PATH)
        props = blob_client.get_blob_properties()
        print(f"File size: {props.size:,} bytes")
        print(f"Last modified: {props.last_modified}")
        print(f"Total shares: {len(shares_df)}\n")
        
        if len(shares_df) > 0:
            # Show columns
            print("Columns:", list(shares_df.columns))
            print()
            
            # Show shares
            print("Shares:")
            print("-" * 40)
            for i, (_, row) in enumerate(shares_df.iterrows()):
                user_id = row.get('user_id', 'N/A')
                shared_email = row.get('shared_email', 'N/A')
                print(f"[{i+1}] User {user_id[:8]}... → {shared_email}")
        else:
            print("No shares in cache")
    
    # Build indexes (like the service does)
    print("\n" + "=" * 40)
    print("📇 INDEX PREVIEW")
    print("=" * 40)
    
    if users_df is not None and len(users_df) > 0:
        print(f"\nemail_to_user index: {len(users_df)} entries")
        print(f"user_id_to_user index: {len(users_df)} entries")
    
    if shares_df is not None and len(shares_df) > 0:
        # Build shares_by_user index
        shares_by_user = {}
        shares_by_email = {}
        for _, row in shares_df.iterrows():
            user_id = row.get('user_id')
            shared_email = row.get('shared_email')
            if user_id and shared_email:
                if user_id not in shares_by_user:
                    shares_by_user[user_id] = set()
                shares_by_user[user_id].add(shared_email)
                
                if shared_email not in shares_by_email:
                    shares_by_email[shared_email] = set()
                shares_by_email[shared_email].add(user_id)
        
        print(f"\nshares_by_user index: {len(shares_by_user)} users with shares")
        for user_id, emails in list(shares_by_user.items())[:3]:
            print(f"  {user_id[:8]}... → {emails}")
        
        print(f"\nshares_by_email index: {len(shares_by_email)} emails shared with")
        for email, user_ids in list(shares_by_email.items())[:3]:
            print(f"  {email} ← {len(user_ids)} user(s)")
    
    print("\n" + "=" * 60)
    print("✅ Cache view complete")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        view_cache()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)
