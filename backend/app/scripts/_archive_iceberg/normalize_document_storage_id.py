#!/usr/bin/env python3
"""
Script to normalize document_storage_id values in the expenses table.

This script:
1. Inspects all document_storage_id values in the expenses table
2. Normalizes them to either None (no receipt) or a valid UUID (has receipt)
3. Updates the table with normalized values

Invalid values that will be normalized to None:
- String 'None'
- Empty string ''
- Invalid UUID strings
- Any other non-UUID values
"""

import sys
import uuid
import pandas as pd
import pyarrow as pa
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.iceberg import get_catalog
from app.core.logging import get_logger

logger = get_logger(__name__)


def normalize_document_storage_id(value):
    """
    Normalize document_storage_id to either None or a valid UUID string.
    
    Returns:
        None if no valid receipt, or a UUID string if valid receipt exists
    """
    # If already None, return None
    if value is None:
        return None
    
    # If it's already a UUID object, convert to string
    if isinstance(value, uuid.UUID):
        return str(value)
    
    # If it's a string, check if it's a valid UUID
    if isinstance(value, str):
        # Handle common invalid values
        if value.lower() in ['none', 'null', '']:
            return None
        
        # Try to parse as UUID
        try:
            uuid_obj = uuid.UUID(value)
            return str(uuid_obj)
        except (ValueError, TypeError):
            # Invalid UUID string, return None
            logger.warning(f"Invalid document_storage_id value: {value}, normalizing to None")
            return None
    
    # For any other type, return None
    logger.warning(f"Unexpected document_storage_id type: {type(value)}, value: {value}, normalizing to None")
    return None


def inspect_document_storage_ids():
    """Inspect all document_storage_id values in the expenses table"""
    catalog = get_catalog()
    table = catalog.load_table("investflow.expenses")
    
    # Scan all expenses
    scan = table.scan()
    arrow_table = scan.to_arrow()
    df = pd.DataFrame(arrow_table.to_pylist())
    
    logger.info(f"Total expenses: {len(df)}")
    
    # Analyze document_storage_id values
    doc_id_col = df['document_storage_id']
    
    # Count by type/value
    value_counts = {}
    type_counts = {}
    none_count = 0
    valid_uuid_count = 0
    invalid_count = 0
    
    for idx, value in doc_id_col.items():
        # Count by type
        value_type = type(value).__name__
        type_counts[value_type] = type_counts.get(value_type, 0) + 1
        
        # Count by value (for strings)
        if isinstance(value, str):
            value_str = value.lower() if value else ''
            value_counts[value_str] = value_counts.get(value_str, 0) + 1
        
        # Categorize
        if value is None:
            none_count += 1
        elif isinstance(value, uuid.UUID):
            valid_uuid_count += 1
        elif isinstance(value, str):
            try:
                uuid.UUID(value)
                valid_uuid_count += 1
            except (ValueError, TypeError):
                invalid_count += 1
                logger.warning(f"Row {idx}: Invalid document_storage_id: {value}")
        else:
            invalid_count += 1
            logger.warning(f"Row {idx}: Unexpected type: {type(value)}, value: {value}")
    
    logger.info("\n=== Document Storage ID Analysis ===")
    logger.info(f"None values: {none_count}")
    logger.info(f"Valid UUID values: {valid_uuid_count}")
    logger.info(f"Invalid values: {invalid_count}")
    logger.info(f"\nType distribution:")
    for vtype, count in sorted(type_counts.items()):
        logger.info(f"  {vtype}: {count}")
    
    if value_counts:
        logger.info(f"\nString value distribution (first 20):")
        for val, count in sorted(value_counts.items(), key=lambda x: -x[1])[:20]:
            logger.info(f"  '{val}': {count}")
    
    return df


