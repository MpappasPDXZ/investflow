#!/usr/bin/env python3
"""
Generate a detailed CSV/markdown mapping of lease columns with data analysis.

Outputs:
1. Full mapping table
2. Unused columns list
3. Columns with no data
4. Recommendations
"""
import sys
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import read_table, load_table
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

# Columns user can edit in the frontend form
USER_EDITABLE_COLUMNS = {
    "property_id", "unit_id", "state", "lease_date", "commencement_date", 
    "termination_date", "lease_duration_months", "auto_convert_month_to_month",
    "monthly_rent", "show_prorated_rent", "prorated_rent_amount", "prorated_rent_language",
    "security_deposit", "include_holding_fee_addendum", "holding_fee_amount", "holding_fee_date",
    "payment_method", "max_occupants", "max_adults", "num_children",
    "pets_allowed", "pet_fee", "max_pets", "pets",
    "utilities_tenant", "utilities_landlord", "utilities_provided_by_owner_city",
    "parking_spaces", "parking_small_vehicles", "parking_large_trucks",
    "garage_spaces", "offstreet_parking_spots", "shared_parking_arrangement",
    "include_keys_clause", "has_front_door", "has_back_door",
    "front_door_keys", "back_door_keys", "garage_back_door_keys", "key_replacement_fee",
    "has_shared_driveway", "shared_driveway_with",
    "has_garage", "garage_outlets_prohibited", "has_garage_door_opener", "garage_door_opener_fee",
    "has_attic", "attic_usage", "has_basement", "appliances_provided",
    "snow_removal_responsibility", "tenant_lawn_mowing", "tenant_snow_removal", "tenant_lawn_care",
    "lead_paint_disclosure", "lead_paint_year_built",
    "early_termination_allowed", "early_termination_notice_days", "early_termination_fee_months",
    "moveout_costs", "methamphetamine_disclosure",
    "owner_name", "owner_address", "manager_name", "manager_address", "moveout_inspection_rights",
    "notes",
}

# Columns used in LaTeX generation
LATEX_USED_COLUMNS = {
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

# System/metadata columns
SYSTEM_COLUMNS = {
    "id", "user_id", "status", "lease_version", "created_at", "updated_at", "is_active",
    "generated_pdf_document_id", "template_used",
}

def main():
    """Generate detailed column mapping"""
    logger.info("=" * 80)
    logger.info("DETAILED LEASE COLUMN MAPPING")
    logger.info("=" * 80)
    logger.info("")
    
    # Get actual table schema and data
    table = load_table(NAMESPACE, TABLE_NAME)
    current_schema = table.schema()
    schema_columns = {field.name for field in current_schema.fields}
    
    logger.info("📖 Reading table data to check which columns have values...")
    df = read_table(NAMESPACE, TABLE_NAME)
    logger.info(f"  ✅ Read {len(df)} rows")
    
    # Check unique lease IDs
    unique_lease_ids = df["id"].nunique() if "id" in df.columns else 0
    logger.info(f"  📋 Unique lease IDs: {unique_lease_ids}")
    logger.info("")
    
    # Analyze each column
    results = []
    for col in sorted(schema_columns):
        in_schema = True  # We're iterating schema columns
        user_editable = col in USER_EDITABLE_COLUMNS
        latex_used = col in LATEX_USED_COLUMNS
        is_system = col in SYSTEM_COLUMNS
        
        # Check if column has data
        has_data = False
        non_null_count = 0
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            has_data = non_null_count > 0
        
        # Determine category
        if is_system:
            category = "System"
        elif user_editable and latex_used:
            category = "User + LaTeX"
        elif user_editable:
            category = "User Only"
        elif latex_used:
            category = "LaTeX Only"
        else:
            category = "UNUSED"
        
        # Determine recommendation
        if category == "UNUSED":
            recommendation = "❌ REMOVE"
        elif not has_data and not is_system:
            if latex_used:
                recommendation = "⚠️  Keep (used in LaTeX, may be needed)"
            else:
                recommendation = "⚠️  Consider removing (no data)"
        else:
            recommendation = "✅ Keep"
        
        results.append({
            "column": col,
            "in_schema": "✅" if in_schema else "❌",
            "user_editable": "✅" if user_editable else "",
            "latex_used": "✅" if latex_used else "",
            "is_system": "✅" if is_system else "",
            "category": category,
            "has_data": "✅" if has_data else "❌",
            "non_null_count": non_null_count,
            "recommendation": recommendation
        })
    
    # Print detailed table
    logger.info("=" * 80)
    logger.info("FULL COLUMN MAPPING")
    logger.info("=" * 80)
    logger.info("")
    logger.info("| Column | Schema | User Edit | LaTeX | System | Has Data | Non-Null | Category | Recommendation |")
    logger.info("|--------|--------|-----------|-------|--------|----------|----------|----------|----------------|")
    
    for r in results:
        logger.info(f"| `{r['column']}` | {r['in_schema']} | {r['user_editable']} | {r['latex_used']} | {r['is_system']} | {r['has_data']} | {r['non_null_count']} | {r['category']} | {r['recommendation']} |")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("UNUSED COLUMNS (Candidates for Removal)")
    logger.info("=" * 80)
    
    unused = [r for r in results if r["category"] == "UNUSED"]
    if unused:
        for r in unused:
            logger.info(f"  ❌ {r['column']} (has data: {r['has_data']}, non-null: {r['non_null_count']})")
        logger.info(f"")
        logger.info(f"Total: {len(unused)} unused columns")
    else:
        logger.info("  ✅ No unused columns found")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("COLUMNS WITH NO DATA (but may be needed)")
    logger.info("=" * 80)
    
    no_data = [r for r in results if not r["has_data"] and not r["is_system"] and r["category"] != "UNUSED"]
    if no_data:
        for r in sorted(no_data, key=lambda x: (x["latex_used"] == "", x["column"])):
            latex_mark = "✅" if r["latex_used"] else ""
            logger.info(f"  {r['column']} (LaTeX: {latex_mark}, Category: {r['category']})")
        logger.info(f"")
        logger.info(f"Total: {len(no_data)} columns with no data")
    else:
        logger.info("  ✅ All columns have data")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"  Total rows: {len(df)}")
    logger.info(f"  Unique lease IDs: {unique_lease_ids}")
    logger.info(f"  Schema columns: {len(schema_columns)}")
    logger.info(f"  User-editable columns: {len(USER_EDITABLE_COLUMNS)}")
    logger.info(f"  LaTeX-used columns: {len(LATEX_USED_COLUMNS)}")
    logger.info(f"  Unused columns: {len(unused)}")
    logger.info(f"  Columns with no data: {len(no_data)}")
    logger.info("")
    logger.info("=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)
    logger.info("1. Remove unused columns: " + ", ".join([r["column"] for r in unused]))
    logger.info("2. Keep all LaTeX-used columns (even if no data currently)")
    logger.info("3. Keep all user-editable columns")
    logger.info("4. Keep all system columns")
    logger.info("=" * 80)
    
    return results, unused, no_data, unique_lease_ids

if __name__ == "__main__":
    results, unused, no_data, unique_count = main()
    logger.info("")
    logger.info("⚠️  Please review the mapping above and verify unused columns before removal.")


