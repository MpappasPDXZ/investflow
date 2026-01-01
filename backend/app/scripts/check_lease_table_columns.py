#!/usr/bin/env python3
"""
Check actual columns in the leases table and compare with LaTeX usage.
Also check how many unique lease IDs exist.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, load_table
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

# Columns used in LaTeX generator
USED_COLUMNS = {
    "id", "user_id", "property_id", "unit_id",
    "status", "lease_version", "state",
    "lease_date", "commencement_date", "termination_date", "auto_convert_month_to_month", "signed_date",
    "monthly_rent", "rent_due_day", "rent_due_by_day", "rent_due_by_time", "payment_method", 
    "prorated_first_month_rent", "show_prorated_rent",
    "late_fee_day_1_10", "late_fee_day_11", "late_fee_day_16", "late_fee_day_21",
    "nsf_fee",
    "security_deposit", "deposit_return_days",
    "include_holding_fee_addendum", "holding_fee_amount", "holding_fee_date",
    "max_occupants", "max_adults", "max_children",
    "utilities_tenant", "utilities_landlord", "utilities_provided_by_owner_city",
    "pets_allowed", "pet_fee_one", "pet_fee_two", "pet_deposit_total", "pet_description", 
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
    "manager_address", "deposit_account_info", "moveout_inspection_rights", "military_termination_days",
    "tenant_lawn_mowing", "tenant_snow_removal", "tenant_lawn_care",
    "generated_pdf_document_id", "template_used",
    "notes", "created_at", "updated_at", "is_active",
}

def main():
    """Check table columns and data"""
    logger.info("=" * 70)
    logger.info("LEASE TABLE COLUMN ANALYSIS")
    logger.info("=" * 70)
    logger.info("")
    
    # Get actual table schema
    table = load_table(NAMESPACE, TABLE_NAME)
    current_schema = table.schema()
    schema_columns = {field.name for field in current_schema.fields}
    
    logger.info(f"📊 Table schema has {len(schema_columns)} columns")
    
    # Read actual data to see what columns have data
    logger.info("📖 Reading table data...")
    df = read_table(NAMESPACE, TABLE_NAME)
    logger.info(f"  ✅ Read {len(df)} rows")
    
    # Check unique lease IDs
    unique_lease_ids = df["id"].nunique() if "id" in df.columns else 0
    logger.info(f"  📋 Unique lease IDs: {unique_lease_ids}")
    
    # Find columns that exist in schema but are not used in LaTeX
    unused_in_schema = schema_columns - USED_COLUMNS
    
    # Find columns used in LaTeX but not in schema (may have been added via evolution)
    missing_in_schema = USED_COLUMNS - schema_columns
    
    # Find columns in data that are all null/empty (candidates for removal)
    all_null_columns = []
    for col in df.columns:
        if df[col].isna().all() or (df[col].dtype == 'object' and (df[col].astype(str).str.strip() == '').all()):
            all_null_columns.append(col)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("UNUSED COLUMNS (in schema but not used in LaTeX)")
    logger.info("=" * 70)
    if unused_in_schema:
        for col in sorted(unused_in_schema):
            # Check if column has any non-null data
            has_data = col in df.columns and not df[col].isna().all()
            status = "📊 (has data)" if has_data else "🗑️  (all null)"
            logger.info(f"  {col} {status}")
        logger.info(f"")
        logger.info(f"Total: {len(unused_in_schema)} unused columns")
    else:
        logger.info("  ✅ No unused columns found")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("MISSING COLUMNS (used in LaTeX but not in schema)")
    logger.info("=" * 70)
    if missing_in_schema:
        for col in sorted(missing_in_schema):
            logger.info(f"  ⚠️  {col}")
        logger.info(f"")
        logger.info(f"Total: {len(missing_in_schema)} missing columns")
        logger.info("  Note: These may have been added via schema evolution")
    else:
        logger.info("  ✅ All LaTeX columns exist in schema")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("ALL NULL COLUMNS (candidates for removal)")
    logger.info("=" * 70)
    if all_null_columns:
        for col in sorted(all_null_columns):
            logger.info(f"  🗑️  {col}")
        logger.info(f"")
        logger.info(f"Total: {len(all_null_columns)} columns with no data")
    else:
        logger.info("  ✅ No all-null columns found")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"  Total rows: {len(df)}")
    logger.info(f"  Unique lease IDs: {unique_lease_ids}")
    logger.info(f"  Schema columns: {len(schema_columns)}")
    logger.info(f"  LaTeX used columns: {len(USED_COLUMNS)}")
    logger.info(f"  Unused in schema: {len(unused_in_schema)}")
    logger.info(f"  Missing in schema: {len(missing_in_schema)}")
    logger.info(f"  All null columns: {len(all_null_columns)}")
    logger.info("=" * 70)
    
    return unused_in_schema, missing_in_schema, all_null_columns, unique_lease_ids

if __name__ == "__main__":
    unused, missing, null_cols, unique_count = main()
    logger.info("")
    logger.info("⚠️  Please verify the unused columns list above.")
    logger.info("   These columns will be removed from the schema if approved.")


