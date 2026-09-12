#!/usr/bin/env python3
"""
Migration script to fix file_size column type in documents table.

This script changes file_size from int64 to int32 for better storage efficiency.
File sizes rarely exceed 2GB, so int32 (max ~2.1GB) is sufficient.

This script:
1. Backs up documents data to local parquet file
2. Reads the table and converts file_size to int32
3. Rewrites the table with the corrected schema
4. Verifies the migration
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog, table_exists, load_table, read_table

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "documents"  # Also check if it's called "document_storage"


def create_documents_schema() -> pa.Schema:
    """Create PyArrow schema for documents table with corrected file_size type"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=True),
        pa.field("unit_id", pa.string(), nullable=True),
        pa.field("tenant_id", pa.string(), nullable=True),
        pa.field("blob_location", pa.string(), nullable=False),
        pa.field("container_name", pa.string(), nullable=True),
        pa.field("blob_name", pa.string(), nullable=True),
        pa.field("file_name", pa.string(), nullable=False),
        pa.field("file_type", pa.string(), nullable=True),
        pa.field("file_size", pa.int32(), nullable=True),  # CHANGED: int64 -> int32
        pa.field("document_type", pa.string(), nullable=True),
        pa.field("document_metadata", pa.list_(pa.list_(pa.string())), nullable=True),
        pa.field("display_name", pa.string(), nullable=True),
        pa.field("uploaded_at", pa.timestamp("us"), nullable=True),
        pa.field("expires_at", pa.timestamp("us"), nullable=True),
        pa.field("is_deleted", pa.bool_(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_document_storage_schema() -> pa.Schema:
    """Create PyArrow schema for document_storage table with corrected file_size type"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("blob_location", pa.string(), nullable=False),
        pa.field("file_name", pa.string(), nullable=False),
        pa.field("file_type", pa.string(), nullable=True),
        pa.field("file_size", pa.int32(), nullable=True),  # CHANGED: int64 -> int32
        pa.field("document_type", pa.string(), nullable=True),
        pa.field("metadata", pa.string(), nullable=True),  # JSONB as string
        pa.field("uploaded_by_user_id", pa.string(), nullable=True),  # UUID as string
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("expires_at", pa.timestamp("us"), nullable=True),
    ])


def migrate_table(table_name: str, schema_func):
    """Migrate a table to fix file_size column type"""
    logger.info("=" * 80)
    logger.info(f"🔄 Migrating {table_name} table: fixing file_size column type")
    logger.info("=" * 80)
    
    try:
        catalog = get_catalog()
        table_identifier = (*NAMESPACE, table_name)
        
        if not table_exists(NAMESPACE, table_name):
            logger.warning(f"  ⚠️  {table_name} table doesn't exist, skipping")
            return
        
        # Step 1: Load table
        logger.info(f"📖 Step 1: Loading {table_name} table...")
        table = catalog.load_table(table_identifier)
        current_schema = table.schema()
        
        # Check if file_size column exists and what type it is
        file_size_field = None
        for field in current_schema.fields:
            if field.name == "file_size":
                file_size_field = field
                break
        
        if not file_size_field:
            logger.warning(f"  ⚠️  file_size column not found in {table_name}, skipping")
            return
        
        # Check if it's already int32
        from pyiceberg.types import IntegerType
        if isinstance(file_size_field.field_type, IntegerType):
            if file_size_field.field_type.precision == 32:
                logger.info(f"  ✅ file_size is already int32, no migration needed")
                return
            elif file_size_field.field_type.precision == 64:
                logger.info(f"  🔄 file_size is int64, will convert to int32")
            else:
                logger.info(f"  🔄 file_size type: {file_size_field.field_type}, will convert to int32")
        else:
            logger.info(f"  🔄 file_size type: {file_size_field.field_type}, will convert to int32")
        
        # Step 2: Backup data
        logger.info(f"💾 Step 2: Backing up {table_name} data...")
        backup_dir = Path("/tmp/iceberg_migrations")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{table_name}_backup_{timestamp}.parquet"
        
        df = read_table(NAMESPACE, table_name)
        df.to_parquet(backup_file, index=False)
        logger.info(f"  ✅ Backup saved to: {backup_file}")
        logger.info(f"  📊 Rows: {len(df)}")
        
        # Step 3: Check for file sizes that exceed int32 max (2,147,483,647 bytes = ~2GB)
        if "file_size" in df.columns:
            max_size = df["file_size"].max() if not df["file_size"].isna().all() else 0
            if pd.notna(max_size) and max_size > 2147483647:
                logger.error(f"  ❌ ERROR: Found file_size value {max_size} that exceeds int32 max (2,147,483,647)")
                logger.error(f"  ❌ Cannot migrate - some files are too large for int32")
                logger.error(f"  💡 Consider keeping int64 or using a different approach")
                return
            
            # Count nulls and non-nulls
            null_count = df["file_size"].isna().sum()
            non_null_count = len(df) - null_count
            logger.info(f"  📊 file_size stats: {non_null_count} non-null, {null_count} null values")
            if non_null_count > 0:
                logger.info(f"  📊 Max file_size: {max_size:,} bytes ({max_size / (1024*1024):.2f} MB)")
        
        # Step 4: Convert file_size to int32
        logger.info(f"🔄 Step 3: Converting file_size to int32...")
        if "file_size" in df.columns:
            # Convert to int32, handling nulls
            def to_int32(x):
                if pd.isna(x) or x is None:
                    return None
                try:
                    val = int(x)
                    # Clamp to int32 range if needed (shouldn't happen based on check above)
                    if val > 2147483647:
                        logger.warning(f"  ⚠️  Clamping file_size {val} to int32 max")
                        return 2147483647
                    if val < -2147483648:
                        logger.warning(f"  ⚠️  Clamping file_size {val} to int32 min")
                        return -2147483648
                    return val
                except (ValueError, TypeError):
                    return None
            
            df["file_size"] = df["file_size"].apply(to_int32)
            logger.info(f"  ✅ Converted file_size column to int32")
        
        # Step 5: Get target schema
        target_schema = schema_func()
        
        # Step 6: Ensure all columns match schema
        logger.info(f"🔧 Step 4: Aligning DataFrame with target schema...")
        schema_field_names = {field.name for field in target_schema}
        
        # Add missing columns with None
        for field in target_schema:
            if field.name not in df.columns:
                df[field.name] = None
                logger.info(f"  ➕ Added missing column: {field.name}")
        
        # Remove extra columns (shouldn't happen, but be safe)
        columns_to_remove = [col for col in df.columns if col not in schema_field_names]
        if columns_to_remove:
            logger.warning(f"  ⚠️  Removing columns not in schema: {columns_to_remove}")
            df = df.drop(columns=columns_to_remove)
        
        # Reorder columns to match schema
        schema_column_order = [field.name for field in target_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Step 7: Convert timestamps
        logger.info(f"🕐 Step 5: Converting timestamp columns...")
        for col in ['created_at', 'updated_at', 'uploaded_at', 'expires_at']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors='coerce').dt.tz_localize(None).dt.floor('us')
        
        # Step 8: Convert to PyArrow and overwrite
        logger.info(f"💾 Step 6: Rewriting table with corrected schema...")
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        arrow_table = arrow_table.cast(target_schema)
        
        # Overwrite the table (this creates new parquet files with corrected schema)
        table.overwrite(arrow_table)
        
        logger.info(f"  ✅ Successfully rewrote {len(df)} rows with int32 file_size")
        
        # Step 9: Verify
        logger.info(f"✅ Step 7: Verifying migration...")
        verify_table = catalog.load_table(table_identifier)
        verify_schema = verify_table.schema()
        
        # Check file_size type
        for field in verify_schema.fields:
            if field.name == "file_size":
                from pyiceberg.types import IntegerType
                if isinstance(field.field_type, IntegerType):
                    if field.field_type.precision == 32:
                        logger.info(f"  ✅ Verified: file_size is now int32")
                    else:
                        logger.warning(f"  ⚠️  file_size is still {field.field_type}")
                else:
                    logger.warning(f"  ⚠️  file_size type: {field.field_type}")
                break
        
        verify_df = read_table(NAMESPACE, table_name)
        logger.info(f"  ✅ Verification: Table has {len(verify_df)} rows")
        logger.info(f"  ✅ Columns: {len(verify_df.columns)}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ Migration completed successfully!")
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"❌ Error migrating {table_name}: {e}", exc_info=True)
        raise


def main():
    """Main migration function"""
    logger.info("=" * 80)
    logger.info("Migration: Fix file_size column type (int64 -> int32)")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This migration fixes the file_size column type in file-related tables")
    logger.info("to use int32 instead of int64 for better storage efficiency.")
    logger.info("")
    
    # Try both table names (documents and document_storage)
    tables_to_migrate = []
    
    if table_exists(NAMESPACE, "documents"):
        tables_to_migrate.append(("documents", create_documents_schema))
        logger.info("  ✅ Found 'documents' table")
    
    if table_exists(NAMESPACE, "document_storage"):
        tables_to_migrate.append(("document_storage", create_document_storage_schema))
        logger.info("  ✅ Found 'document_storage' table")
    
    if not tables_to_migrate:
        logger.warning("  ⚠️  No file-related tables found (documents or document_storage)")
        logger.warning("  ⚠️  Migration will be skipped")
        return
    
    logger.info("")
    
    # Migrate each table
    for table_name, schema_func in tables_to_migrate:
        try:
            migrate_table(table_name, schema_func)
        except Exception as e:
            logger.error(f"❌ Failed to migrate {table_name}: {e}", exc_info=True)
            logger.error("  💡 Check the backup file and restore if needed")
            raise
    
    logger.info("=" * 80)
    logger.info("✅ All migrations completed successfully!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()




