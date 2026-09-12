#!/usr/bin/env python3
"""
Migration script to change pet_description to pets column and ensure pets/moveout_costs handled like tenants

This script:
1. Backs up leases data to parquet file
2. Drops the leases table
3. Recreates 'leases' table with new schema:
   - Change: pet_description -> pets (string/JSON column, like tenants)
   - Ensure: pets, moveout_costs, tenants all use string/JSON dtype (like tenants)
4. Migrates data from pet_description to pets format
5. Converts and loads data back

IMPORTANT: Run this inside Docker:
    docker-compose exec backend python3 app/scripts/migrate_pets_to_json_column.py
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

from app.core.iceberg import get_catalog, read_table, load_table, table_exists, append_data
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
LEASES_TABLE = "leases"
BACKUP_FILE = Path("/tmp/leases_backup_pets_migration.parquet")


def create_new_leases_schema() -> pa.Schema:
    """Create new PyArrow schema for leases table with pets as JSON column (like tenants)"""
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
        pa.field("lease_start", pa.date32(), nullable=False),
        pa.field("lease_end", pa.date32(), nullable=False),
        pa.field("auto_convert_month_to_month", pa.bool_(), nullable=True),
        
        # Financial Terms
        pa.field("monthly_rent", pa.decimal128(10, 2), nullable=False),
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
        pa.field("holding_fee_amount", pa.decimal128(10, 2), nullable=True),
        pa.field("holding_fee_date", pa.string(), nullable=True),
        
        # Utilities
        pa.field("utilities_tenant", pa.string(), nullable=True),
        pa.field("utilities_landlord", pa.string(), nullable=True),
        
        # Pets - CHANGED: pet_description -> pets (string/JSON like tenants)
        pa.field("pet_fee", pa.decimal128(10, 2), nullable=True),
        pa.field("pets", pa.string(), nullable=True),  # JSON string like tenants
        
        # Parking
        pa.field("garage_spaces", pa.decimal128(3, 1), nullable=True),
        pa.field("key_replacement_fee", pa.decimal128(10, 2), nullable=True),
        pa.field("shared_driveway_with", pa.string(), nullable=True),
        pa.field("garage_door_opener_fee", pa.decimal128(10, 2), nullable=True),
        
        # Appliances
        pa.field("appliances_provided", pa.string(), nullable=True),
        
        # Early Termination
        pa.field("early_termination_fee_amount", pa.decimal128(10, 2), nullable=True),
        
        # Move-out costs - string/JSON like tenants
        pa.field("moveout_costs", pa.string(), nullable=True),  # JSON string like tenants
        
        # Owner/Manager
        pa.field("owner_name", pa.string(), nullable=True),
        pa.field("manager_name", pa.string(), nullable=True),
        pa.field("manager_address", pa.string(), nullable=True),
        
        # PDF/Document
        pa.field("generated_pdf_document_id", pa.string(), nullable=True),
        pa.field("template_used", pa.string(), nullable=True),
        
        # Tenants - string/JSON
        pa.field("tenants", pa.string(), nullable=True),  # JSON string
        
        # Notes
        pa.field("notes", pa.string(), nullable=True),
        
        # Booleans
        pa.field("include_holding_fee_addendum", pa.bool_(), nullable=True),
        pa.field("has_shared_driveway", pa.bool_(), nullable=True),
        pa.field("tenant_lawn_mowing", pa.bool_(), nullable=True),
        pa.field("tenant_snow_removal", pa.bool_(), nullable=True),
        pa.field("tenant_lawn_care", pa.bool_(), nullable=True),
        pa.field("has_garage_door_opener", pa.bool_(), nullable=True),
        pa.field("lead_paint_disclosure", pa.bool_(), nullable=True),
        pa.field("early_termination_allowed", pa.bool_(), nullable=True),
        pa.field("disclosure_methamphetamine", pa.bool_(), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
        
        # Integers
        pa.field("rent_due_day", pa.int32(), nullable=True),
        pa.field("rent_due_by_day", pa.int32(), nullable=True),
        pa.field("max_occupants", pa.int32(), nullable=True),
        pa.field("max_adults", pa.int32(), nullable=True),
        pa.field("offstreet_parking_spots", pa.int32(), nullable=True),
        pa.field("front_door_keys", pa.int32(), nullable=True),
        pa.field("back_door_keys", pa.int32(), nullable=True),
        pa.field("garage_back_door_keys", pa.int32(), nullable=True),
        pa.field("disclosure_lead_paint", pa.int32(), nullable=True),
        pa.field("early_termination_notice_days", pa.int32(), nullable=True),
        pa.field("early_termination_fee_months", pa.int32(), nullable=True),
        
        # Timestamps
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def convert_pet_description_to_pets(leases_df: pd.DataFrame) -> pd.DataFrame:
    """Convert pet_description JSON to pets JSON format"""
    logger.info("  🔄 Converting pet_description to pets format...")
    
    def convert_pet_description(pet_desc_json):
        """Convert old pet_description format to new pets format"""
        if pd.isna(pet_desc_json) or not pet_desc_json:
            return None
        
        try:
            # Parse old format: [{"pet_type": "dog", "breed": "Golden", "pet_name": "George", "weight": "100"}]
            pet_descriptions = json.loads(pet_desc_json) if isinstance(pet_desc_json, str) else pet_desc_json
            
            if not pet_descriptions or not isinstance(pet_descriptions, list):
                return None
            
            # Convert to new format: [{"type": "dog", "breed": "Golden", "name": "George", "weight": "100", "isEmotionalSupport": false}]
            pets = []
            for pet_desc in pet_descriptions:
                pet = {
                    "type": pet_desc.get("pet_type", pet_desc.get("type", "")),
                    "breed": pet_desc.get("breed"),
                    "name": pet_desc.get("pet_name", pet_desc.get("name")),
                    "weight": pet_desc.get("weight"),
                    "isEmotionalSupport": pet_desc.get("isEmotionalSupport", False)
                }
                pets.append(pet)
            
            return json.dumps(pets) if pets else None
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning(f"    ⚠️  Error converting pet_description: {e}")
            return None
    
    # Convert pet_description to pets
    if 'pet_description' in leases_df.columns:
        leases_df['pets'] = leases_df['pet_description'].apply(convert_pet_description)
        logger.info(f"  ✅ Converted {leases_df['pets'].notna().sum()} pet_description records to pets")
    else:
        leases_df['pets'] = None
        logger.info("  ⏭️  No pet_description column found, setting pets to None")
    
    return leases_df


def ensure_json_strings(leases_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure pets, moveout_costs, and tenants are JSON strings (not objects)"""
    logger.info("  🔄 Ensuring JSON columns are strings...")
    
    # Ensure pets is a JSON string
    if 'pets' in leases_df.columns:
        def ensure_pets_string(pets_val):
            if pd.isna(pets_val) or pets_val is None:
                return None
            if isinstance(pets_val, str):
                return pets_val
            if isinstance(pets_val, (list, dict)):
                return json.dumps(pets_val)
            return None
        leases_df['pets'] = leases_df['pets'].apply(ensure_pets_string)
    
    # Ensure moveout_costs is a JSON string
    if 'moveout_costs' in leases_df.columns:
        def ensure_moveout_costs_string(costs_val):
            if pd.isna(costs_val) or costs_val is None:
                return None
            if isinstance(costs_val, str):
                return costs_val
            if isinstance(costs_val, (list, dict)):
                return json.dumps(costs_val)
            return None
        leases_df['moveout_costs'] = leases_df['moveout_costs'].apply(ensure_moveout_costs_string)
    
    # Ensure tenants is a JSON string
    if 'tenants' in leases_df.columns:
        def ensure_tenants_string(tenants_val):
            if pd.isna(tenants_val) or tenants_val is None:
                return None
            if isinstance(tenants_val, str):
                return tenants_val
            if isinstance(tenants_val, (list, dict)):
                return json.dumps(tenants_val)
            return None
        leases_df['tenants'] = leases_df['tenants'].apply(ensure_tenants_string)
    
    logger.info("  ✅ All JSON columns are now strings")
    return leases_df