def normalize_all_document_storage_ids(dry_run=True):
    """
    Normalize all document_storage_id values in the expenses table.
    
    Args:
        dry_run: If True, only report what would be changed without making changes
    """
    catalog = get_catalog()
    table = catalog.load_table("investflow.expenses")
    
    # Scan all expenses
    scan = table.scan()
    arrow_table = scan.to_arrow()
    df = pd.DataFrame(arrow_table.to_pylist())
    
    logger.info(f"Processing {len(df)} expenses...")
    
    # Track changes
    changes = []
    normalized_count = 0
    
    # Normalize document_storage_id for each row
    for idx, row in df.iterrows():
        original_value = row['document_storage_id']
        normalized_value = normalize_document_storage_id(original_value)
        
        if original_value != normalized_value:
            changes.append({
                'id': row['id'],
                'original': original_value,
                'normalized': normalized_value,
                'type_original': type(original_value).__name__ if original_value is not None else 'None'
            })
            normalized_count += 1
            df.at[idx, 'document_storage_id'] = normalized_value
    
    logger.info(f"\n=== Normalization Results ===")
    logger.info(f"Total expenses: {len(df)}")
    logger.info(f"Expenses that need normalization: {normalized_count}")
    
    if changes:
        logger.info(f"\nFirst 10 changes:")
        for change in changes[:10]:
            logger.info(f"  ID {change['id']}: {change['type_original']} '{change['original']}' -> {type(change['normalized']).__name__} '{change['normalized']}'")
    
    if dry_run:
        logger.info("\n*** DRY RUN - No changes made ***")
        logger.info("Run with --apply to actually apply changes")
        return changes
    
    # Apply changes to Iceberg table by exporting, normalizing, and recreating
    logger.info("\nApplying changes to Iceberg table...")
    
    # Step 1: Export current data to parquet backup
    logger.info("Step 1: Creating backup...")
    backup_file = Path("/tmp/expenses_backup_before_normalize.parquet")
    df_backup = df.copy()
    df_backup.to_parquet(backup_file, index=False)
    logger.info(f"✅ Backup saved to: {backup_file}")
    
    # Step 2: Normalize document_storage_id in the DataFrame
    logger.info("Step 2: Normalizing document_storage_id values...")
    df['document_storage_id'] = df['document_storage_id'].apply(normalize_document_storage_id)
    logger.info(f"✅ Normalized {normalized_count} values")
    
    # Step 3: Save normalized data to parquet
    logger.info("Step 3: Saving normalized data...")
    normalized_file = Path("/tmp/expenses_normalized.parquet")
    df.to_parquet(normalized_file, index=False)
    logger.info(f"✅ Normalized data saved to: {normalized_file}")
    
    # Step 4: Get the table schema
    logger.info("Step 4: Getting table schema...")
    original_schema = arrow_table.schema
    logger.info(f"✅ Schema has {len(original_schema)} fields")
    
    # Step 5: Drop and recreate table with normalized data
    logger.info("Step 5: Recreating table with normalized data...")
    from app.core.iceberg import append_data
    
    table_path = ("investflow", "expenses")
    
    # Drop existing table
    try:
        catalog.drop_table(table_path)
        logger.info("✅ Dropped existing table")
    except Exception as e:
        logger.warning(f"Could not drop table (may not exist): {e}")
    
    # Create new table with same schema
    catalog.create_table(
        identifier=table_path,
        schema=original_schema,
        properties={"format-version": "2"}
    )
    logger.info("✅ Created new table")
    
    # Step 6: Prepare data for upload (ensure types match schema)
    logger.info("Step 6: Preparing data for upload...")
    df_upload = df.copy()
    
    # Convert types to match schema
    for field in original_schema:
        col_name = field.name
        if col_name not in df_upload.columns:
            continue
        
        field_type = field.type
        if pa.types.is_string(field_type):
            df_upload[col_name] = df_upload[col_name].astype(str).replace('None', None)
            df_upload[col_name] = df_upload[col_name].where(pd.notna(df_upload[col_name]), None)
        elif pa.types.is_date32(field_type):
            df_upload[col_name] = pd.to_datetime(df_upload[col_name]).dt.date
        elif pa.types.is_timestamp(field_type):
            df_upload[col_name] = pd.to_datetime(df_upload[col_name])
    
    # Step 7: Upload normalized data
    logger.info("Step 7: Uploading normalized data...")
    append_data(("investflow",), "expenses", df_upload)
    logger.info(f"✅ Uploaded {len(df_upload)} expenses")
    
    # Step 8: Verify
    logger.info("Step 8: Verifying...")
    verify_scan = catalog.load_table(table_path).scan()
    verify_table = verify_scan.to_arrow()
    verify_df = pd.DataFrame(verify_table.to_pylist())
    logger.info(f"✅ Verified: {len(verify_df)} expenses in table")
    
    # Check document_storage_id values
    doc_id_values = verify_df['document_storage_id']
    none_count = doc_id_values.isna().sum()
    valid_count = doc_id_values.notna().sum()
    logger.info(f"✅ document_storage_id: {none_count} None, {valid_count} valid UUIDs")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Normalization completed successfully!")
    logger.info("=" * 80)
    
    return changes


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Normalize document_storage_id values in expenses table")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (default: True)")
    parser.add_argument("--apply", action="store_true", help="Apply changes (overrides --dry-run)")
    parser.add_argument("--inspect-only", action="store_true", help="Only inspect, don't normalize")
    
    args = parser.parse_args()
    
    if args.inspect_only:
        logger.info("=== INSPECTION MODE ===")
        inspect_document_storage_ids()
    else:
        dry_run = not args.apply
        logger.info(f"=== NORMALIZATION MODE (dry_run={dry_run}) ===")
        
        # First inspect
        logger.info("Step 1: Inspecting current state...")
        inspect_document_storage_ids()
        
        # Then normalize
        logger.info("\nStep 2: Normalizing values...")
        normalize_all_document_storage_ids(dry_run=dry_run)

