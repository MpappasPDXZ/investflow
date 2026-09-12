#!/usr/bin/env python3
"""
Migration script to merge lease_tenants into leases_full and restructure schema

This script:
1. Backs up leases_full and lease_tenants data to parquet files
2. Merges tenant data from lease_tenants into leases_full as JSON
3. Drops both tables
4. Recreates 'leases' table (renamed from leases_full) with new schema:
   - Add tenants JSON column (from lease_tenants)
   - Remove: user_id, utilities_provided_by_owner_city, pets, pets_allowed, max_children, max_pets,
             parking_spaces, parking_small_vehicles, parking_large_trucks, military_termination_days
   - Restructure pets: pet_fee (amount), pet_description (JSON with pet_type, breed, pet_name, weight)
   - Rename: snow_removal_responsibility -> tenant_snow_removal
   - Rename: lead_paint_year_built -> disclosure_lead_paint
   - Rename: methamphetamine_disclosure -> disclosure_methamphetamine
   - Set defaults: owner_name = "S&M Axios Heartland Holdings, LLC"
   - Merge: owner_address + manager_address -> manager_address (default: "1606 S 208th St., Elkhorn, NE 68022")
   - Set default: manager_name = "Sarah Pappas"
5. Converts and loads data back

IMPORTANT: Run this inside Docker:
    docker-compose exec backend python3 app/scripts/migrate_leases_merge_tenants.py
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

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
OLD_LEASES_TABLE = "leases_full"
OLD_TENANTS_TABLE = "lease_tenants"
NEW_LEASES_TABLE = "leases"
LEASES_BACKUP_FILE = Path("/tmp/leases_full_backup.parquet")
TENANTS_BACKUP_FILE = Path("/tmp/lease_tenants_backup.parquet")


def create_new_leases_schema() -> pa.Schema:
    """Create new PyArrow schema for leases table with merged tenants and updated fields"""
    return pa.schema([
        # Primary identifiers
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("unit_id", pa.string(), nullable=True),
        
        # Status
        pa.field("status", pa.string(), nullable=False),
        pa.field("lease_number", pa.int32(), nullable=False),
        pa.field("lease_version", pa.int32(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        
        # Dates
        pa.field("lease_date", pa.date32(), nullable=True),
        pa.field("lease_start", pa.date32(), nullable=False),  # RENAMED from commencement_date
        pa.field("lease_end", pa.date32(), nullable=False),  # RENAMED from termination_date
        pa.field("auto_convert_month_to_month", pa.bool_(), nullable=True),
        
        # Financial Terms
        pa.field("monthly_rent", pa.decimal128(10, 2), nullable=False),
        pa.field("rent_due_day", pa.int32(), nullable=False),
        pa.field("rent_due_by_day", pa.int32(), nullable=False),
        pa.field("rent_due_by_time", pa.string(), nullable=True),
        pa.field("payment_method", pa.string(), nullable=True),
        pa.field("prorated_first_month_rent", pa.decimal128(10, 2), nullable=True),
        pa.field("show_prorated_rent", pa.bool_(), nullable=True),
        
        # Late Charges
        pa.field("late_fee_day_1_10", pa.decimal128(10, 2), nullable=True),
        pa.field("late_fee_day_11", pa.decimal128(10, 2), nullable=True),
        pa.field("late_fee_day_16", pa.decimal128(10, 2), nullable=True),
        pa.field("late_fee_day_21", pa.decimal128(10, 2), nullable=True),
        
        # Insufficient Funds
        pa.field("nsf_fee", pa.decimal128(10, 2), nullable=True),
        
        # Security Deposit
        pa.field("security_deposit", pa.decimal128(10, 2), nullable=False),
        
        # Holding Fee
        pa.field("include_holding_fee_addendum", pa.bool_(), nullable=True),
        pa.field("holding_fee_amount", pa.decimal128(10, 2), nullable=True),
        pa.field("holding_fee_date", pa.string(), nullable=True),
        
        # Occupants (max_children REMOVED)
        pa.field("max_occupants", pa.int32(), nullable=True),
        pa.field("max_adults", pa.int32(), nullable=True),
        
        # Utilities (utilities_provided_by_owner_city REMOVED)
        pa.field("utilities_tenant", pa.string(), nullable=True),
        pa.field("utilities_landlord", pa.string(), nullable=True),
        
        # Pets (restructured: pets_allowed, max_pets, pets REMOVED)
        pa.field("pet_fee", pa.decimal128(10, 2), nullable=True),  # Amount only
        pa.field("pet_description", pa.string(), nullable=True),  # JSON: [{pet_type, breed, pet_name, weight}]
        
        # Parking (parking_spaces, parking_small_vehicles, parking_large_trucks REMOVED)
        pa.field("garage_spaces", pa.decimal128(3, 1), nullable=True),  # Supports .5 increments
        pa.field("offstreet_parking_spots", pa.int32(), nullable=True),
        
        # Keys
        pa.field("front_door_keys", pa.int32(), nullable=True),
        pa.field("back_door_keys", pa.int32(), nullable=True),
        pa.field("garage_back_door_keys", pa.int32(), nullable=True),  # 3rd door (garage back door)
        pa.field("key_replacement_fee", pa.decimal128(10, 2), nullable=True),
        
        # Shared Driveway
        pa.field("has_shared_driveway", pa.bool_(), nullable=True),
        pa.field("shared_driveway_with", pa.string(), nullable=True),
        
        # Tenant Maintenance Responsibilities
        pa.field("tenant_lawn_mowing", pa.bool_(), nullable=True),
        pa.field("tenant_snow_removal", pa.bool_(), nullable=True),  # RENAMED from snow_removal_responsibility (was string, now boolean)
        pa.field("tenant_lawn_care", pa.bool_(), nullable=True),
        
        # Garage
        pa.field("has_garage_door_opener", pa.bool_(), nullable=True),  # Garage door opener available
        pa.field("garage_door_opener_fee", pa.decimal128(10, 2), nullable=True),  # Replacement fee for garage door opener
        
        # Appliances
        pa.field("appliances_provided", pa.string(), nullable=True),
        
        # Lead Paint (RENAMED)
        pa.field("lead_paint_disclosure", pa.bool_(), nullable=True),
        pa.field("disclosure_lead_paint", pa.int32(), nullable=True),  # RENAMED from lead_paint_year_built
        
        # Early Termination
        pa.field("early_termination_allowed", pa.bool_(), nullable=True),
        pa.field("early_termination_notice_days", pa.int32(), nullable=True),
        pa.field("early_termination_fee_months", pa.int32(), nullable=True),
        pa.field("early_termination_fee_amount", pa.decimal128(10, 2), nullable=True),
        
        # Move-Out Costs
        pa.field("moveout_costs", pa.string(), nullable=True),
        
        # Missouri-Specific (military_termination_days REMOVED)
        pa.field("disclosure_methamphetamine", pa.bool_(), nullable=True),  # RENAMED from methamphetamine_disclosure
        pa.field("owner_name", pa.string(), nullable=True),  # Default: "S&M Axios Heartland Holdings, LLC"
        pa.field("manager_name", pa.string(), nullable=True),  # Default: "Sarah Pappas"
        pa.field("manager_address", pa.string(), nullable=True),  # Default: "1606 S 208th St., Elkhorn, NE 68022"
        
        # Document References
        pa.field("generated_pdf_document_id", pa.string(), nullable=True),
        pa.field("template_used", pa.string(), nullable=True),
        
        # Tenants (NEW JSON column)
        pa.field("tenants", pa.string(), nullable=True),  # JSON array of tenant objects
        
        # Metadata
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def backup_tables():
    """Backup both tables to local parquet files"""
    logger.info(f"📦 Step 1: Backing up tables...")
    
    # Backup leases_full
    if table_exists(NAMESPACE, OLD_LEASES_TABLE):
        logger.info(f"  📖 Backing up {OLD_LEASES_TABLE}...")
        leases_df = read_table(NAMESPACE, OLD_LEASES_TABLE)
        if leases_df is not None and not leases_df.empty:
            leases_df.to_parquet(LEASES_BACKUP_FILE, index=False)
            logger.info(f"    ✅ Saved {len(leases_df)} rows to {LEASES_BACKUP_FILE}")
        else:
            logger.info(f"    ℹ️  {OLD_LEASES_TABLE} is empty")
            leases_df = None
    else:
        logger.warning(f"    ⚠️  {OLD_LEASES_TABLE} does not exist")
        leases_df = None
    
    # Backup lease_tenants
    if table_exists(NAMESPACE, OLD_TENANTS_TABLE):
        logger.info(f"  📖 Backing up {OLD_TENANTS_TABLE}...")
        tenants_df = read_table(NAMESPACE, OLD_TENANTS_TABLE)
        if tenants_df is not None and not tenants_df.empty:
            tenants_df.to_parquet(TENANTS_BACKUP_FILE, index=False)
            logger.info(f"    ✅ Saved {len(tenants_df)} rows to {TENANTS_BACKUP_FILE}")
        else:
            logger.info(f"    ℹ️  {OLD_TENANTS_TABLE} is empty")
            tenants_df = None
    else:
        logger.warning(f"    ⚠️  {OLD_TENANTS_TABLE} does not exist")
        tenants_df = None
    
    return leases_df, tenants_df


def merge_tenant_data(leases_df: pd.DataFrame, tenants_df: pd.DataFrame) -> pd.DataFrame:
    """Merge tenant data from lease_tenants into leases as JSON"""
    logger.info(f"📋 Step 2: Merging tenant data into leases...")
    
    if tenants_df is None or tenants_df.empty:
        logger.info(f"  ℹ️  No tenant data to merge")
        leases_df['tenants'] = None
        return leases_df
    
    # Group tenants by lease_id
    tenants_by_lease = {}
    for _, tenant in tenants_df.iterrows():
        lease_id = tenant['lease_id']
        if lease_id not in tenants_by_lease:
            tenants_by_lease[lease_id] = []
        
        # Build tenant object
        tenant_obj = {
            'id': tenant.get('id'),
            'tenant_order': int(tenant.get('tenant_order', 0)) if pd.notna(tenant.get('tenant_order')) else 0,
            'first_name': tenant.get('first_name', ''),
            'last_name': tenant.get('last_name', ''),
            'email': tenant.get('email'),
            'phone': tenant.get('phone'),
            'signed_date': str(tenant.get('signed_date')) if pd.notna(tenant.get('signed_date')) else None,
        }
        tenants_by_lease[lease_id].append(tenant_obj)
    
    # Sort tenants by tenant_order
    for lease_id in tenants_by_lease:
        tenants_by_lease[lease_id].sort(key=lambda x: x.get('tenant_order', 0))
    
    logger.info(f"  ✅ Found tenants for {len(tenants_by_lease)} leases")
    
    # Add tenants JSON column to leases
    def get_tenants_json(lease_id):
        if lease_id in tenants_by_lease:
            return json.dumps(tenants_by_lease[lease_id])
        return None
    
    leases_df['tenants'] = leases_df['id'].apply(get_tenants_json)
    
    logger.info(f"  ✅ Merged tenant data into leases")
    return leases_df


def convert_pet_data(leases_df: pd.DataFrame) -> pd.DataFrame:
    """Convert pet data to new structure"""
    logger.info(f"🐾 Step 3: Converting pet data...")
    
    # Convert pets JSON to pet_description JSON
    if 'pets' in leases_df.columns:
        def convert_pets_to_description(pets_json):
            if pd.isna(pets_json) or not pets_json:
                return None
            
            try:
                pets = json.loads(pets_json) if isinstance(pets_json, str) else pets_json
                if not pets:
                    return None
                
                # Convert to new format: [{pet_type, breed, pet_name, weight}]
                pet_descriptions = []
                for pet in pets:
                    pet_desc = {
                        'pet_type': pet.get('type', 'other'),  # dog, cat, or other
                        'breed': pet.get('breed'),
                        'pet_name': pet.get('name'),
                        'weight': pet.get('weight')
                    }
                    pet_descriptions.append(pet_desc)
                
                return json.dumps(pet_descriptions) if pet_descriptions else None
            except:
                return None
        
        leases_df['pet_description'] = leases_df['pets'].apply(convert_pets_to_description)
        logger.info(f"  ✅ Converted pets to pet_description JSON")
    else:
        leases_df['pet_description'] = None
    
    # pet_fee already exists, keep it as is
    
    return leases_df


def drop_and_recreate_table():
    """Drop old tables and create new one with updated schema"""
    logger.info(f"🔄 Step 4: Dropping and recreating tables...")
    
    catalog = get_catalog()
    
    # Drop old tables if they exist
    if table_exists(NAMESPACE, OLD_LEASES_TABLE):
        logger.info(f"  🗑️  Dropping {OLD_LEASES_TABLE}...")
        catalog.drop_table(f"{NAMESPACE[0]}.{OLD_LEASES_TABLE}")
        logger.info(f"    ✅ Dropped {OLD_LEASES_TABLE}")
    
    if table_exists(NAMESPACE, OLD_TENANTS_TABLE):
        logger.info(f"  🗑️  Dropping {OLD_TENANTS_TABLE}...")
        catalog.drop_table(f"{NAMESPACE[0]}.{OLD_TENANTS_TABLE}")
        logger.info(f"    ✅ Dropped {OLD_TENANTS_TABLE}")
    
    # Check if new table already exists
    if table_exists(NAMESPACE, NEW_LEASES_TABLE):
        logger.info(f"  🗑️  Dropping existing {NEW_LEASES_TABLE}...")
        catalog.drop_table(f"{NAMESPACE[0]}.{NEW_LEASES_TABLE}")
        logger.info(f"    ✅ Dropped existing {NEW_LEASES_TABLE}")
    
    # Create new table with updated schema
    logger.info(f"  📝 Creating {NEW_LEASES_TABLE} table with updated schema...")
    schema = create_new_leases_schema()
    catalog.create_table(
        identifier=f"{NAMESPACE[0]}.{NEW_LEASES_TABLE}",
        schema=schema
    )
    logger.info(f"    ✅ Created {NEW_LEASES_TABLE} table")
    
    # Log schema changes
    logger.info(f"  📋 Schema changes:")
    logger.info(f"     - Added: tenants (JSON column)")
    logger.info(f"     - Removed: user_id, utilities_provided_by_owner_city, pets, pets_allowed, max_children, max_pets")
    logger.info(f"     - Removed: parking_spaces, parking_small_vehicles, parking_large_trucks")
    logger.info(f"     - Removed: military_termination_days")
    logger.info(f"     - Removed: garage_outlets_prohibited, has_garage, has_attic, attic_usage, has_basement, moveout_inspection_rights")
    logger.info(f"     - Restructured: pet_fee (amount), pet_description (JSON)")
    logger.info(f"     - Renamed: snow_removal_responsibility (string) -> tenant_snow_removal (boolean)")
    logger.info(f"     - Renamed: lead_paint_year_built -> disclosure_lead_paint")
    logger.info(f"     - Renamed: methamphetamine_disclosure -> disclosure_methamphetamine")
    logger.info(f"     - Renamed: commencement_date -> lease_start")
    logger.info(f"     - Renamed: termination_date -> lease_end")
    logger.info(f"     - Removed: signed_date")
    logger.info(f"     - Merged: owner_address + manager_address -> manager_address")


def convert_and_load_data(leases_df: pd.DataFrame):
    """Convert data to match new schema and load it back"""
    if leases_df is None or leases_df.empty:
        logger.info(f"📋 Step 5: No data to load (table was empty)")
        return
    
    logger.info(f"📋 Step 5: Converting and loading data back...")
    
    # Get new schema field names
    new_schema = create_new_leases_schema()
    new_field_names = [f.name for f in new_schema]
    
    # Create new DataFrame with only fields that exist in new schema
    new_df = pd.DataFrame()
    
    for field_name in new_field_names:
        # Handle renamed fields
        if field_name == "tenant_snow_removal":
            # Renamed from snow_removal_responsibility (convert string to boolean)
            if "snow_removal_responsibility" in leases_df.columns:
                # Convert string to boolean: if it exists and is truthy, set to True
                new_df[field_name] = leases_df["snow_removal_responsibility"].notna() & (leases_df["snow_removal_responsibility"] != "")
            elif "tenant_snow_removal" in leases_df.columns:
                # Keep existing boolean value if it exists
                new_df[field_name] = leases_df["tenant_snow_removal"]
            else:
                new_df[field_name] = None
        elif field_name == "disclosure_lead_paint":
            # Renamed from lead_paint_year_built
            if "lead_paint_year_built" in leases_df.columns:
                new_df[field_name] = leases_df["lead_paint_year_built"]
            else:
                new_df[field_name] = None
        elif field_name == "disclosure_methamphetamine":
            # Renamed from methamphetamine_disclosure
            if "methamphetamine_disclosure" in leases_df.columns:
                new_df[field_name] = leases_df["methamphetamine_disclosure"]
            else:
                new_df[field_name] = None
        elif field_name == "manager_address":
            # Merge owner_address and manager_address
            if "manager_address" in leases_df.columns:
                new_df[field_name] = leases_df["manager_address"]
            elif "owner_address" in leases_df.columns:
                new_df[field_name] = leases_df["owner_address"]
            else:
                new_df[field_name] = "1606 S 208th St., Elkhorn, NE 68022"  # Default
        elif field_name in leases_df.columns:
            new_df[field_name] = leases_df[field_name]
        else:
            # Set defaults for new fields
            if field_name == "owner_name":
                new_df[field_name] = "S&M Axios Heartland Holdings, LLC"
            elif field_name == "manager_name":
                new_df[field_name] = "Sarah Pappas"
            elif field_name == "manager_address":
                new_df[field_name] = "1606 S 208th St., Elkhorn, NE 68022"
            else:
                new_df[field_name] = None
    
    # Ensure DataFrame columns are in exact order matching new schema
    new_df = new_df[new_field_names]
    
    # Convert timestamp columns to microseconds (required, non-nullable)
    for col in ['created_at', 'updated_at']:
        if col in new_df.columns:
            new_df[col] = pd.to_datetime(new_df[col], utc=True).dt.tz_localize(None)
            new_df[col] = new_df[col].dt.floor('us')
            new_df[col] = new_df[col].fillna(pd.Timestamp.now().floor('us'))
    
    # Convert date columns (handle renamed fields)
    date_cols = ['lease_date', 'lease_start', 'lease_end']
    for col in date_cols:
        if col in new_df.columns:
            new_df[col] = pd.to_datetime(new_df[col]).dt.date
            if col == 'lease_start' or col == 'lease_end':
                new_df[col] = new_df[col].fillna(date.today())
    
    # Handle renamed date fields from old schema
    if 'commencement_date' in leases_df.columns and 'lease_start' not in new_df.columns:
        new_df['lease_start'] = pd.to_datetime(leases_df['commencement_date']).dt.date
        new_df['lease_start'] = new_df['lease_start'].fillna(date.today())
    if 'termination_date' in leases_df.columns and 'lease_end' not in new_df.columns:
        new_df['lease_end'] = pd.to_datetime(leases_df['termination_date']).dt.date
        new_df['lease_end'] = new_df['lease_end'].fillna(date.today())
    
    # Convert integer columns
    int_cols = ['lease_number', 'lease_version', 'rent_due_day', 'rent_due_by_day',
                'max_occupants', 'max_adults', 'offstreet_parking_spots',
                'front_door_keys', 'back_door_keys', 'garage_back_door_keys',
                'early_termination_notice_days', 'early_termination_fee_months',
                'disclosure_lead_paint']
    for col in int_cols:
        if col in new_df.columns:
            if col in ['lease_number', 'lease_version', 'rent_due_day', 'rent_due_by_day']:
                new_df[col] = pd.to_numeric(new_df[col], errors='coerce').fillna(1).astype(int)
            else:
                new_df[col] = pd.to_numeric(new_df[col], errors='coerce').astype('Int64')
    
    # Convert boolean columns
    bool_cols = ['auto_convert_month_to_month', 'show_prorated_rent',
                 'include_holding_fee_addendum', 'has_shared_driveway',
                 'tenant_lawn_mowing', 'tenant_snow_removal', 'tenant_lawn_care',
                 'has_garage_door_opener',
                 'lead_paint_disclosure', 'early_termination_allowed',
                 'disclosure_methamphetamine', 'is_active']
    for col in bool_cols:
        if col in new_df.columns:
            if col == 'is_active':
                new_df[col] = new_df[col].fillna(True).astype(bool)
            else:
                new_df[col] = new_df[col].astype('boolean')
    
    # Convert string columns (required fields must not be nullable)
    string_cols = ['id', 'property_id', 'status', 'state']
    for col in string_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].astype(str)
            new_df[col] = new_df[col].fillna('')
    
    # Convert decimal columns with proper precision
    decimal_cols = ['monthly_rent', 'prorated_first_month_rent',
                    'late_fee_day_1_10', 'late_fee_day_11', 'late_fee_day_16', 'late_fee_day_21',
                    'nsf_fee', 'security_deposit', 'holding_fee_amount',
                    'pet_fee', 'key_replacement_fee', 'garage_door_opener_fee',
                    'early_termination_fee_amount', 'garage_spaces']
    for col in decimal_cols:
        if col in new_df.columns:
            if col == 'garage_spaces':
                new_df[col] = new_df[col].apply(
                    lambda x: Decimal(str(round(float(x), 1))) if pd.notna(x) and x is not None else None
                )
            elif col in ['monthly_rent', 'security_deposit']:
                new_df[col] = new_df[col].apply(
                    lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else Decimal('0')
                )
            else:
                new_df[col] = new_df[col].apply(
                    lambda x: Decimal(str(round(float(x), 2))) if pd.notna(x) else None
                )
    
    logger.info(f"  ✅ Converted {len(new_df)} rows")
    
    # Load data back - use explicit schema casting
    logger.info(f"  📤 Loading data back to {NEW_LEASES_TABLE}...")
    table = load_table(NAMESPACE, NEW_LEASES_TABLE)
    table_schema = table.schema().as_arrow()
    
    # Convert to PyArrow with explicit schema
    arrow_table = pa.Table.from_pandas(new_df)
    # Cast to exact schema to ensure types match
    arrow_table = arrow_table.cast(table_schema)
    table.append(arrow_table)
    logger.info(f"  ✅ Loaded {len(new_df)} rows back to {NEW_LEASES_TABLE}")


def main():
    """Run the migration"""
    try:
        logger.info("🚀 Starting leases migration: merge tenants and restructure schema")
        logger.info("=" * 80)
        
        # Step 1: Backup tables
        leases_df, tenants_df = backup_tables()
        
        # Step 2: Merge tenant data
        if leases_df is not None and not leases_df.empty:
            leases_df = merge_tenant_data(leases_df, tenants_df)
            leases_df = convert_pet_data(leases_df)
        else:
            logger.info("  ℹ️  No lease data to process")
            leases_df = None
        
        # Step 3: Drop and recreate table
        drop_and_recreate_table()
        
        # Step 4: Convert and load data
        convert_and_load_data(leases_df)
        
        logger.info("=" * 80)
        logger.info("✅ Migration complete!")
        logger.info(f"   Backups saved to:")
        logger.info(f"     - {LEASES_BACKUP_FILE}")
        logger.info(f"     - {TENANTS_BACKUP_FILE}")
        logger.info(f"   Table {NEW_LEASES_TABLE} has been created with updated schema")
        logger.info(f"   Please review the columns before proceeding")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

