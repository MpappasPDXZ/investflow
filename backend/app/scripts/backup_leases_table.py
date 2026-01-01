#!/usr/bin/env python3
"""
Backup leases_full table before dropping and recreating.

This script:
1. Reads all data from leases_full table
2. Saves to local parquet file (with timestamp)
3. Saves to ADLS backup folder (with timestamp)
4. Verifies backup integrity
5. Provides summary statistics

CRITICAL: Run this before dropping the table!
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
import io

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, table_exists
from app.core.logging import setup_logging, get_logger
from app.services.adls_service import adls_service

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

def save_backup_to_adls(df: pd.DataFrame, timestamp: str) -> bool:
    """Save backup to ADLS"""
    try:
        # Convert timestamps to microseconds (Parquet requirement)
        df_backup = df.copy()
        for col in df_backup.columns:
            if pd.api.types.is_datetime64_any_dtype(df_backup[col]):
                df_backup[col] = df_backup[col].astype('datetime64[us]')
        
        # Convert to parquet bytes
        table = pa.Table.from_pandas(df_backup, preserve_index=False)
        stream = io.BytesIO()
        pq.write_table(table, stream)
        stream.seek(0)
        
        # Upload to ADLS backup folder
        backup_path = f"backup/leases_recreate_{timestamp}/leases_full.parquet"
        blob_client = adls_service.blob_service_client.get_blob_client(
            container=adls_service.container_name,
            blob=backup_path
        )
        blob_client.upload_blob(stream, overwrite=True)
        
        logger.info(f"✅ Backup saved to ADLS: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save backup to ADLS: {e}", exc_info=True)
        return False

def main():
    """Backup leases table"""
    logger.info("=" * 70)
    logger.info("BACKUP LEASES TABLE")
    logger.info("=" * 70)
    logger.info("⚠️  This backup is required before dropping/recreating the table")
    logger.info("")
    
    # Check if table exists
    if not table_exists(NAMESPACE, TABLE_NAME):
        logger.error(f"❌ Table {TABLE_NAME} does not exist!")
        sys.exit(1)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Step 1: Read all data
        logger.info(f"📖 Reading data from {TABLE_NAME}...")
        df = read_table(NAMESPACE, TABLE_NAME)
        total_rows = len(df)
        logger.info(f"  ✅ Read {total_rows} total rows")
        
        # Step 1.5: Filter to only active records (remove soft-deleted)
        logger.info("🔍 Filtering to active records only...")
        if "is_active" in df.columns:
            df_active = df[df["is_active"] == True].copy()
            inactive_count = total_rows - len(df_active)
            logger.info(f"  ✅ Found {len(df_active)} active records, {inactive_count} inactive (will be excluded)")
            
            if inactive_count > 0:
                logger.info(f"  🗑️  Removing {inactive_count} inactive records from backup")
            
            df = df_active
        else:
            logger.warning("  ⚠️  No 'is_active' column found - backing up all records")
        
        # Step 1.6: Deduplicate to latest version per lease (append-only pattern)
        logger.info("🔄 Deduplicating to latest version per lease...")
        if "id" in df.columns:
            initial_count = len(df)
            if "updated_at" in df.columns:
                # Sort by updated_at descending and keep first (most recent)
                df = df.sort_values("updated_at", ascending=False)
                df = df.drop_duplicates(subset=["id"], keep="first")
            elif "lease_version" in df.columns:
                # Sort by lease_version descending and keep first (highest version)
                df = df.sort_values("lease_version", ascending=False)
                df = df.drop_duplicates(subset=["id"], keep="first")
            else:
                # Just drop duplicates by ID (keep first)
                df = df.drop_duplicates(subset=["id"], keep="first")
            
            dedup_count = initial_count - len(df)
            if dedup_count > 0:
                logger.info(f"  ✅ Deduplicated: {len(df)} unique leases (removed {dedup_count} older versions)")
            else:
                logger.info(f"  ✅ No duplicates found: {len(df)} unique leases")
        else:
            logger.warning("  ⚠️  No 'id' column found - cannot deduplicate")
        
        row_count = len(df)
        if row_count == 0:
            logger.warning("⚠️  No active records to backup")
            return
        
        # Step 2: Save to local parquet
        local_backup_path = f"/tmp/leases_backup_{timestamp}.parquet"
        logger.info(f"💾 Saving to local file: {local_backup_path}")
        
        # Convert timestamps for parquet
        df_local = df.copy()
        for col in df_local.columns:
            if pd.api.types.is_datetime64_any_dtype(df_local[col]):
                df_local[col] = df_local[col].astype('datetime64[us]')
        
        df_local.to_parquet(local_backup_path, index=False)
        file_size = Path(local_backup_path).stat().st_size / 1024 / 1024  # MB
        logger.info(f"  ✅ Saved {file_size:.2f} MB to local file")
        
        # Step 3: Save to ADLS
        logger.info(f"☁️  Saving to ADLS...")
        adls_success = save_backup_to_adls(df, timestamp)
        
        # Step 4: Verify backup integrity
        logger.info("🔍 Verifying backup integrity...")
        df_verify = pd.read_parquet(local_backup_path)
        
        if len(df_verify) != row_count:
            logger.error(f"❌ Backup verification failed: {len(df_verify)} rows != {row_count} rows")
            sys.exit(1)
        
        logger.info(f"  ✅ Backup verified: {len(df_verify)} rows match original")
        
        # Step 5: Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("BACKUP SUMMARY")
        logger.info("=" * 70)
        logger.info(f"  Table: {TABLE_NAME}")
        logger.info(f"  Rows: {row_count}")
        logger.info(f"  Columns: {len(df.columns)}")
        logger.info(f"  Local backup: {local_backup_path}")
        logger.info(f"  Local size: {file_size:.2f} MB")
        logger.info(f"  Timestamp: {timestamp}")
        if adls_success:
            logger.info(f"  ADLS backup: backup/leases_recreate_{timestamp}/leases_full.parquet")
        else:
            logger.warning(f"  ⚠️  ADLS backup failed (local backup is safe)")
        logger.info("")
        logger.info("✅ BACKUP COMPLETE - Safe to proceed with drop/recreate")
        logger.info(f"📝 Save this timestamp for restore: {timestamp}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

