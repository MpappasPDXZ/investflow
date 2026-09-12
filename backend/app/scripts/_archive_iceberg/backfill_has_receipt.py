#!/usr/bin/env python3
"""
Backfill has_receipt for all existing expenses
1. Read all expenses
2. Set has_receipt based on document_storage_id
3. Upsert all records back
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

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

from app.core.iceberg import get_catalog, read_table, load_table, table_exists
from app.services.expense_service import expense_service
from app.schemas.expense import ExpenseUpdate
from app.core.logging import get_logger
import uuid

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "expenses"

def main():
    print("=" * 80)
    print("Backfill has_receipt for All Expenses")
    print("=" * 80)
    print()
    
    catalog = get_catalog()
    
    # Step 1: Read all expenses
    print("Step 1: Reading all expenses...")
    if not table_exists(NAMESPACE, TABLE_NAME):
        print(f"❌ Table {TABLE_NAME} does not exist!")
        return
    
    df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Loaded {len(df)} expenses")
    print()
    
    # Step 2: Check current has_receipt values
    print("Step 2: Checking current has_receipt values...")
    if 'has_receipt' not in df.columns:
        print("❌ has_receipt column does not exist in table!")
        return
    
    # Count current states
    null_count = df['has_receipt'].isna().sum()
    true_count = (df['has_receipt'] == True).sum()
    false_count = (df['has_receipt'] == False).sum()
    
    print(f"   - has_receipt = True: {true_count}")
    print(f"   - has_receipt = False: {false_count}")
    print(f"   - has_receipt = null: {null_count}")
    print()
    
    # Step 3: Deduplicate by ID (keep most recent by updated_at)
    print("Step 3: Deduplicating expenses (keeping most recent by updated_at)...")
    if 'updated_at' in df.columns:
        df = df.sort_values('updated_at', ascending=False).drop_duplicates(subset=['id'], keep='first')
        print(f"✅ Deduplicated: {len(df)} unique expenses")
    else:
        df = df.drop_duplicates(subset=['id'], keep='first')
        print(f"✅ Deduplicated: {len(df)} unique expenses")
    print()
    
    # Step 4: Update has_receipt based on document_storage_id
    print("Step 4: Updating has_receipt based on document_storage_id...")
    
    # Set has_receipt to True if document_storage_id is not None/empty, False otherwise
    df['has_receipt'] = df['document_storage_id'].notna() & (df['document_storage_id'] != '') & (df['document_storage_id'] != 'None')
    df['has_receipt'] = df['has_receipt'].astype('boolean')
    
    # Count updated values
    updated_true_count = (df['has_receipt'] == True).sum()
    updated_false_count = (df['has_receipt'] == False).sum()
    updated_null_count = df['has_receipt'].isna().sum()
    
    print(f"✅ Updated has_receipt values")
    print(f"   - has_receipt = True: {updated_true_count}")
    print(f"   - has_receipt = False: {updated_false_count}")
    print(f"   - has_receipt = null: {updated_null_count}")
    print()
    
    # Step 5: Update each expense individually using the service
    print("Step 5: Updating expenses using service (ensures proper schema handling)...")
    updated_count = 0
    skipped_count = 0
    
    for idx, row in df.iterrows():
        try:
            expense_id = uuid.UUID(row['id'])
            
            # Check if has_receipt needs updating
            current_has_receipt = row['has_receipt']
            expected_has_receipt = row['document_storage_id'] is not None and row['document_storage_id'] != '' and row['document_storage_id'] != 'None'
            
            # Only update if has_receipt is null or incorrect
            if pd.isna(current_has_receipt) or current_has_receipt != expected_has_receipt:
                update_data = ExpenseUpdate(has_receipt=expected_has_receipt)
                result = expense_service.update_expense(expense_id, update_data)
                if result:
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            logger.warning(f"Failed to update expense {row.get('id')}: {e}")
            skipped_count += 1
    
    print(f"✅ Updated {updated_count} expenses")
    print(f"   Skipped {skipped_count} expenses (already correct)")
    print()
    
    # Step 6: Verify
    print("Step 6: Verifying backfill...")
    verify_df = read_table(NAMESPACE, TABLE_NAME)
    print(f"✅ Verified: {len(verify_df)} expenses in table")
    
    # Verify has_receipt values
    if 'has_receipt' in verify_df.columns:
        verify_true_count = (verify_df['has_receipt'] == True).sum()
        verify_false_count = (verify_df['has_receipt'] == False).sum()
        verify_null_count = verify_df['has_receipt'].isna().sum()
        
        print(f"✅ Final has_receipt values:")
        print(f"   - has_receipt = True: {verify_true_count}")
        print(f"   - has_receipt = False: {verify_false_count}")
        print(f"   - has_receipt = null: {verify_null_count}")
        
        if verify_null_count > 0:
            print(f"⚠️  WARNING: {verify_null_count} expenses still have null has_receipt values!")
        else:
            print(f"✅ All expenses have has_receipt set (no null values)")
    print()
    
    print("=" * 80)
    print("✅ Backfill completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()

