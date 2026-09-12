#!/usr/bin/env python3
"""
Restore leases data from backup files after schema changes
"""
import sys
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import pyarrow as pa
import json
from decimal import Decimal

# Add parent directory to path to import app modules
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, read_table, load_table, table_exists
from app.core.logging import setup_logging, get_logger
from app.scripts.migrate_leases_merge_tenants import create_new_leases_schema, merge_tenant_data, convert_pet_data

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
NEW_LEASES_TABLE = "leases"
LEASES_BACKUP_FILE = Path("/tmp/leases_full_backup.parquet")
TENANTS_BACKUP_FILE = Path("/tmp/lease_tenants_backup.parquet")


def restore_data():
    """Restore data from backup files"""
    logger.info("🔄 Restoring leases data from backup files...")
    
    # Load backup files
    if not LEASES_BACKUP_FILE.exists():
        logger.error(f"❌ Backup file not found: {LEASES_BACKUP_FILE}")
        return
    
    logger.info(f"  📖 Loading {LEASES_BACKUP_FILE}...")
    leases_df = pd.read_parquet(LEASES_BACKUP_FILE)
    logger.info(f"    ✅ Loaded {len(leases_df)} leases")
    
    tenants_df = None
    if TENANTS_BACKUP_FILE.exists():
        logger.info(f"  📖 Loading {TENANTS_BACKUP_FILE}...")
        tenants_df = pd.read_parquet(TENANTS_BACKUP_FILE)
        logger.info(f"    ✅ Loaded {len(tenants_df)} tenant records")
    else:
        logger.warning(f"    ⚠️  Tenant backup file not found: {TENANTS_BACKUP_FILE}")
    
    # Merge tenant data
    if leases_df is not None and not leases_df.empty:
        leases_df = merge_tenant_data(leases_df, tenants_df)
        leases_df = convert_pet_data(leases_df)
    
    # Convert and load data (using the same function from migration script)
    from app.scripts.migrate_leases_merge_tenants import convert_and_load_data
    convert_and_load_data(leases_df)
    
    logger.info("✅ Data restoration complete!")


if __name__ == "__main__":
    try:
        restore_data()
    except Exception as e:
        logger.error(f"❌ Restoration failed: {e}", exc_info=True)
        raise




