#!/usr/bin/env python3
"""
Migrate tenants table: remove columns and require property_id
1. Write off data to parquet
2. Convert data to new dtypes (remove columns, ensure property_id/unit_id)
3. Drop table
4. Recreate table with new schema (ordered by dtype)
5. Upload data back
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import pyarrow as pa

# Add parent directory to path
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment
if not os.getenv('LAKEKEEPER__BASE_URI'):
    env_file = backend_dir / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

from app.core.iceberg import get_catalog, read_table, load_table, table_exists, append_data
from app.core.logging import get_logger
import json

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "tenants"
REFERENCES_TABLE_NAME = "tenant_landlord_references"

def create_tenants_schema() -> pa.Schema:
    """Create PyArrow schema for tenants table WITHOUT dropped columns, ordered by dtype"""
    return pa.schema([
        # STRING fields (in Iceberg order)
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string - REQUIRED
        pa.field("unit_id", pa.string(), nullable=True),  # UUID as string - nullable
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=True),
        pa.field("phone", pa.string(), nullable=True),
        pa.field("current_address", pa.string(), nullable=True),
        pa.field("current_city", pa.string(), nullable=True),
        pa.field("current_state", pa.string(), nullable=True),
        pa.field("current_zip", pa.string(), nullable=True),
        pa.field("employer_name", pa.string(), nullable=True),
        pa.field("status", pa.string(), nullable=True),  # applicant, approved, current, former, rejected
        pa.field("notes", pa.string(), nullable=True),
        pa.field("background_check_status", pa.string(), nullable=True),  # pass, fail, pending, not_started
        
        # DECIMAL128 fields (in Iceberg order)
        pa.field("monthly_income", pa.decimal128(10, 2), nullable=True),
        
        # INT32 fields (in Iceberg order)
        pa.field("credit_score", pa.int32(), nullable=True),
        
        # DATE32 fields (in Iceberg order)
        pa.field("date_of_birth", pa.date32(), nullable=True),
        
        # JSON fields (in Iceberg order) - landlord references stored as JSON array
        pa.field("landlord_references", pa.string(), nullable=True),  # JSON string - array of landlord reference objects
        
        # TIMESTAMP fields (in Iceberg order)
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])

def main():
    print("=" * 80)
    print("Migrate Tenants Table - Remove Columns and Require property_id")
    print("=" * 80)
    print()
    
    catalog = get_catalog()
    
    # Step 1: Write off data to parquet
    print("Step 1: Writing off data to parquet...")
    if not table_exists(NAMESPACE, TABLE_NAME):
        print(f"❌ Table {TABLE_NAME} does not exist!")
        return
    
    df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Loaded {len(df)} tenants")
    
    # Save backup to /tmp (writable in Docker)
    backup_file = Path(f"/tmp/tenants_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
    df.to_parquet(backup_file, index=False)
    print(f"✅ Backup saved to: {backup_file}")
    print()
    
    # Step 2: Convert data to new dtypes (remove columns)
    print("Step 2: Converting data to new dtypes...")
    columns_to_drop = [
        'phone_secondary',
        'ssn_last_four',
        'drivers_license',
        'drivers_license_state',
        'employer_phone',
        'job_title',
        'employment_start_date',
        'emergency_contact_name',
        'emergency_contact_phone',
        'emergency_contact_relationship',
        'background_check_document_id',
        'application_document_id',
        'background_check_date',
        'has_evictions',
        'eviction_details',
        'lease_id',
        'is_deleted',
        'user_id',
        'previous_landlord_name',
        'previous_landlord_phone',
        'previous_landlord_reference',
        'previous_landlord_contacted'
    ]
    
    dropped_cols = []
    for col in columns_to_drop:
        if col in df.columns:
            dropped_cols.append(col)
            print(f"  📝 Removing {col} column")
    
    if dropped_cols:
        df = df.drop(columns=dropped_cols)
        print(f"✅ Removed columns: {', '.join(dropped_cols)}")
    else:
        print("✅ No columns to remove (already removed)")
    
    # Ensure property_id exists and is not null (required)
    if 'property_id' not in df.columns:
        print("  ➕ Adding property_id column (required)")
        df['property_id'] = None
    else:
        # Check for null property_id values
        null_property_ids = df['property_id'].isna().sum()
        if null_property_ids > 0:
            print(f"  ⚠️  Warning: {null_property_ids} tenants have null property_id")
            # For now, we'll set them to empty string and they'll need to be fixed manually
            df['property_id'] = df['property_id'].fillna('')
    
    # Ensure unit_id exists (optional)
    if 'unit_id' not in df.columns:
        print("  ➕ Adding unit_id column (optional)")
        df['unit_id'] = None
    
    # Ensure date_of_birth exists (optional)
    if 'date_of_birth' not in df.columns:
        print("  ➕ Adding date_of_birth column (optional)")
        df['date_of_birth'] = None
    
    # Ensure employer_name exists (optional)
    if 'employer_name' not in df.columns:
        print("  ➕ Adding employer_name column (optional)")
        df['employer_name'] = None
    
    # Initialize landlord_references as empty JSON array if not exists
    if 'landlord_references' not in df.columns:
        print("  ➕ Adding landlord_references column (JSON)")
        df['landlord_references'] = '[]'  # Empty JSON array
    
    # Step 2a: Migrate landlord references from separate table to JSON column
    print("Step 2a: Migrating landlord references from separate table to JSON column...")
    try:
        # First, check for legacy previous_landlord_* fields and migrate them
        legacy_refs_migrated = 0
        for idx, tenant_row in df.iterrows():
            landlord_name = tenant_row.get('previous_landlord_name')
            landlord_phone = tenant_row.get('previous_landlord_phone')
            landlord_reference = tenant_row.get('previous_landlord_reference')
            landlord_contacted = tenant_row.get('previous_landlord_contacted')
            
            # If any legacy field has data, create a reference entry
            if pd.notna(landlord_name) and str(landlord_name).strip():
                legacy_ref = {
                    'landlord_name': str(landlord_name).strip(),
                }
                if pd.notna(landlord_phone) and str(landlord_phone).strip():
                    legacy_ref['landlord_phone'] = str(landlord_phone).strip()
                if pd.notna(landlord_reference) and str(landlord_reference).strip():
                    legacy_ref['notes'] = str(landlord_reference).strip()
                # Set status based on contacted flag
                if pd.notna(landlord_contacted):
                    legacy_ref['status'] = 'pass' if landlord_contacted else 'no_info'
                else:
                    legacy_ref['status'] = 'no_info'
                
                # Get existing references or create new list
                existing_refs = df.loc[idx, 'landlord_references']
                if pd.notna(existing_refs) and existing_refs and existing_refs != '[]':
                    try:
                        refs_list = json.loads(existing_refs) if isinstance(existing_refs, str) else existing_refs
                    except:
                        refs_list = []
                else:
                    refs_list = []
                
                # Add legacy reference to the list
                refs_list.append(legacy_ref)
                df.loc[idx, 'landlord_references'] = json.dumps(refs_list)
                legacy_refs_migrated += 1
        
        if legacy_refs_migrated > 0:
            print(f"  ✅ Migrated {legacy_refs_migrated} legacy previous_landlord_* fields to JSON")
        
        # Now migrate from separate tenant_landlord_references table
        if table_exists(NAMESPACE, REFERENCES_TABLE_NAME):
            refs_df = read_table(NAMESPACE, REFERENCES_TABLE_NAME)
            print(f"  📋 Loaded {len(refs_df)} landlord references from {REFERENCES_TABLE_NAME} table")
            
            # Group references by tenant_id and convert to JSON
            tenant_refs_dict = {}
            for _, ref_row in refs_df.iterrows():
                tenant_id = ref_row.get('tenant_id')
                if not tenant_id or pd.isna(tenant_id):
                    continue
                
                # Convert reference to dict (exclude id, tenant_id, user_id, created_at, updated_at)
                contact_date = ref_row.get('contact_date')
                if pd.notna(contact_date):
                    # Convert date to string format YYYY-MM-DD
                    if isinstance(contact_date, pd.Timestamp):
                        contact_date_str = contact_date.strftime('%Y-%m-%d')
                    elif hasattr(contact_date, 'strftime'):
                        contact_date_str = contact_date.strftime('%Y-%m-%d')
                    else:
                        contact_date_str = str(contact_date)
                else:
                    contact_date_str = None
                
                ref_dict = {
                    'landlord_name': ref_row.get('landlord_name', ''),
                    'landlord_phone': ref_row.get('landlord_phone') if pd.notna(ref_row.get('landlord_phone')) else None,
                    'landlord_email': ref_row.get('landlord_email') if pd.notna(ref_row.get('landlord_email')) else None,
                    'property_address': ref_row.get('property_address') if pd.notna(ref_row.get('property_address')) else None,
                    'contact_date': contact_date_str,
                    'status': ref_row.get('status', 'no_info'),
                    'notes': ref_row.get('notes') if pd.notna(ref_row.get('notes')) else None,
                }
                
                # Remove None values to keep JSON clean
                ref_dict = {k: v for k, v in ref_dict.items() if v is not None}
                
                if tenant_id not in tenant_refs_dict:
                    tenant_refs_dict[tenant_id] = []
                tenant_refs_dict[tenant_id].append(ref_dict)
            
            # Update tenants DataFrame with JSON references (merge with existing)
            migrated_count = 0
            for tenant_id, refs_list in tenant_refs_dict.items():
                # Find tenant in DataFrame
                tenant_mask = df['id'] == tenant_id
                if tenant_mask.any():
                    # Get existing references
                    existing_refs = df.loc[tenant_mask, 'landlord_references'].iloc[0]
                    if pd.notna(existing_refs) and existing_refs and existing_refs != '[]':
                        try:
                            existing_list = json.loads(existing_refs) if isinstance(existing_refs, str) else existing_refs
                        except:
                            existing_list = []
                    else:
                        existing_list = []
                    
                    # Merge with new references (avoid duplicates by checking landlord_name)
                    existing_names = {ref.get('landlord_name') for ref in existing_list if isinstance(ref, dict)}
                    for ref in refs_list:
                        if ref.get('landlord_name') not in existing_names:
                            existing_list.append(ref)
                    
                    # Convert merged list to JSON string
                    refs_json = json.dumps(existing_list)
                    df.loc[tenant_mask, 'landlord_references'] = refs_json
                    migrated_count += 1
                    print(f"  ✅ Migrated {len(refs_list)} references for tenant {tenant_id}")
            
            print(f"✅ Migrated landlord references for {migrated_count} tenants")
            print(f"  📊 Total references migrated: {sum(len(refs) for refs in tenant_refs_dict.values())}")
        else:
            print(f"  ⏭️  {REFERENCES_TABLE_NAME} table does not exist, skipping migration")
    except Exception as e:
        print(f"  ⚠️  Warning: Could not migrate landlord references: {e}")
        print(f"  📝 Continuing with empty landlord_references for all tenants")
        # Ensure all tenants have empty JSON array
        df['landlord_references'] = '[]'
    
    print()
    
    # Ensure all required columns exist with proper types
    schema = create_tenants_schema()
    expected_columns = {field.name for field in schema}
    existing_columns = set(df.columns)
    
    # Add missing columns with default values
    for field in schema:
        if field.name not in df.columns:
            if field.nullable:
                df[field.name] = None
            else:
                if pa.types.is_string(field.type):
                    df[field.name] = ""
                elif pa.types.is_decimal128(field.type):
                    df[field.name] = 0.0
                elif pa.types.is_int32(field.type):
                    df[field.name] = 0
                elif pa.types.is_date32(field.type):
                    df[field.name] = pd.Timestamp('1970-01-01').date()
                elif pa.types.is_bool_(field.type):
                    df[field.name] = False
                elif pa.types.is_timestamp(field.type):
                    df[field.name] = None
            print(f"  ➕ Added missing column: {field.name}")
    
    # Reorder columns to match schema
    df = df[[field.name for field in schema if field.name in df.columns]]
    print(f"✅ Data prepared with {len(df)} rows and {len(df.columns)} columns")
    print()
    
    # Step 3: Drop table
    print("Step 3: Dropping existing table...")
    catalog.drop_table((*NAMESPACE, TABLE_NAME))
    print("✅ Table dropped")
    print()
    
    # Step 4: Recreate table with new schema
    print("Step 4: Recreating table with new schema...")
    catalog.create_table(identifier=(*NAMESPACE, TABLE_NAME), schema=schema)
    print("✅ Table recreated with new schema (columns removed, property_id required)")
    print()
    
    # Step 5: Prepare data for upload
    print("Step 5: Preparing data for upload...")
    print(f"✅ Prepared {len(df)} rows for upload")
    print()
    
    # Step 6: Upload data to Iceberg
    print("Step 6: Uploading data to Iceberg...")
    append_data(NAMESPACE, TABLE_NAME, df)
    print("✅ Data uploaded successfully")
    print()
    
    # Step 7: Verify upload
    print("Step 7: Verifying upload...")
    verify_df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Verified: {len(verify_df)} tenants in table")
    print(f"✅ Columns: {', '.join(verify_df.columns)}")
    
    # Verify dropped columns are gone
    for col in columns_to_drop:
        if col in verify_df.columns:
            print(f"❌ WARNING: {col} column still exists!")
        else:
            print(f"✅ Confirmed: {col} column removed")
    
    print()
    print("=" * 80)
    print("✅ Migration completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()

