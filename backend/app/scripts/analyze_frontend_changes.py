#!/usr/bin/env python3
"""
Analyze what fields need to be added to frontend and what should be removed.

1. Fields to ADD to frontend: LaTeX-used columns that are NOT user-editable
2. Fields to REMOVE from frontend: Columns in schema but NOT used in LaTeX (and not system)
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

# System/metadata columns (always keep)
SYSTEM_COLUMNS = {
    "id", "user_id", "status", "lease_version", "created_at", "updated_at", "is_active",
    "generated_pdf_document_id", "template_used",
}

def main():
    """Analyze frontend changes needed"""
    logger.info("=" * 80)
    logger.info("FRONTEND CHANGES ANALYSIS")
    logger.info("=" * 80)
    logger.info("")
    
    # Get actual table schema
    table = load_table(NAMESPACE, TABLE_NAME)
    current_schema = table.schema()
    schema_columns = {field.name for field in current_schema.fields}
    
    # 1. Fields to ADD to frontend: LaTeX-used but NOT user-editable (and not system)
    fields_to_add = []
    for col in LATEX_USED_COLUMNS:
        if col not in USER_EDITABLE_COLUMNS and col not in SYSTEM_COLUMNS:
            fields_to_add.append(col)
    
    # 2. Fields to REMOVE from frontend: User-editable but NOT used in LaTeX (and not system)
    fields_to_remove = []
    for col in USER_EDITABLE_COLUMNS:
        if col not in LATEX_USED_COLUMNS and col not in SYSTEM_COLUMNS:
            fields_to_remove.append(col)
    
    # 3. Fields to REMOVE from schema: In schema but NOT used in LaTeX (and not system)
    fields_to_remove_from_schema = []
    for col in schema_columns:
        if col not in LATEX_USED_COLUMNS and col not in SYSTEM_COLUMNS:
            fields_to_remove_from_schema.append(col)
    
    logger.info("=" * 80)
    logger.info("1. FIELDS TO ADD TO FRONTEND")
    logger.info("=" * 80)
    logger.info("(LaTeX-used but NOT user-editable, NOT system)")
    logger.info("")
    if fields_to_add:
        for col in sorted(fields_to_add):
            logger.info(f"  ➕ {col}")
        logger.info(f"")
        logger.info(f"Total: {len(fields_to_add)} fields to add")
    else:
        logger.info("  ✅ No fields need to be added")
    logger.info("")
    
    logger.info("=" * 80)
    logger.info("2. FIELDS TO REMOVE FROM FRONTEND")
    logger.info("=" * 80)
    logger.info("(User-editable but NOT used in LaTeX, NOT system)")
    logger.info("")
    if fields_to_remove:
        for col in sorted(fields_to_remove):
            logger.info(f"  ➖ {col}")
        logger.info(f"")
        logger.info(f"Total: {len(fields_to_remove)} fields to remove")
    else:
        logger.info("  ✅ No fields need to be removed")
    logger.info("")
    
    logger.info("=" * 80)
    logger.info("3. FIELDS TO REMOVE FROM SCHEMA")
    logger.info("=" * 80)
    logger.info("(In schema but NOT used in LaTeX, NOT system)")
    logger.info("")
    if fields_to_remove_from_schema:
        for col in sorted(fields_to_remove_from_schema):
            logger.info(f"  ❌ {col}")
        logger.info(f"")
        logger.info(f"Total: {len(fields_to_remove_from_schema)} fields to remove from schema")
    else:
        logger.info("  ✅ No fields need to be removed from schema")
    logger.info("")
    
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"  Fields to add to frontend: {len(fields_to_add)}")
    logger.info(f"  Fields to remove from frontend: {len(fields_to_remove)}")
    logger.info(f"  Fields to remove from schema: {len(fields_to_remove_from_schema)}")
    logger.info("=" * 80)
    
    return fields_to_add, fields_to_remove, fields_to_remove_from_schema

if __name__ == "__main__":
    to_add, to_remove, to_remove_from_schema = main()


