"""
Create Iceberg document metadata table

This table stores metadata for all documents (receipts, leases, screenings, etc.) 
stored in Azure Data Lake Storage (ADLS).
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.iceberg import get_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    StringType, TimestampType, LongType, BooleanType, NestedField, MapType
)
from pyiceberg.table import Table
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import YearTransform

def create_document_metadata_table():
    """Create the document_metadata Iceberg table"""
    
    # Load the catalog using app's get_catalog
    catalog = get_catalog()
    
    namespace = "investflow"
    table_name = "document_metadata"
    full_table_name = f"{namespace}.{table_name}"
    
    # Define the schema
    schema = Schema(
        NestedField(1, "id", StringType(), required=True, doc="Document UUID"),
        NestedField(2, "user_id", StringType(), required=True, doc="User who uploaded the document"),
        NestedField(3, "property_id", StringType(), required=False, doc="Associated property ID (optional)"),
        NestedField(4, "unit_id", StringType(), required=False, doc="Associated unit ID (optional)"),
        NestedField(5, "blob_location", StringType(), required=True, doc="Full ADLS blob path"),
        NestedField(6, "container_name", StringType(), required=True, doc="Azure storage container"),
        NestedField(7, "blob_name", StringType(), required=True, doc="Blob name/path within container"),
        NestedField(8, "file_name", StringType(), required=True, doc="Original filename"),
        NestedField(9, "file_type", StringType(), required=True, doc="MIME type (e.g., application/pdf, image/jpeg)"),
        NestedField(10, "file_size", LongType(), required=True, doc="File size in bytes"),
        NestedField(11, "document_type", StringType(), required=True, doc="Type: receipt, lease, screening, invoice, other"),
        NestedField(12, "document_metadata", MapType(13, StringType(), 14, StringType(), value_required=False), required=False, doc="Additional metadata (OCR text, tags, etc.)"),
        NestedField(15, "uploaded_at", TimestampType(), required=True, doc="Upload timestamp"),
        NestedField(16, "expires_at", TimestampType(), required=False, doc="Expiration timestamp (if applicable)"),
        NestedField(17, "is_deleted", BooleanType(), required=True, doc="Soft delete flag"),
        NestedField(18, "created_at", TimestampType(), required=True, doc="Record creation timestamp"),
        NestedField(19, "updated_at", TimestampType(), required=True, doc="Last update timestamp"),
    )
    
    # Define partition spec - partition by year of upload for efficient querying
    partition_spec = PartitionSpec(
        PartitionField(source_id=15, field_id=1000, transform=YearTransform(), name="upload_year")
    )
    
    # Check if table exists
    try:
        existing_table = catalog.load_table(full_table_name)
        print(f"✅ Table {full_table_name} already exists")
        print(f"Schema: {existing_table.schema()}")
        return existing_table
    except Exception:
        print(f"Table {full_table_name} does not exist, creating...")
    
    # Create the table
    try:
        table = catalog.create_table(
            identifier=full_table_name,
            schema=schema,
            partition_spec=partition_spec,
            properties={
                "write.format.default": "parquet",
                "write.parquet.compression-codec": "snappy",
            }
        )
        print(f"✅ Created table: {full_table_name}")
        print(f"Schema: {table.schema()}")
        print(f"Partition spec: {table.spec()}")
        return table
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        raise

if __name__ == "__main__":
    try:
        create_document_metadata_table()
        print("\n✅ Document metadata table created successfully!")
    except Exception as e:
        print(f"\n❌ Failed to create document metadata table: {e}")
        sys.exit(1)

