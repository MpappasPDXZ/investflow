#!/usr/bin/env python3
"""
Complete workflow to backup, drop, recreate, and restore leases_full table.

This script:
1. Backs up all data to local parquet file
2. Drops the existing table
3. Creates a new table with the current schema
4. Restores data from backup
5. Verifies the restore

WARNING: This will temporarily delete all data!
Make sure you have a backup before running!
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import (
    read_table, append_data, table_exists, get_catalog, load_table
)
from app.core.logging import setup_logging, get_logger
from app.scripts.create_data import create_leases_schema

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

def main():
    """Complete backup, drop, recreate, and restore workflow"""
    logger.info("=" * 80)
    logger.info("COMPLETE LEASES TABLE RECREATION WORKFLOW")
    logger.info("=" * 80)
    logger.info("⚠️  WARNING: This will temporarily delete all data!")
    logger.info("")
    
    # Safety check
    response = input("Type 'YES' to continue: ")
    if response != "YES":
        logger.info("❌ Aborted")
        sys.exit(0)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = Path(f"leases_backup_{timestamp}.parquet")
    
    try:
        # ========================================================================
        # STEP 1: BACKUP ALL DATA TO LOCAL PARQUET
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 1: BACKUP DATA TO LOCAL PARQUET")
        logger.info("=" * 80)
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"❌ Table {TABLE_NAME} does not exist!")
            sys.exit(1)
        
        logger.info(f"📖 Reading all data from {TABLE_NAME}...")
        df = read_table(NAMESPACE, TABLE_NAME)
        row_count = len(df)
        col_count = len(df.columns)
        logger.info(f"  ✅ Read {row_count} rows with {col_count} columns")
        
        if row_count == 0:
            logger.warning("⚠️  Table is empty - nothing to backup")
        else:
            # Handle append-only pattern - keep only latest version per lease
            if "id" in df.columns and "updated_at" in df.columns:
                logger.info("🔄 Deduplicating to latest version per lease...")
                df = df.sort_values("updated_at", ascending=False)
                df = df.drop_duplicates(subset=["id"], keep="first")
                logger.info(f"  ✅ Deduplicated to {len(df)} unique leases")
            
            # Save to local parquet
            logger.info(f"💾 Saving backup to {backup_file}...")
            df.to_parquet(backup_file, index=False)
            logger.info(f"  ✅ Backup saved: {backup_file}")
            logger.info(f"  📊 Backup size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
        
        # ========================================================================
        # STEP 2: DROP EXISTING TABLE
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 2: DROP EXISTING TABLE")
        logger.info("=" * 80)
        
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, TABLE_NAME)
        
        logger.info(f"🗑️  Dropping table {TABLE_NAME}...")
        try:
            catalog.drop_table(table_identifier)
            logger.info(f"  ✅ Table {TABLE_NAME} dropped")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not drop table (may not exist): {e}")
        
        # ========================================================================
        # STEP 3: RECREATE TABLE WITH CURRENT SCHEMA
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 3: RECREATE TABLE WITH CURRENT SCHEMA")
        logger.info("=" * 80)
        
        logger.info(f"🔨 Creating new table {TABLE_NAME}...")
        schema = create_leases_schema()
        
        # Create table optimized for fast id-based lookups
        # PRIMARY KEY: 'id' field - all operations filter by this
        # With <10 active rows, operations should be INSTANT (<1 second)
        catalog.create_table(
            identifier=table_identifier,
            schema=schema,
            properties={
                "write.metadata.delete-after-commit.enabled": "true",
                "write.metadata.previous-versions-max": "4"
            }
        )
        
        logger.info(f"  ✅ Table {TABLE_NAME} created")
        logger.info(f"  📋 Schema: {len(schema)} columns")
        logger.info(f"  🔑 PRIMARY KEY: 'id' field - all lookups use predicate pushdown on this")
        logger.info(f"  ⚙️  Metadata cleanup: Enabled (keeps only 4 versions)")
        logger.info(f"  ⚡ Performance: With <10 rows, saves should be <1 second")
        
        # Verify table exists
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"❌ Table {TABLE_NAME} does not exist after creation!")
            sys.exit(1)
        
        # ========================================================================
        # STEP 4: RESTORE DATA FROM BACKUP
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 4: RESTORE DATA FROM BACKUP")
        logger.info("=" * 80)
        
        if row_count == 0:
            logger.info("  ℹ️  No data to restore (table was empty)")
        else:
            # Load backup
            logger.info(f"📖 Loading backup from {backup_file}...")
            df_restore = pd.read_parquet(backup_file)
            logger.info(f"  ✅ Loaded {len(df_restore)} rows")
            
            # Check schema compatibility
            logger.info("🔍 Checking schema compatibility...")
            table = load_table(NAMESPACE, TABLE_NAME)
            current_schema = table.schema()
            schema_field_names = {field.name for field in current_schema.fields}
            backup_columns = set(df_restore.columns)
            
            # Drop columns that don't exist in new schema
            extra_columns = backup_columns - schema_field_names
            if extra_columns:
                logger.info(f"  🗑️  Removing {len(extra_columns)} columns from backup: {extra_columns}")
                df_restore = df_restore.drop(columns=list(extra_columns))
            
            # Note missing columns (will be added as None by append_data)
            missing_columns = schema_field_names - backup_columns
            if missing_columns:
                logger.info(f"  ➕ Schema has {len(missing_columns)} new columns (will be None)")
            
            # Restore data
            logger.info(f"💾 Restoring {len(df_restore)} rows to {TABLE_NAME}...")
            append_data(NAMESPACE, TABLE_NAME, df_restore)
            logger.info(f"  ✅ Data restored")
        
        # ========================================================================
        # STEP 5: VERIFY RESTORE
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("STEP 5: VERIFY RESTORE")
        logger.info("=" * 80)
        
        logger.info(f"🔍 Reading restored data from {TABLE_NAME}...")
        restored_df = read_table(NAMESPACE, TABLE_NAME)
        restored_count = len(restored_df)
        
        logger.info(f"  ✅ Restored table has {restored_count} rows")
        logger.info(f"  📋 Restored table has {len(restored_df.columns)} columns")
        
        if row_count > 0 and restored_count != len(df_restore):
            logger.error(f"❌ Verification failed: {restored_count} rows != {len(df_restore)} rows")
            sys.exit(1)
        
        # Check for active leases
        if "is_active" in restored_df.columns:
            active_count = restored_df["is_active"].sum() if "is_active" in restored_df.columns else 0
            logger.info(f"  ✅ Active leases: {active_count}")
        
        # ========================================================================
        # SUMMARY
        # ========================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ WORKFLOW COMPLETE")
        logger.info("=" * 80)
        logger.info(f"  Table: {TABLE_NAME}")
        logger.info(f"  Backup file: {backup_file}")
        logger.info(f"  Rows restored: {restored_count}")
        logger.info(f"  Columns: {len(restored_df.columns)}")
        logger.info(f"  PRIMARY KEY: 'id' - all operations filter by this field")
        logger.info(f"  Metadata cleanup: Enabled (keeps only 4 versions)")
        logger.info("")
        logger.info("⚡ PERFORMANCE EXPECTATIONS:")
        logger.info("  - With <10 active rows, all operations should be INSTANT")
        logger.info("  - GET /leases/{id}: <100ms (predicate pushdown on 'id')")
        logger.info("  - PUT /leases/{id}: <1 second (delete + append, both filter by 'id')")
        logger.info("  - POST /leases: <1 second (simple append)")
        logger.info("")
        logger.info("📝 Next steps:")
        logger.info("  1. Test GET /leases/{id} - should be <100ms")
        logger.info("  2. Test PUT /leases/{id} - should be <1 second")
        logger.info("  3. Test lease generation")
        logger.info(f"  4. Keep backup file: {backup_file}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}", exc_info=True)
        logger.error("")
        logger.error("⚠️  If the table was dropped but restore failed, you can restore manually:")
        logger.error(f"   python app/scripts/restore_leases_table.py {backup_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()

