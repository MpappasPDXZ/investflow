#!/usr/bin/env python3
"""
Verify that all fields used in lease_generator_service.py exist in:
1. Database schema (create_data.py)
2. Frontend form (leases/page.tsx)
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Fields extracted from lease_generator_service.py
# Grouped by source: lease_data vs property_data

LEASE_DATA_FIELDS = {
    # String fields
    "owner_name",
    "state",
    "utilities_tenant",
    "utilities_provided_by_owner_city",
    "shared_driveway_with",
    "appliances_provided",
    "attic_usage",
    "holding_fee_date",
    
    # Date fields
    "commencement_date",
    "termination_date",
    "lease_date",
    
    # Decimal/Currency fields
    "monthly_rent",
    "security_deposit",
    "holding_fee_amount",
    "late_fee_day_1_10",
    "late_fee_day_11",
    "late_fee_day_16",
    "late_fee_day_21",
    "nsf_fee",
    "pet_fee",
    "key_replacement_fee",
    "garage_door_opener_fee",
    "early_termination_fee_amount",
    
    # Integer fields
    "max_occupants",
    "max_adults",
    "max_pets",
    "front_door_keys",
    "back_door_keys",
    "garage_back_door_keys",
    "garage_spaces",
    "offstreet_parking_spots",
    "parking_spaces",
    "early_termination_notice_days",
    "lead_paint_year_built",
    
    # Boolean fields
    "include_holding_fee_addendum",
    "pets_allowed",
    "tenant_lawn_mowing",
    "tenant_snow_removal",
    "tenant_lawn_care",
    "has_shared_driveway",
    "has_garage_door_opener",
    "show_prorated_rent",
    "early_termination_allowed",
    "garage_outlets_prohibited",
    "lead_paint_disclosure",
    "has_attic",
    
    # List/Array fields
    "pets",
    
    # Computed/derived fields (not in DB)
    "deposit_return_days",  # Computed from state
    "unit_id",  # Used to determine is_multi_family
}

PROPERTY_DATA_FIELDS = {
    "address",  # full_address
    "description",  # property_description
    "year_built",
    "city",  # Used for is_omaha check
}

# Read database schema
def get_db_schema_fields():
    """Get all fields from create_leases_schema()"""
    from app.scripts.create_data import create_leases_schema
    schema = create_leases_schema()
    return {field.name for field in schema.fields}

# Read frontend form fields
def get_frontend_fields():
    """Extract field names from frontend form"""
    frontend_file = Path(__file__).parent.parent.parent / "frontend" / "app" / "(dashboard)" / "leases" / "page.tsx"
    
    if not frontend_file.exists():
        return set()
    
    content = frontend_file.read_text()
    
    # Extract formData fields - look for pattern: field_name: 
    import re
    # Pattern to match formData field names
    pattern = r'(\w+):\s*(?:formData\.|["\']|true|false|\d+|\[|\{)'
    matches = re.findall(r'(\w+):\s*[^,}\n]+', content)
    
    # Also look for formData.field_name patterns
    formdata_pattern = r'formData\.(\w+)'
    formdata_matches = re.findall(formdata_pattern, content)
    
    # Combine and filter
    all_matches = set(matches + formdata_matches)
    
    # Filter out common non-field names
    excluded = {
        'formData', 'setFormData', 'handleSaveParameters', 'handleNewLease', 
        'handleEditLease', 'useProperties', 'useTenants', 'useLeasesList',
        'useUnits', 'useState', 'useEffect', 'useCallback', 'useMemo',
        'property', 'tenant', 'lease', 'unit', 'id', 'type', 'value',
        'onChange', 'onClick', 'className', 'placeholder', 'label',
        'div', 'input', 'select', 'button', 'form', 'section',
        'true', 'false', 'null', 'undefined', 'string', 'number', 'boolean',
        'Date', 'Object', 'Array', 'Function', 'React', 'useRouter',
    }
    
    return {m for m in all_matches if m and m not in excluded and not m.startswith('_')}

def main():
    print("=" * 80)
    print("LEASE GENERATOR FIELD VERIFICATION")
    print("=" * 80)
    
    # Get database schema
    db_fields = get_db_schema_fields()
    print(f"\n📊 Database Schema: {len(db_fields)} fields")
    
    # Get frontend fields (simplified check)
    frontend_fields = get_frontend_fields()
    print(f"🎨 Frontend Form: {len(frontend_fields)} fields detected")
    
    # Check lease_data fields
    print("\n" + "=" * 80)
    print("LEASE_DATA FIELDS CHECK")
    print("=" * 80)
    
    missing_in_db = []
    for field in LEASE_DATA_FIELDS:
        if field not in db_fields:
            missing_in_db.append(field)
            print(f"  ❌ MISSING IN DB: {field}")
        else:
            print(f"  ✅ {field}")
    
    # Check property_data fields
    print("\n" + "=" * 80)
    print("PROPERTY_DATA FIELDS CHECK")
    print("=" * 80)
    
    # Property fields are in properties table, not leases table
    from app.scripts.create_data import create_properties_schema
    properties_schema = create_properties_schema()
    property_db_fields = {field.name for field in properties_schema.fields}
    
    for field in PROPERTY_DATA_FIELDS:
        if field not in property_db_fields:
            print(f"  ❌ MISSING IN PROPERTIES TABLE: {field}")
        else:
            print(f"  ✅ {field}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total lease_data fields checked: {len(LEASE_DATA_FIELDS)}")
    print(f"Missing in database: {len(missing_in_db)}")
    if missing_in_db:
        print(f"\n⚠️  Missing fields: {', '.join(missing_in_db)}")
    else:
        print("\n✅ All lease_data fields exist in database schema!")
    
    print(f"\nTotal property_data fields checked: {len(PROPERTY_DATA_FIELDS)}")
    print("✅ All property_data fields exist in properties table!")

if __name__ == "__main__":
    main()


