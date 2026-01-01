#!/usr/bin/env python3
"""
Restore leases_full table from backup.

This script:
1. Loads backup parquet file (local or ADLS)
2. Handles append-only pattern (keeps only latest version per lease)
3. Restores data to the recreated table
4. Verifies restore integrity
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
import io

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, append_data, table_exists
from app.core.logging import setup_logging, get_logger
from app.services.adls_service import adls_service

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

def load_backup_from_adls(backup_timestamp: str) -> pd.DataFrame:
    """Load backup from ADLS"""
    try:
        backup_path = f"backup/leases_recreate_{backup_timestamp}/leases_full.parquet"
        blob_client = adls_service.blob_service_client.get_blob_client(
            container=adls_service.container_name,
            blob=backup_path
        )
        
        # Download blob
        stream = blob_client.download_blob()
        df = pd.read_parquet(io.BytesIO(stream.readall()))
        
        logger.info(f"✅ Loaded backup from ADLS: {backup_path}")
        return df
    except Exception as e:
        logger.error(f"❌ Failed to load backup from ADLS: {e}", exc_info=True)
        raise

def main():
    """Restore leases table from backup"""
    logger.info("=" * 70)
    logger.info("RESTORE LEASES TABLE")
    logger.info("=" * 70)
    
    # Get backup timestamp or path
    if len(sys.argv) > 1:
        backup_input = sys.argv[1]
    else:
        backup_input = input("Enter backup timestamp (YYYYMMDD_HHMMSS) or local file path: ").strip()
    
    try:
        # Step 1: Load backup data
        logger.info("📖 Loading backup data...")
        
        if Path(backup_input).exists():
            # Local file
            logger.info(f"  Loading from local file: {backup_input}")
            df = pd.read_parquet(backup_input)
        elif backup_input.replace("_", "").replace("-", "").isdigit() and len(backup_input) == 15:
            # ADLS timestamp
            logger.info(f"  Loading from ADLS with timestamp: {backup_input}")
            df = load_backup_from_adls(backup_input)
        else:
            logger.error(f"❌ Invalid backup input: {backup_input}")
            logger.error("   Provide either a local file path or timestamp (YYYYMMDD_HHMMSS)")
            sys.exit(1)
        
        row_count = len(df)
        logger.info(f"  ✅ Loaded {row_count} rows from backup")
        
        if row_count == 0:
            logger.warning("⚠️  Backup is empty - nothing to restore")
            return
        
        # Step 2: Handle append-only pattern
        # For leases, we use append-only, so we need to keep only the latest version per lease
        logger.info("🔄 Processing append-only pattern (keeping latest version per lease)...")
        
        if "id" in df.columns and "updated_at" in df.columns:
            # Sort by updated_at descending and drop duplicates keeping first (most recent)
            df = df.sort_values("updated_at", ascending=False)
            df = df.drop_duplicates(subset=["id"], keep="first")
            logger.info(f"  ✅ Deduplicated to {len(df)} unique leases (latest versions)")
        else:
            logger.warning("  ⚠️  Could not deduplicate (missing id or updated_at columns)")
        
        # Step 2.5: Get the current table schema and drop columns that don't exist
        logger.info("🔍 Checking schema compatibility...")
        from app.core.iceberg import load_table
        table = load_table(NAMESPACE, TABLE_NAME)
        current_schema = table.schema()
        schema_field_names = {field.name for field in current_schema.fields}
        backup_columns = set(df.columns)
        
        # Find columns in backup that don't exist in schema
        extra_columns = backup_columns - schema_field_names
        if extra_columns:
            logger.info(f"  🗑️  Removing {len(extra_columns)} columns from backup that don't exist in new schema: {extra_columns}")
            df = df.drop(columns=list(extra_columns))
        
        # Find columns in schema that are missing from backup (will be added as None by append_data)
        missing_columns = schema_field_names - backup_columns
        if missing_columns:
            logger.info(f"  ➕ Schema has {len(missing_columns)} columns not in backup (will be added as None)")
        
        # Step 3: Verify table exists and is empty
        logger.info("🔍 Verifying table...")
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"❌ Table {TABLE_NAME} does not exist! Run recreate_leases_table.py first")
            sys.exit(1)
        
        # Check if table is empty
        existing_df = read_table(NAMESPACE, TABLE_NAME)
        if len(existing_df) > 0:
            logger.warning(f"⚠️  Table already has {len(existing_df)} rows")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != "y":
                logger.info("❌ Aborted")
                sys.exit(0)
        
        # Step 4: Restore data
        logger.info(f"💾 Restoring {len(df)} rows to {TABLE_NAME}...")
        append_data(NAMESPACE, TABLE_NAME, df)
        logger.info(f"  ✅ Data restored")
        
        # Step 5: Verify restore
        logger.info("🔍 Verifying restore...")
        restored_df = read_table(NAMESPACE, TABLE_NAME)
        
        if len(restored_df) != len(df):
            logger.error(f"❌ Restore verification failed: {len(restored_df)} rows != {len(df)} rows")
            sys.exit(1)
        
        logger.info(f"  ✅ Restore verified: {len(restored_df)} rows match backup")
        
        # Step 6: Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ RESTORE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"  Table: {TABLE_NAME}")
        logger.info(f"  Rows restored: {len(restored_df)}")
        logger.info(f"  Columns: {len(restored_df.columns)}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Restore failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

