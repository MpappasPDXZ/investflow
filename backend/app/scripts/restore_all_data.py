#!/usr/bin/env python3
"""
Restore ALL data from old Iceberg snapshots to new Iceberg tables.

This script restores:
- Users
- Properties
- Clients
- Expenses (transactions)
- Rents
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa
from decimal import Decimal

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.iceberg import get_catalog

setup_logging()
logger = get_logger(__name__)

NAMESPACE = ("investflow",)


def create_users_schema() -> pa.Schema:
    """Create PyArrow schema for users table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=False),
        pa.field("password_hash", pa.string(), nullable=False),
        pa.field("tax_rate", pa.decimal128(5, 2), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_properties_schema() -> pa.Schema:
    """Create PyArrow schema for properties table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("display_name", pa.string(), nullable=False),
        pa.field("address_line1", pa.string(), nullable=False),
        pa.field("city", pa.string(), nullable=False),
        pa.field("state_province", pa.string(), nullable=False),
        pa.field("postal_code", pa.string(), nullable=False),
        pa.field("country", pa.string(), nullable=True),
        pa.field("purchase_date", pa.date32(), nullable=True),
        pa.field("purchase_price", pa.decimal128(15, 2), nullable=True),
        pa.field("square_footage", pa.int32(), nullable=True),
        pa.field("num_bedrooms", pa.int32(), nullable=True),
        pa.field("num_bathrooms", pa.decimal128(3, 1), nullable=True),
        pa.field("property_type", pa.string(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_clients_schema() -> pa.Schema:
    """Create PyArrow schema for clients table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=True),
        pa.field("phone", pa.string(), nullable=True),
        pa.field("lease_start_date", pa.date32(), nullable=True),
        pa.field("lease_end_date", pa.date32(), nullable=True),
        pa.field("monthly_rent", pa.decimal128(10, 2), nullable=True),
        pa.field("security_deposit", pa.decimal128(10, 2), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for expenses table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("expense_type", pa.string(), nullable=False),
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("date", pa.date32(), nullable=False),
        pa.field("description", pa.string(), nullable=True),
        pa.field("vendor", pa.string(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_rents_schema() -> pa.Schema:
    """Create PyArrow schema for rents table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),
        pa.field("property_id", pa.string(), nullable=False),
        pa.field("client_id", pa.string(), nullable=False),
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("rent_period_start", pa.date32(), nullable=False),
        pa.field("rent_period_end", pa.date32(), nullable=False),
        pa.field("payment_date", pa.date32(), nullable=True),
        pa.field("payment_method", pa.string(), nullable=True),
        pa.field("is_paid", pa.bool_(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_table_if_not_exists(catalog, table_name: str, schema: pa.Schema):
    """Create table if it doesn't exist"""
    try:
        table_identifier = (*NAMESPACE, table_name)
        catalog.load_table(table_identifier)
        logger.info(f"✅ Table already exists: {'.'.join(table_identifier)}")
        return False
    except Exception:
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
    if len(df) == 0:
        logger.info(f"⚠️  No data to load for {table_name}")
        return
    
    try:
        table_identifier = (*NAMESPACE, table_name)
        table = catalog.load_table(table_identifier)
        table_schema = table.schema().as_arrow()
        
        # Add missing columns with appropriate defaults
        df_copy = df.copy()
        for field in table_schema:
            if field.name not in df_copy.columns:
                # Provide defaults for required (non-nullable) fields
                if not field.nullable:
                    if pa.types.is_string(field.type):
                        default_val = "UNKNOWN"
                    elif pa.types.is_integer(field.type):
                        default_val = 0
                    elif pa.types.is_floating(field.type) or pa.types.is_decimal(field.type):
                        default_val = 0.0
                    elif pa.types.is_boolean(field.type):
                        default_val = True
                    elif pa.types.is_date(field.type):
                        default_val = pd.Timestamp('2000-01-01').date()
                    else:
                        default_val = ""
                    logger.info(f"  Adding missing required column '{field.name}' with default: {default_val}")
                else:
                    default_val = None
                    logger.info(f"  Adding missing column '{field.name}' with null values")
                df_copy[field.name] = default_val
        
        # Reorder columns to match schema
        df_copy = df_copy[[field.name for field in table_schema]]
        
        # Convert timestamp columns to microseconds
        for col in df_copy.columns:
            if df_copy[col].dtype == 'datetime64[ns]':
                df_copy[col] = df_copy[col].astype('datetime64[us]')
        
        # Convert to PyArrow table
        arrow_table = pa.Table.from_pandas(df_copy)
        
        # Cast to the table's schema
        arrow_table = arrow_table.cast(table_schema)
        
        # Append data
        table.append(arrow_table)
        
        logger.info(f"✅ Loaded {len(df_copy)} records into {'.'.join(table_identifier)}")
    except Exception as e:
        logger.error(f"❌ Failed to load data into {table_name}: {e}", exc_info=True)
        raise


def main():
    """Main function"""
    print("=" * 70)
    print("Restore ALL Data from Old Iceberg Snapshots")
    print("=" * 70)
    print()
    
    catalog = get_catalog()
    
    # Load all data files
    print("Step 1: Loading data from old Iceberg snapshots...")
    data_files = {
        'users': backend_dir / "app" / "users_old.parquet",
        'properties': backend_dir / "app" / "properties_old.parquet",
        'clients': backend_dir / "app" / "clients_old.parquet",
        'expenses': backend_dir / "app" / "expenses_old.parquet",
        'rents': backend_dir / "app" / "rents_old.parquet",
    }
    
    data = {}
    for table, file_path in data_files.items():
        if file_path.exists():
            df = pd.read_parquet(file_path)
            data[table] = df
            print(f"  ✅ {table}: {len(df)} records")
        else:
            print(f"  ❌ {table}: file not found at {file_path}")
            data[table] = pd.DataFrame()
    
    print()
    
    # Create tables
    print("Step 2: Creating Iceberg tables...")
    schemas = {
        'users': create_users_schema(),
        'properties': create_properties_schema(),
        'clients': create_clients_schema(),
        'expenses': create_expenses_schema(),
        'rents': create_rents_schema(),
    }
    
    for table_name, schema in schemas.items():
        create_table_if_not_exists(catalog, table_name, schema)
    
    print()
    
    # Load data into tables
    print("Step 3: Loading data into Iceberg tables...")
    for table_name, df in data.items():
        load_data_to_table(catalog, table_name, df)
    
    print()
    
    # Verify
    print("Step 4: Verifying data...")
    for table_name in data.keys():
        try:
            table = catalog.load_table((*NAMESPACE, table_name))
            scan = table.scan()
            arrow_table = scan.to_arrow()
            print(f"  ✅ {table_name}: {len(arrow_table)} records verified")
        except Exception as e:
            print(f"  ❌ {table_name}: verification failed - {e}")
    
    print()
    print("=" * 70)
    print("✅ Data restoration complete!")
    print("=" * 70)
    print()
    print("Summary:")
    print(f"  • Namespace: {'.'.join(NAMESPACE)}")
    print(f"  • Tables restored:")
    for table_name, df in data.items():
        if len(df) > 0:
            print(f"    - {table_name}: {len(df)} records")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Failed to restore data: {e}", exc_info=True)
        sys.exit(1)

