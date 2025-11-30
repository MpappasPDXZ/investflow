"""
Create Iceberg expenses table with unit_id support

This script creates the expenses table in Iceberg with all necessary fields including unit_id.
"""
import sys
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    StringType, TimestampType, DoubleType, DateType, BooleanType, NestedField
)
from pyiceberg.table import Table
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import YearTransform

def create_expenses_table():
    """Create the expenses Iceberg table"""
    
    # Load the catalog
    catalog = load_catalog("default")
    
    namespace = "investflow"
    table_name = "expenses"
    full_table_name = f"{namespace}.{table_name}"
    
    # Define the schema
    schema = Schema(
        NestedField(1, "id", StringType(), required=True, doc="Expense UUID"),
        NestedField(2, "property_id", StringType(), required=True, doc="Property ID"),
        NestedField(3, "unit_id", StringType(), required=False, doc="Optional unit ID for multi-unit properties"),
        NestedField(4, "description", StringType(), required=True, doc="Expense description"),
        NestedField(5, "date", DateType(), required=True, doc="Date of expense"),
        NestedField(6, "amount", DoubleType(), required=True, doc="Expense amount"),
        NestedField(7, "vendor", StringType(), required=False, doc="Vendor name"),
        NestedField(8, "expense_type", StringType(), required=True, doc="Expense type (capex, pandi, utilities, maintenance, insurance, property_management, other)"),
        NestedField(9, "document_storage_id", StringType(), required=False, doc="Link to receipt/invoice document"),
        NestedField(10, "is_planned", BooleanType(), required=True, doc="True if planned expense, false if actual"),
        NestedField(11, "notes", StringType(), required=False, doc="Additional notes"),
        NestedField(12, "created_by_user_id", StringType(), required=True, doc="User who created the expense"),
        NestedField(13, "created_at", TimestampType(), required=True, doc="Record creation timestamp"),
        NestedField(14, "updated_at", TimestampType(), required=True, doc="Last update timestamp"),
    )
    
    # Define partition spec - partition by year of expense date for efficient queries
    partition_spec = PartitionSpec(
        PartitionField(source_id=5, field_id=1000, transform=YearTransform(), name="expense_year")
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
        create_expenses_table()
        print("\n✅ Expenses table created successfully!")
    except Exception as e:
        print(f"\n❌ Failed to create expenses table: {e}")
        sys.exit(1)

