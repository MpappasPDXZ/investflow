#!/usr/bin/env python3
"""
Analyze which columns are used in the LaTeX lease generator vs which exist in the schema.

This script:
1. Extracts all columns used in lease_generator_service.py
2. Compares with the schema in create_data.py
3. Identifies unused columns
4. Provides a report for verification
"""
import sys
from pathlib import Path
import re

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.scripts.create_data import create_leases_schema
import pyarrow as pa

# Columns used in LaTeX generator (extracted from lease_generator_service.py)
USED_COLUMNS = {
    # Primary identifiers (always needed)
    "id", "user_id", "property_id", "unit_id",
    
    # Status
    "status", "lease_version", "state",
    
    # Dates
    "lease_date", "commencement_date", "termination_date", "auto_convert_month_to_month", "signed_date",
    
    # Financial Terms
    "monthly_rent", "rent_due_day", "rent_due_by_day", "rent_due_by_time", "payment_method", 
    "prorated_first_month_rent", "show_prorated_rent",
    
    # Late Charges
    "late_fee_day_1_10", "late_fee_day_11", "late_fee_day_16", "late_fee_day_21",
    
    # Insufficient Funds
    "nsf_fee",
    
    # Security Deposit
    "security_deposit", "deposit_return_days",
    
    # Holding Fee (used in LaTeX)
    "include_holding_fee_addendum", "holding_fee_amount", "holding_fee_date",
    
    # Occupants
    "max_occupants", "max_adults", "max_children",
    
    # Utilities
    "utilities_tenant", "utilities_landlord", "utilities_provided_by_owner_city",
    
    # Pets
    "pets_allowed", "pet_fee_one", "pet_fee_two", "pet_deposit_total", "pet_description", 
    "max_pets", "pet_fee", "pets",
    
    # Parking
    "parking_spaces", "parking_small_vehicles", "parking_large_trucks", 
    "garage_spaces", "offstreet_parking_spots",
    
    # Keys
    "front_door_keys", "back_door_keys", "garage_back_door_keys", "key_replacement_fee",
    
    # Shared Driveway
    "has_shared_driveway", "shared_driveway_with", "snow_removal_responsibility",
    
    # Garage
    "has_garage", "garage_outlets_prohibited", "has_garage_door_opener", "garage_door_opener_fee",
    
    # Special Spaces
    "has_attic", "attic_usage", "has_basement",
    
    # Appliances
    "appliances_provided",
    
    # Lead Paint
    "lead_paint_disclosure", "lead_paint_year_built",
    
    # Early Termination
    "early_termination_allowed", "early_termination_notice_days", "early_termination_fee_months", 
    "early_termination_fee_amount",
    
    # Move-Out Costs
    "moveout_costs",
    
    # Missouri-Specific
    "methamphetamine_disclosure", "owner_name", "owner_address", "manager_name", 
    "manager_address", "deposit_account_info", "moveout_inspection_rights", "military_termination_days",
    
    # Tenant Responsibilities (used in LaTeX)
    "tenant_lawn_mowing", "tenant_snow_removal", "tenant_lawn_care",
    
    # Document References
    "generated_pdf_document_id", "template_used",
    
    # Metadata (always needed for system)
    "notes", "created_at", "updated_at", "is_active",
}

def main():
    """Analyze columns"""
    print("=" * 70)
    print("LEASE COLUMN ANALYSIS")
    print("=" * 70)
    print()
    
    # Get schema columns
    schema = create_leases_schema()
    schema_columns = {field.name for field in schema}
    
    print(f"📊 Schema has {len(schema_columns)} columns")
    print(f"📊 LaTeX generator uses {len(USED_COLUMNS)} columns")
    print()
    
    # Find unused columns
    unused_columns = schema_columns - USED_COLUMNS
    
    # Find columns used but not in schema (shouldn't happen, but check)
    missing_columns = USED_COLUMNS - schema_columns
    
    print("=" * 70)
    print("UNUSED COLUMNS (in schema but not used in LaTeX)")
    print("=" * 70)
    if unused_columns:
        for col in sorted(unused_columns):
            print(f"  ❌ {col}")
        print()
        print(f"Total: {len(unused_columns)} unused columns")
    else:
        print("  ✅ No unused columns found")
    print()
    
    if missing_columns:
        print("=" * 70)
        print("⚠️  MISSING COLUMNS (used in LaTeX but not in schema)")
        print("=" * 70)
        for col in sorted(missing_columns):
            print(f"  ⚠️  {col}")
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Schema columns: {len(schema_columns)}")
    print(f"  Used columns: {len(USED_COLUMNS)}")
    print(f"  Unused columns: {len(unused_columns)}")
    print(f"  Missing columns: {len(missing_columns)}")
    print()
    print("=" * 70)
    
    return unused_columns

if __name__ == "__main__":
    unused = main()
    print()
    print("⚠️  Please verify the unused columns list above.")
    print("   These columns will be removed from the schema if approved.")