def drop_and_recreate_table():
    """Drop and recreate leases table with new schema"""
    logger.info("  🔄 Dropping and recreating leases table...")
    
    catalog = get_catalog()
    table_identifier = (*NAMESPACE, LEASES_TABLE)
    
    try:
        # Drop existing table
        if table_exists(NAMESPACE, LEASES_TABLE):
            table = catalog.load_table(table_identifier)
            catalog.drop_table(table_identifier)
            logger.info("  ✅ Dropped existing leases table")
        else:
            logger.warning("  ⚠️  Leases table doesn't exist, will create new one")
    except Exception as e:
        logger.error(f"  ❌ Error dropping table: {e}")
        raise
    
    # Create new table with updated schema
    try:
        new_schema = create_new_leases_schema()
        # PyIceberg accepts PyArrow schema directly
        catalog.create_table(
            identifier=table_identifier,
            schema=new_schema
        )
        logger.info("  ✅ Created new leases table with pets column (replacing pet_description)")
    except Exception as e:
        logger.error(f"  ❌ Error creating table: {e}")
        raise


def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("🔄 Migrating leases table: pet_description -> pets (JSON column like tenants)")
    logger.info("=" * 80)
    
    try:
        # Step 1: Backup data (or load from existing backup if table doesn't exist)
        logger.info("\n📦 Step 1: Backing up leases data...")
        if not table_exists(NAMESPACE, LEASES_TABLE):
            logger.warning("  ⚠️  Leases table doesn't exist!")
            if BACKUP_FILE.exists():
                logger.info(f"  📖 Loading from existing backup: {BACKUP_FILE}")
                leases_df = pd.read_parquet(BACKUP_FILE)
                logger.info(f"  ✅ Loaded {len(leases_df)} lease records from backup")
            else:
                logger.error("  ❌ No table and no backup file found!")
                return
        else:
            leases_df = read_table(NAMESPACE, LEASES_TABLE)
            logger.info(f"  ✅ Read {len(leases_df)} lease records")
            
            # Save to parquet
            leases_df.to_parquet(BACKUP_FILE, index=False)
            logger.info(f"  ✅ Backed up to {BACKUP_FILE}")
        
        # Step 2: Convert data
        logger.info("\n🔄 Step 2: Converting pet_description to pets format...")
        leases_df = convert_pet_description_to_pets(leases_df)
        leases_df = ensure_json_strings(leases_df)
        
        # Step 3: Drop and recreate table
        logger.info("\n🔄 Step 3: Dropping and recreating table...")
        drop_and_recreate_table()
        
        # Step 4: Prepare data for new schema
        logger.info("\n🔄 Step 4: Preparing data for new schema...")
        new_schema = create_new_leases_schema()
        schema_columns = [field.name for field in new_schema]
        
        # Reindex to match new schema (adds missing columns, removes extra ones)
        leases_df = leases_df.reindex(columns=schema_columns)
        
        # Remove pet_description column if it exists
        if 'pet_description' in leases_df.columns:
            leases_df = leases_df.drop(columns=['pet_description'])
            logger.info("  ✅ Removed pet_description column")
        
        # Step 5: Load data back
        logger.info("\n📤 Step 5: Loading data back into new table...")
        append_data(NAMESPACE, LEASES_TABLE, leases_df)
        logger.info(f"  ✅ Loaded {len(leases_df)} lease records")
        
        # Step 6: Verify
        logger.info("\n✅ Step 6: Verifying migration...")
        verify_df = read_table(NAMESPACE, LEASES_TABLE)
        logger.info(f"  ✅ Verified: {len(verify_df)} records in new table")
        
        # Check pets column
        if 'pets' in verify_df.columns:
            pets_count = verify_df['pets'].notna().sum()
            logger.info(f"  ✅ Pets column: {pets_count} records with data")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        logger.info("\n📝 Summary of changes:")
        logger.info("     - Changed: pet_description -> pets (string/JSON column)")
        logger.info("     - Ensured: pets, moveout_costs, tenants all use string/JSON dtype")
        logger.info(f"     - Migrated: {len(leases_df)} lease records")
        
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
        logger.error("\n💾 Backup file saved at: " + str(BACKUP_FILE))
        logger.error("   You can restore from backup if needed.")
        raise


if __name__ == "__main__":
    main()

