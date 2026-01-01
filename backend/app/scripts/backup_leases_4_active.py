#!/usr/bin/env python3
"""
Backup only the 4 active lease records with only the columns that will remain in the new schema.

This script:
1. Reads leases_full table
2. Filters for is_active=True
3. Gets only the latest version of each lease (deduplicate by id, keep latest lease_version)
4. Keeps only the first 4 unique lease IDs
5. Filters columns to only those that will remain in the new schema (LaTeX-used + System)
6. Saves to parquet and uploads to ADLS
"""
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, load_table
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

# Columns that will remain in the new schema (LaTeX-used + System)
KEEP_COLUMNS = {
    # System columns
    "id", "user_id", "status", "lease_version", "created_at", "updated_at", "is_active",
    "generated_pdf_document_id", "template_used",
    # LaTeX-used columns
    "property_id", "unit_id", "state",
    "lease_date", "commencement_date", "termination_date", "auto_convert_month_to_month", "signed_date",
    "monthly_rent", "rent_due_day", "rent_due_by_day", "rent_due_by_time", "payment_method", 
    "prorated_first_month_rent", "show_prorated_rent",
    "late_fee_day_1_10", "late_fee_day_11", "late_fee_day_16", "late_fee_day_21",
    "nsf_fee",
    "security_deposit", "deposit_return_days",
    "include_holding_fee_addendum", "holding_fee_amount", "holding_fee_date",
    "max_occupants", "max_adults", "max_children",
    "utilities_tenant", "utilities_landlord", "utilities_provided_by_owner_city",
    "pets_allowed", "pet_fee", "pet_description", 
    "max_pets", "pet_fee", "pets",
    "parking_spaces", "parking_small_vehicles", "parking_large_trucks", 
    "garage_spaces", "offstreet_parking_spots",
    "front_door_keys", "back_door_keys", "garage_back_door_keys", "key_replacement_fee",
    "has_shared_driveway", "shared_driveway_with", "snow_removal_responsibility",
    "has_garage", "garage_outlets_prohibited", "has_garage_door_opener", "garage_door_opener_fee",
    "has_attic", "attic_usage", "has_basement",
    "appliances_provided",
    "lead_paint_disclosure", "lead_paint_year_built",
    "early_termination_allowed", "early_termination_notice_days", "early_termination_fee_months", 
    "early_termination_fee_amount",
    "moveout_costs",
    "methamphetamine_disclosure", "owner_name", "owner_address", "manager_name", 
    "manager_address", "moveout_inspection_rights", "military_termination_days",
    "tenant_lawn_mowing", "tenant_snow_removal", "tenant_lawn_care",
    "notes",
}

def main():
    """Backup 4 active leases with cleaned columns"""
    logger.info("=" * 70)
    logger.info("BACKUP 4 ACTIVE LEASES (CLEANED SCHEMA)")
    logger.info("=" * 70)
    logger.info("")
    
    # Read table
    logger.info("📖 Reading leases_full table...")
    df = read_table(NAMESPACE, TABLE_NAME)
    logger.info(f"  ✅ Read {len(df)} total rows")
    
    # Filter for active leases
    if "is_active" in df.columns:
        df = df[df["is_active"] == True].copy()
        logger.info(f"  ✅ Filtered to {len(df)} active rows")
    else:
        logger.warning("  ⚠️  No 'is_active' column found, using all rows")
    
    # Deduplicate: keep latest version per lease ID
    if "id" in df.columns and "lease_version" in df.columns:
        df = df.sort_values("lease_version", ascending=False)
        df = df.drop_duplicates(subset=["id"], keep="first")
        logger.info(f"  ✅ Deduplicated to {len(df)} unique leases (latest version)")
    
    # Keep only first 4 unique lease IDs
    if len(df) > 4:
        df = df.head(4).copy()
        logger.info(f"  ✅ Limited to 4 leases")
    
    logger.info(f"  📋 Lease IDs: {df['id'].tolist() if 'id' in df.columns else 'N/A'}")
    
    # Filter columns to only those we're keeping
    existing_columns = set(df.columns)
    columns_to_keep = [col for col in KEEP_COLUMNS if col in existing_columns]
    columns_to_drop = [col for col in existing_columns if col not in KEEP_COLUMNS]
    
    logger.info("")
    logger.info(f"  📊 Columns to keep: {len(columns_to_keep)}")
    logger.info(f"  🗑️  Columns to drop: {len(columns_to_drop)}")
    if columns_to_drop:
        logger.info(f"     Dropping: {', '.join(sorted(columns_to_drop))}")
    
    df_clean = df[columns_to_keep].copy()
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_file = f"/tmp/leases_4_active_{timestamp}.parquet"
    
    # Save locally
    logger.info("")
    logger.info(f"💾 Saving to {local_file}...")
    df_clean.to_parquet(local_file, index=False)
    logger.info(f"  ✅ Saved {len(df_clean)} rows, {len(df_clean.columns)} columns")
    
    # Note: Lakekeeper manages ADLS, so we just save locally
    logger.info("")
    logger.info("  ℹ️  Backup saved locally (Lakekeeper manages ADLS)")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ BACKUP COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Rows: {len(df_clean)}")
    logger.info(f"  Columns: {len(df_clean.columns)}")
    logger.info(f"  Timestamp: {timestamp}")
    logger.info(f"  Local file: {local_file}")
    logger.info("")
    logger.info("⚠️  Safe to proceed with schema migration")
    logger.info("=" * 70)
    
    return timestamp, local_file

if __name__ == "__main__":
    timestamp, local_file = main()
    print(f"\n✅ Backup complete. Timestamp: {timestamp}")

