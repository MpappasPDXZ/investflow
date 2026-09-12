#!/usr/bin/env python3
"""
Generate a comprehensive mapping of lease columns showing:
1. User-editable columns (from frontend form)
2. Columns used in LaTeX generation
3. Columns in database schema
4. System/metadata columns (not user-editable)

Outputs a markdown table for easy review.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import load_table
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "leases_full"

# Columns user can edit in the frontend form (from page.tsx formData state)
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

# Columns used in LaTeX generation (from lease_generator_service.py)
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

# System/metadata columns (not user-editable, managed by system)
SYSTEM_COLUMNS = {
    "id", "user_id", "status", "lease_version", "created_at", "updated_at", "is_active",
    "generated_pdf_document_id", "template_used",
}

def main():
    """Generate column mapping"""
    logger.info("=" * 70)
    logger.info("GENERATING LEASE COLUMN MAPPING")
    logger.info("=" * 70)
    logger.info("")
    
    # Get actual table schema
    table = load_table(NAMESPACE, TABLE_NAME)
    current_schema = table.schema()
    schema_columns = {field.name for field in current_schema.fields}
    
    # Combine all columns
    all_columns = schema_columns | USER_EDITABLE_COLUMNS | LATEX_USED_COLUMNS
    
    # Categorize each column
    mapping = []
    for col in sorted(all_columns):
        in_schema = col in schema_columns
        user_editable = col in USER_EDITABLE_COLUMNS
        latex_used = col in LATEX_USED_COLUMNS
        is_system = col in SYSTEM_COLUMNS
        
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
            category = "Unused"
        
        mapping.append({
            "column": col,
            "in_schema": in_schema,
            "user_editable": user_editable,
            "latex_used": latex_used,
            "is_system": is_system,
            "category": category
        })
    
    # Print markdown table
    logger.info("## Lease Column Mapping")
    logger.info("")
    logger.info("| Column | In Schema | User Editable | Used in LaTeX | System | Category |")
    logger.info("|--------|-----------|---------------|---------------|--------|----------|")
    
    for m in mapping:
        schema_mark = "✅" if m["in_schema"] else "❌"
        user_mark = "✅" if m["user_editable"] else ""
        latex_mark = "✅" if m["latex_used"] else ""
        system_mark = "✅" if m["is_system"] else ""
        category = m["category"]
        
        logger.info(f"| `{m['column']}` | {schema_mark} | {user_mark} | {latex_mark} | {system_mark} | {category} |")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY BY CATEGORY")
    logger.info("=" * 70)
    
    # Count by category
    category_counts = {}
    for m in mapping:
        cat = m["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    for cat, count in sorted(category_counts.items()):
        logger.info(f"  {cat}: {count} columns")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("UNUSED COLUMNS (not user-editable, not in LaTeX, not system)")
    logger.info("=" * 70)
    
    unused = [m for m in mapping if m["category"] == "Unused" and m["in_schema"]]
    if unused:
        for m in unused:
            logger.info(f"  ❌ {m['column']}")
        logger.info(f"")
        logger.info(f"Total: {len(unused)} unused columns in schema")
    else:
        logger.info("  ✅ No unused columns found")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("MISSING COLUMNS (used but not in schema)")
    logger.info("=" * 70)
    
    missing = [m for m in mapping if (m["user_editable"] or m["latex_used"]) and not m["in_schema"]]
    if missing:
        for m in missing:
            logger.info(f"  ⚠️  {m['column']} ({m['category']})")
        logger.info(f"")
        logger.info(f"Total: {len(missing)} missing columns")
    else:
        logger.info("  ✅ All used columns exist in schema")
    
    logger.info("")
    logger.info("=" * 70)
    
    return mapping, unused, missing

if __name__ == "__main__":
    mapping, unused, missing = main()


