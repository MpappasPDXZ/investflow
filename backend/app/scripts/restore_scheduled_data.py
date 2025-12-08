#!/usr/bin/env python3
"""
Restore scheduled financial data from CDC cache to Iceberg tables.

This script:
1. Reads the scheduled expenses and revenue data from the downloaded parquet files
2. Creates the necessary Iceberg tables if they don't exist
3. Loads the data into the tables
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
from app.core.iceberg import get_catalog

setup_logging()
logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)
WAREHOUSE_NAME = settings.LAKEKEEPER__WAREHOUSE_NAME


def create_scheduled_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for scheduled_expenses table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("expense_type", pa.string(), nullable=False),
        pa.field("item_name", pa.string(), nullable=True),
        pa.field("purchase_price", pa.decimal128(15, 2), nullable=True),
        pa.field("depreciation_rate", pa.decimal128(5, 4), nullable=True),
        pa.field("count", pa.float64(), nullable=True),
        pa.field("annual_cost", pa.decimal128(15, 2), nullable=True),
        pa.field("principal", pa.decimal128(15, 2), nullable=True),
        pa.field("interest_rate", pa.decimal128(5, 4), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
        pa.field("_cdc_timestamp", pa.timestamp("us"), nullable=True),
    ])


def create_scheduled_revenue_schema() -> pa.Schema:
    """Create PyArrow schema for scheduled_revenue table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("revenue_type", pa.string(), nullable=False),
        pa.field("item_name", pa.string(), nullable=True),
        pa.field("annual_amount", pa.decimal128(15, 2), nullable=True),
        pa.field("appreciation_rate", pa.decimal128(5, 4), nullable=True),
        pa.field("property_value", pa.decimal128(15, 2), nullable=True),
        pa.field("value_added_amount", pa.decimal128(15, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
        pa.field("_cdc_timestamp", pa.timestamp("us"), nullable=True),
    ])


def ensure_namespace(catalog):
    """Ensure the namespace exists"""
    try:
        catalog.create_namespace(NAMESPACE)
        logger.info(f"✅ Created namespace: {'.'.join(NAMESPACE)}")
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"✅ Namespace already exists: {'.'.join(NAMESPACE)}")
        else:
            raise


def create_table_if_not_exists(catalog, table_name: str, schema: pa.Schema):
    """Create table if it doesn't exist"""
    try:
        table_identifier = (*NAMESPACE, table_name)
        catalog.load_table(table_identifier)
        logger.info(f"✅ Table already exists: {'.'.join(table_identifier)}")
        return False
    except Exception:
        # Table doesn't exist, create it
        try:
            table_identifier = (*NAMESPACE, table_name)
            catalog.create_table(
                identifier=table_identifier,
                schema=schema,
            )
            logger.info(f"✅ Created table: {'.'.join(table_identifier)}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create table {table_name}: {e}")
            raise


def load_data_to_table(catalog, table_name: str, df: pd.DataFrame):
    """Load data into an Iceberg table"""
    try:
        table_identifier = (*NAMESPACE, table_name)
        table = catalog.load_table(table_identifier)
        
        # Convert timestamp columns to microseconds (Iceberg requirement)
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype('datetime64[us]')
        
        # Convert to PyArrow table
        arrow_table = pa.Table.from_pandas(df)
        
        # Cast to the table's schema
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        # Append data
        table.append(arrow_table)
        
        logger.info(f"✅ Loaded {len(df)} records into {'.'.join(table_identifier)}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to load data into {table_name}: {e}", exc_info=True)
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Restore Scheduled Financial Data to Iceberg")
    print("=" * 70)
    print()
    
    # Get catalog
    catalog = get_catalog()
    
    # Step 1: Ensure namespace exists
    print("Step 1: Ensuring namespace exists...")
    ensure_namespace(catalog)
    print()
    
    # Step 2: Load data from parquet files
    print("Step 2: Loading data from parquet files...")
    expenses_file = backend_dir / "app" / "scheduled_expenses.parquet"
    revenue_file = backend_dir / "app" / "scheduled_revenue.parquet"
    
    if not expenses_file.exists():
        print(f"❌ Expenses file not found: {expenses_file}")
        return
    
    if not revenue_file.exists():
        print(f"❌ Revenue file not found: {revenue_file}")
        return
    
    expenses_df = pd.read_parquet(expenses_file)
    revenue_df = pd.read_parquet(revenue_file)
    
    print(f"✅ Loaded {len(expenses_df)} expense records")
    print(f"✅ Loaded {len(revenue_df)} revenue records")
    print()
    
    # Step 3: Create tables if they don't exist
    print("Step 3: Creating tables...")
    create_table_if_not_exists(catalog, "scheduled_expenses", create_scheduled_expenses_schema())
    create_table_if_not_exists(catalog, "scheduled_revenue", create_scheduled_revenue_schema())
    print()
    
    # Step 4: Load data into tables
    print("Step 4: Loading data into Iceberg tables...")
    load_data_to_table(catalog, "scheduled_expenses", expenses_df)
    load_data_to_table(catalog, "scheduled_revenue", revenue_df)
    print()
    
    # Step 5: Verify data was loaded
    print("Step 5: Verifying data...")
    expenses_table = catalog.load_table((*NAMESPACE, "scheduled_expenses"))
    revenue_table = catalog.load_table((*NAMESPACE, "scheduled_revenue"))
    
    expenses_scan = expenses_table.scan()
    revenue_scan = revenue_table.scan()
    
    expenses_arrow = expenses_scan.to_arrow()
    revenue_arrow = revenue_scan.to_arrow()
    
    print(f"✅ Verified: {len(expenses_arrow)} expense records in Iceberg")
    print(f"✅ Verified: {len(revenue_arrow)} revenue records in Iceberg")
    print()
    
    print("=" * 70)
    print("✅ Data restoration complete!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  • Namespace: {'.'.join(NAMESPACE)}")
    print(f"  • Tables created: scheduled_expenses, scheduled_revenue")
    print(f"  • Expense records: {len(expenses_arrow)}")
    print(f"  • Revenue records: {len(revenue_arrow)}")
    print(f"  • Property ID: {expenses_df['property_id'].iloc[0]}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Failed to restore data: {e}", exc_info=True)
        sys.exit(1)

