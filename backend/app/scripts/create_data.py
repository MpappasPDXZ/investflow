#!/usr/bin/env python3
"""
Create sample data using PyIceberg and Lakekeeper.

This script:
1. Creates Iceberg tables via Lakekeeper (drops if already exist)
2. Truncates and loads data (drops and recreates tables)
3. Tests reads to verify data was loaded correctly

All tables are created in the 'investflow' namespace.
"""
import sys
import asyncio
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date
import uuid
import pandas as pd
import pyarrow as pa

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


def create_user_schema() -> pa.Schema:
    """Create PyArrow schema for user table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=False),
        pa.field("password_hash", pa.string(), nullable=False),  # Password hash for authentication
        pa.field("tax_rate", pa.decimal128(5, 2), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_user_shares_schema() -> pa.Schema:
    """Create PyArrow schema for user_shares table (bidirectional sharing)"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),  # User who created the share
        pa.field("shared_email", pa.string(), nullable=False),  # Email to share with (bidirectional)
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
    ])


def create_properties_schema() -> pa.Schema:
    """Create PyArrow schema for properties table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),  # UUID as string
        pa.field("display_name", pa.string(), nullable=True),
        pa.field("purchase_price", pa.decimal128(12, 2), nullable=False),
        pa.field("monthly_rent_to_income_ratio", pa.decimal128(4, 2), nullable=True),
        pa.field("address_line1", pa.string(), nullable=True),
        pa.field("address_line2", pa.string(), nullable=True),
        pa.field("city", pa.string(), nullable=True),
        pa.field("state", pa.string(), nullable=True),
        pa.field("zip_code", pa.string(), nullable=True),
        pa.field("property_type", pa.string(), nullable=True),
        pa.field("has_units", pa.bool_(), nullable=True),  # NEW: indicates multi-unit property
        pa.field("unit_count", pa.int32(), nullable=True),  # NEW: number of units
        pa.field("bedrooms", pa.int32(), nullable=True),
        pa.field("bathrooms", pa.decimal128(3, 1), nullable=True),
        pa.field("square_feet", pa.int32(), nullable=True),
        pa.field("year_built", pa.int32(), nullable=True),
        pa.field("current_monthly_rent", pa.decimal128(10, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_units_schema() -> pa.Schema:
    """Create PyArrow schema for units table (for multi-family/duplex properties)"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string - foreign key to properties
        pa.field("unit_number", pa.string(), nullable=False),  # e.g., "Unit 1", "1A", "Apt 201"
        pa.field("bedrooms", pa.int32(), nullable=True),
        pa.field("bathrooms", pa.decimal128(3, 1), nullable=True),
        pa.field("square_feet", pa.int32(), nullable=True),
        pa.field("current_monthly_rent", pa.decimal128(10, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_expenses_schema() -> pa.Schema:
    """Create PyArrow schema for expenses table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("description", pa.string(), nullable=False),
        pa.field("date", pa.date32(), nullable=False),
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("vendor", pa.string(), nullable=True),
        pa.field("expense_type", pa.string(), nullable=False),  # enum as string
        pa.field("document_storage_id", pa.string(), nullable=True),  # UUID as string
        pa.field("is_planned", pa.bool_(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("created_by_user_id", pa.string(), nullable=True),  # UUID as string
    ])


def create_clients_schema() -> pa.Schema:
    """Create PyArrow schema for clients table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("first_name", pa.string(), nullable=False),
        pa.field("last_name", pa.string(), nullable=False),
        pa.field("email", pa.string(), nullable=True),
        pa.field("phone", pa.string(), nullable=True),
        pa.field("phone_secondary", pa.string(), nullable=True),
        pa.field("address_line1", pa.string(), nullable=True),
        pa.field("address_line2", pa.string(), nullable=True),
        pa.field("city", pa.string(), nullable=True),
        pa.field("state", pa.string(), nullable=True),
        pa.field("zip_code", pa.string(), nullable=True),
        pa.field("emergency_contact_name", pa.string(), nullable=True),
        pa.field("emergency_contact_phone", pa.string(), nullable=True),
        pa.field("annual_income", pa.decimal128(12, 2), nullable=True),
        pa.field("lease_start_date", pa.date32(), nullable=True),
        pa.field("lease_end_date", pa.date32(), nullable=True),
        pa.field("monthly_rent_amount", pa.decimal128(10, 2), nullable=True),
        pa.field("security_deposit", pa.decimal128(10, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("is_active", pa.bool_(), nullable=True),
    ])


def create_rents_schema() -> pa.Schema:
    """Create PyArrow schema for rents table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("client_id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("amount", pa.decimal128(10, 2), nullable=False),
        pa.field("rent_period_start", pa.date32(), nullable=False),
        pa.field("rent_period_end", pa.date32(), nullable=False),
        pa.field("payment_date", pa.date32(), nullable=False),
        pa.field("payment_method", pa.string(), nullable=True),  # enum as string
        pa.field("transaction_reference", pa.string(), nullable=True),
        pa.field("is_late", pa.bool_(), nullable=True),
        pa.field("late_fee", pa.decimal128(10, 2), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("created_by_user_id", pa.string(), nullable=True),  # UUID as string
    ])


def create_property_plan_schema() -> pa.Schema:
    """Create PyArrow schema for property_plan table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("annual_tax", pa.decimal128(10, 2), nullable=False),
        pa.field("annual_property_taxes", pa.decimal128(10, 2), nullable=False),
        pa.field("plan_year", pa.int32(), nullable=True),
        pa.field("notes", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_document_storage_schema() -> pa.Schema:
    """Create PyArrow schema for document_storage table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("blob_location", pa.string(), nullable=False),
        pa.field("file_name", pa.string(), nullable=False),
        pa.field("file_type", pa.string(), nullable=True),
        pa.field("file_size", pa.int64(), nullable=True),
        pa.field("document_type", pa.string(), nullable=True),  # enum as string
        pa.field("metadata", pa.string(), nullable=True),  # JSONB as string
        pa.field("uploaded_by_user_id", pa.string(), nullable=True),  # UUID as string
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
        pa.field("expires_at", pa.timestamp("us"), nullable=True),
    ])


def create_scenarios_schema() -> pa.Schema:
    """Create PyArrow schema for scenarios table"""
    return pa.schema([
        pa.field("id", pa.string(), nullable=False),  # UUID as string
        pa.field("property_id", pa.string(), nullable=False),  # UUID as string
        pa.field("user_id", pa.string(), nullable=False),  # UUID as string
        pa.field("scenario_name", pa.string(), nullable=True),
        pa.field("monthly_rent", pa.decimal128(10, 2), nullable=False),
        pa.field("vacancy_rate", pa.decimal128(5, 2), nullable=False),
        pa.field("annual_expenses", pa.decimal128(10, 2), nullable=False),
        pa.field("tax_savings", pa.decimal128(10, 2), nullable=False),
        pa.field("annual_appreciation", pa.decimal128(10, 2), nullable=False),
        pa.field("purchase_price", pa.decimal128(12, 2), nullable=False),
        pa.field("down_payment", pa.decimal128(12, 2), nullable=False),
        pa.field("annual_rent", pa.decimal128(10, 2), nullable=True),
        pa.field("cash_on_cash_roi", pa.decimal128(5, 2), nullable=True),
        pa.field("total_roi", pa.decimal128(5, 2), nullable=True),
        pa.field("net_cash_flow", pa.decimal128(10, 2), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=True),
        pa.field("updated_at", pa.timestamp("us"), nullable=True),
    ])


def create_sample_users() -> pd.DataFrame:
    """Create sample user data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333"
        ],
        "first_name": ["John", "Jane", "Bob"],
        "last_name": ["Doe", "Smith", "Wilson"],
        "email": ["john.doe@example.com", "jane.smith@example.com", "bob.wilson@example.com"],
        "tax_rate": [Decimal("0.25"), Decimal("0.30"), Decimal("0.22")],
        "created_at": [now, now, now],
        "updated_at": [now, now, now],
        "is_active": [True, True, True]
    })


def create_sample_properties(user_ids: list) -> pd.DataFrame:
    """Create sample property data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "cccccccc-cccc-cccc-cccc-cccccccccccc"
        ],
        "user_id": [user_ids[0], user_ids[0], user_ids[1]],
        "display_name": ["Main Street Property", "Oak Avenue Condo", "Riverside Apartment"],
        "purchase_price": [Decimal("350000.00"), Decimal("275000.00"), Decimal("425000.00")],
        "monthly_rent_to_income_ratio": [Decimal("2.75"), Decimal("2.75"), Decimal("2.75")],
        "address_line1": ["123 Main St", "456 Oak Ave", "789 River Rd"],
        "address_line2": [None, "Unit 2B", None],
        "city": ["Portland", "Seattle", "Denver"],
        "state": ["OR", "WA", "CO"],
        "zip_code": ["97201", "98101", "80202"],
        "property_type": ["single_family", "condo", "multi_family"],
        "bedrooms": [3, 2, 4],
        "bathrooms": [Decimal("2.0"), Decimal("1.5"), Decimal("2.5")],
        "square_feet": [1500, 1200, 2000],
        "year_built": [1995, 2010, 1985],
        "current_monthly_rent": [Decimal("2200.00"), Decimal("1800.00"), Decimal("2800.00")],
        "notes": ["Great location", None, "Needs some updates"],
        "created_at": [now, now, now],
        "updated_at": [now, now, now],
        "is_active": [True, True, True]
    })


def create_sample_expenses(property_ids: list, user_ids: list, document_storage_ids: list) -> pd.DataFrame:
    """Create sample expense data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "e1111111-1111-1111-1111-111111111111",
            "e2222222-2222-2222-2222-222222222222",
            "e3333333-3333-3333-3333-333333333333",
            "e4444444-4444-4444-4444-444444444444"
        ],
        "property_id": [property_ids[0], property_ids[0], property_ids[1], property_ids[2]],
        "description": ["Roof repair", "Property insurance", "Plumbing fix", "HVAC maintenance"],
        "date": [date(2024, 1, 15), date(2024, 2, 1), date(2024, 2, 20), date(2024, 3, 10)],
        "amount": [Decimal("2500.00"), Decimal("1200.00"), Decimal("450.00"), Decimal("800.00")],
        "vendor": ["ABC Roofing", "State Farm", "PlumbPro", "CoolAir Inc"],
        "expense_type": ["capex", "insurance", "maintenance", "maintenance"],
        "document_storage_id": [document_storage_ids[0], None, document_storage_ids[2], None],  # Link some expenses to documents
        "is_planned": [False, False, False, False],
        "notes": ["Emergency repair", None, "Leaky faucet", "Annual service"],
        "created_at": [now, now, now, now],
        "updated_at": [now, now, now, now],
        "created_by_user_id": [user_ids[0], user_ids[0], user_ids[0], user_ids[1]]
    })


def create_sample_clients(property_ids: list) -> pd.DataFrame:
    """Create sample client data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "c1111111-1111-1111-1111-111111111111",
            "c2222222-2222-2222-2222-222222222222",
            "c3333333-3333-3333-3333-333333333333"
        ],
        "property_id": [property_ids[0], property_ids[1], property_ids[2]],
        "first_name": ["Alice", "Bob", "Charlie"],
        "last_name": ["Johnson", "Williams", "Brown"],
        "email": ["alice.j@example.com", "bob.w@example.com", "charlie.b@example.com"],
        "phone": ["503-555-0101", "206-555-0202", "303-555-0303"],
        "phone_secondary": [None, "206-555-0203", None],
        "address_line1": ["123 Main St", "456 Oak Ave", "789 River Rd"],
        "address_line2": [None, "Unit 2B", None],
        "city": ["Portland", "Seattle", "Denver"],
        "state": ["OR", "WA", "CO"],
        "zip_code": ["97201", "98101", "80202"],
        "emergency_contact_name": ["John Johnson", "Mary Williams", "Diana Brown"],
        "emergency_contact_phone": ["503-555-0102", "206-555-0204", "303-555-0304"],
        "annual_income": [Decimal("75000.00"), Decimal("65000.00"), Decimal("85000.00")],
        "lease_start_date": [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)],
        "lease_end_date": [date(2024, 12, 31), date(2025, 1, 31), date(2025, 2, 28)],
        "monthly_rent_amount": [Decimal("2200.00"), Decimal("1800.00"), Decimal("2800.00")],
        "security_deposit": [Decimal("2200.00"), Decimal("1800.00"), Decimal("2800.00")],
        "notes": [None, "Great tenant", "Pays on time"],
        "created_at": [now, now, now],
        "updated_at": [now, now, now],
        "is_active": [True, True, True]
    })


def create_sample_rents(client_ids: list, property_ids: list, user_ids: list) -> pd.DataFrame:
    """Create sample rent data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "r1111111-1111-1111-1111-111111111111",
            "r2222222-2222-2222-2222-222222222222",
            "r3333333-3333-3333-3333-333333333333"
        ],
        "client_id": [client_ids[0], client_ids[1], client_ids[2]],
        "property_id": [property_ids[0], property_ids[1], property_ids[2]],
        "amount": [Decimal("2200.00"), Decimal("1800.00"), Decimal("2800.00")],
        "rent_period_start": [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)],
        "rent_period_end": [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31)],
        "payment_date": [date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)],
        "payment_method": ["electronic", "check", "electronic"],
        "transaction_reference": ["ACH-12345", "CHK-67890", "ACH-11111"],
        "is_late": [False, False, False],
        "late_fee": [Decimal("0.00"), Decimal("0.00"), Decimal("0.00")],
        "notes": [None, None, None],
        "created_at": [now, now, now],
        "updated_at": [now, now, now],
        "created_by_user_id": [user_ids[0], user_ids[0], user_ids[1]]
    })


def create_sample_property_plan(property_ids: list) -> pd.DataFrame:
    """Create sample property_plan data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "p1111111-1111-1111-1111-111111111111",
            "p2222222-2222-2222-2222-222222222222",
            "p3333333-3333-3333-3333-333333333333"
        ],
        "property_id": [property_ids[0], property_ids[1], property_ids[2]],
        "annual_tax": [Decimal("8750.00"), Decimal("6875.00"), Decimal("10625.00")],
        "annual_property_taxes": [Decimal("4200.00"), Decimal("3300.00"), Decimal("5100.00")],
        "plan_year": [2024, 2024, 2024],
        "notes": ["2024 tax plan", None, "Includes all deductions"],
        "created_at": [now, now, now],
        "updated_at": [now, now, now]
    })


def create_sample_document_storage(user_ids: list) -> pd.DataFrame:
    """Create sample document_storage data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "d1111111-1111-1111-1111-111111111111",
            "d2222222-2222-2222-2222-222222222222",
            "d3333333-3333-3333-3333-333333333333"
        ],
        "blob_location": [
            "https://investflowadls.blob.core.windows.net/documents/user1/receipts/2024/01/receipt_001.pdf",
            "https://investflowadls.blob.core.windows.net/documents/user1/leases/2024/lease_agreement.pdf",
            "https://investflowadls.blob.core.windows.net/documents/user2/receipts/2024/02/receipt_002.jpg"
        ],
        "file_name": ["receipt_001.pdf", "lease_agreement.pdf", "receipt_002.jpg"],
        "file_type": ["application/pdf", "application/pdf", "image/jpeg"],
        "file_size": [245760, 512000, 98304],  # bytes
        "document_type": ["receipt", "lease", "receipt"],
        "metadata": [None, '{"pages": 5, "signed": true}', None],  # JSON as string
        "uploaded_by_user_id": [user_ids[0], user_ids[0], user_ids[1]],
        "created_at": [now, now, now],
        "updated_at": [now, now, now],
        "expires_at": [None, None, None]
    })


def create_sample_scenarios(property_ids: list, user_ids: list) -> pd.DataFrame:
    """Create sample scenario data"""
    now = pd.Timestamp.now()
    return pd.DataFrame({
        "id": [
            "s1111111-1111-1111-1111-111111111111",
            "s2222222-2222-2222-2222-222222222222"
        ],
        "property_id": [property_ids[0], property_ids[0]],
        "user_id": [user_ids[0], user_ids[0]],
        "scenario_name": ["Conservative", "Optimistic"],
        "monthly_rent": [Decimal("2200.00"), Decimal("2500.00")],
        "vacancy_rate": [Decimal("7.00"), Decimal("5.00")],
        "annual_expenses": [Decimal("44558.00"), Decimal("44558.00")],
        "tax_savings": [Decimal("7029.00"), Decimal("7029.00")],
        "annual_appreciation": [Decimal("17520.00"), Decimal("17520.00")],
        "purchase_price": [Decimal("350000.00"), Decimal("350000.00")],
        "down_payment": [Decimal("70000.00"), Decimal("70000.00")],
        "annual_rent": [Decimal("24552.00"), Decimal("28500.00")],  # Calculated
        "cash_on_cash_roi": [Decimal("-28.58"), Decimal("-22.94")],  # Calculated
        "total_roi": [Decimal("1.46"), Decimal("2.66")],  # Calculated
        "net_cash_flow": [Decimal("-20006.00"), Decimal("-16058.00")],  # Calculated
        "created_at": [now, now],
        "updated_at": [now, now]
    })


async def ensure_namespace(lakekeeper, warehouse_id: str):
    """Ensure the namespace exists"""
    try:
        namespaces = await lakekeeper.list_namespaces(warehouse_id)
        namespace_list = list(NAMESPACE)
        if namespace_list not in namespaces:
            await lakekeeper.create_namespace(warehouse_id, namespace_list)
            logger.info(f"✅ Created namespace: {'.'.join(NAMESPACE)}")
        else:
            logger.info(f"✅ Namespace already exists: {'.'.join(NAMESPACE)}")
    except Exception as e:
        if "409" in str(e) or "already exists" in str(e).lower():
            logger.info(f"✅ Namespace already exists: {'.'.join(NAMESPACE)}")
        else:
            raise


async def create_table_with_data(
    pyiceberg,
    lakekeeper,
    warehouse_id: str,
    table_name: str,
    schema: pa.Schema,
    data: pd.DataFrame,
    description: str
):
    """Create table, truncate if exists, and load data"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {table_name}")
    logger.info(f"{'='*60}")
    
    # Truncate (drop and recreate) table
    logger.info(f"Truncating table {table_name}...")
    try:
        pyiceberg.truncate_table(NAMESPACE, table_name, schema)
        logger.info(f"  ✅ Table {table_name} truncated (dropped and recreated)")
    except Exception as e:
        logger.warning(f"  ⚠️  Could not truncate (may not exist): {e}")
        # Try creating fresh
        try:
            pyiceberg.create_table(NAMESPACE, table_name, schema)
            logger.info(f"  ✅ Created new table {table_name}")
        except Exception as create_error:
            logger.error(f"  ❌ Failed to create table: {create_error}")
            raise
    
    # Load data
    if len(data) > 0:
        logger.info(f"Loading {len(data)} rows into {table_name}...")
        pyiceberg.append_data(NAMESPACE, table_name, data)
        logger.info(f"  ✅ Loaded {len(data)} rows")
    else:
        logger.info(f"  ⚠️  No data to load for {table_name}")
    
    # Test read
    logger.info(f"Testing read from {table_name}...")
    try:
        df = pyiceberg.read_table(NAMESPACE, table_name)
        logger.info(f"  ✅ Successfully read {len(df)} rows from {table_name}")
        logger.info(f"  📊 Columns: {', '.join(df.columns.tolist())}")
        if len(df) > 0:
            logger.info(f"  📋 Sample row:\n{df.head(1).to_string()}")
    except Exception as e:
        logger.error(f"  ❌ Failed to read from {table_name}: {e}")
        raise


async def test_update_property(pyiceberg, property_id: str):
    """Test updating a property record"""
    print(f"\n📝 Testing UPDATE pattern: Property {property_id}")
    
    try:
        # Read all properties
        df = pyiceberg.read_table(NAMESPACE, "properties")
        original_count = len(df)
        
        # Find the property to update
        mask = df["id"] == property_id
        if not mask.any():
            print(f"  ⚠️  Property {property_id} not found")
            return
        
        # Get original values
        original_row = df[mask].iloc[0]
        original_name = original_row.get("display_name", "N/A")
        
        # Update the property
        print(f"  📋 Original display_name: {original_name}")
        new_name = f"{original_name} (UPDATED)"
        df.loc[mask, "display_name"] = new_name
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Get table schema
        table = pyiceberg.load_table(NAMESPACE, "properties")
        schema = table.schema().as_arrow()
        
        # Truncate and reload (Iceberg update pattern)
        pyiceberg.truncate_table(NAMESPACE, "properties", schema)
        pyiceberg.append_data(NAMESPACE, "properties", df)
        
        # Verify update
        df_after = pyiceberg.read_table(NAMESPACE, "properties")
        updated_row = df_after[df_after["id"] == property_id].iloc[0]
        
        if updated_row["display_name"] == new_name:
            print(f"  ✅ Update successful: {new_name}")
            print(f"  📊 Table still has {len(df_after)} rows (same as before)")
        else:
            print(f"  ❌ Update failed: Expected '{new_name}', got '{updated_row['display_name']}'")
            
    except Exception as e:
        print(f"  ❌ Update test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_update_expense(pyiceberg, expense_id: str):
    """Test updating an expense record"""
    print(f"\n📝 Testing UPDATE pattern: Expense {expense_id}")
    
    try:
        # Read all expenses
        df = pyiceberg.read_table(NAMESPACE, "expenses")
        
        # Find the expense to update
        mask = df["id"] == expense_id
        if not mask.any():
            print(f"  ⚠️  Expense {expense_id} not found")
            return
        
        # Get original values
        original_row = df[mask].iloc[0]
        original_amount = float(original_row["amount"])
        original_desc = original_row.get("description", "N/A")
        
        # Update the expense
        print(f"  📋 Original: {original_desc} - ${original_amount}")
        new_amount = original_amount + 100.00
        new_desc = f"{original_desc} (UPDATED)"
        df.loc[mask, "amount"] = float(new_amount)
        df.loc[mask, "description"] = new_desc
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Get table schema
        table = pyiceberg.load_table(NAMESPACE, "expenses")
        schema = table.schema().as_arrow()
        
        # Truncate and reload
        pyiceberg.truncate_table(NAMESPACE, "expenses", schema)
        pyiceberg.append_data(NAMESPACE, "expenses", df)
        
        # Verify update
        df_after = pyiceberg.read_table(NAMESPACE, "expenses")
        updated_row = df_after[df_after["id"] == expense_id].iloc[0]
        
        if (updated_row["description"] == new_desc and 
            abs(float(updated_row["amount"]) - new_amount) < 0.01):
            print(f"  ✅ Update successful: {new_desc} - ${new_amount}")
        else:
            print(f"  ❌ Update failed")
            
    except Exception as e:
        print(f"  ❌ Update test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_soft_delete_property(pyiceberg, property_id: str):
    """Test soft deleting a property (set is_active=False)"""
    print(f"\n🗑️  Testing SOFT DELETE pattern: Property {property_id}")
    
    try:
        # Read all properties
        df = pyiceberg.read_table(NAMESPACE, "properties")
        original_count = len(df)
        active_count = len(df[df["is_active"] == True])
        
        # Find the property to soft delete
        mask = df["id"] == property_id
        if not mask.any():
            print(f"  ⚠️  Property {property_id} not found")
            return
        
        # Soft delete (set is_active=False)
        print(f"  📋 Original: {active_count} active properties")
        df.loc[mask, "is_active"] = False
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Get table schema
        table = pyiceberg.load_table(NAMESPACE, "properties")
        schema = table.schema().as_arrow()
        
        # Truncate and reload
        pyiceberg.truncate_table(NAMESPACE, "properties", schema)
        pyiceberg.append_data(NAMESPACE, "properties", df)
        
        # Verify soft delete
        df_after = pyiceberg.read_table(NAMESPACE, "properties")
        deleted_row = df_after[df_after["id"] == property_id].iloc[0]
        active_after = len(df_after[df_after["is_active"] == True])
        
        if deleted_row["is_active"] == False and active_after == active_count - 1:
            print(f"  ✅ Soft delete successful: {active_after} active properties (was {active_count})")
            print(f"  📊 Total rows unchanged: {len(df_after)} (soft delete preserves data)")
        else:
            print(f"  ❌ Soft delete failed")
            
    except Exception as e:
        print(f"  ❌ Soft delete test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_soft_delete_client(pyiceberg, client_id: str):
    """Test soft deleting a client (set is_active=False)"""
    print(f"\n🗑️  Testing SOFT DELETE pattern: Client {client_id}")
    
    try:
        # Read all clients
        df = pyiceberg.read_table(NAMESPACE, "clients")
        active_count = len(df[df["is_active"] == True])
        
        # Find the client to soft delete
        mask = df["id"] == client_id
        if not mask.any():
            print(f"  ⚠️  Client {client_id} not found")
            return
        
        # Soft delete
        print(f"  📋 Original: {active_count} active clients")
        df.loc[mask, "is_active"] = False
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Get table schema
        table = pyiceberg.load_table(NAMESPACE, "clients")
        schema = table.schema().as_arrow()
        
        # Truncate and reload
        pyiceberg.truncate_table(NAMESPACE, "clients", schema)
        pyiceberg.append_data(NAMESPACE, "clients", df)
        
        # Verify soft delete
        df_after = pyiceberg.read_table(NAMESPACE, "clients")
        deleted_row = df_after[df_after["id"] == client_id].iloc[0]
        active_after = len(df_after[df_after["is_active"] == True])
        
        if deleted_row["is_active"] == False and active_after == active_count - 1:
            print(f"  ✅ Soft delete successful: {active_after} active clients (was {active_count})")
        else:
            print(f"  ❌ Soft delete failed")
            
    except Exception as e:
        print(f"  ❌ Soft delete test failed: {e}")
        import traceback
        traceback.print_exc()


async def verify_property_update(pyiceberg, property_id: str):
    """Verify a property was updated correctly"""
    try:
        df = pyiceberg.read_table(NAMESPACE, "properties")
        row = df[df["id"] == property_id].iloc[0]
        
        if "(UPDATED)" in str(row.get("display_name", "")):
            print(f"  ✅ Property {property_id} update verified")
        else:
            print(f"  ⚠️  Property {property_id} update not found")
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")


async def verify_property_soft_delete(pyiceberg, property_id: str):
    """Verify a property was soft deleted correctly"""
    try:
        df = pyiceberg.read_table(NAMESPACE, "properties")
        row = df[df["id"] == property_id].iloc[0]
        
        if row["is_active"] == False:
            print(f"  ✅ Property {property_id} soft delete verified (is_active=False)")
        else:
            print(f"  ⚠️  Property {property_id} still active")
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")


async def verify_client_soft_delete(pyiceberg, client_id: str):
    """Verify a client was soft deleted correctly"""
    try:
        df = pyiceberg.read_table(NAMESPACE, "clients")
        row = df[df["id"] == client_id].iloc[0]
        
        if row["is_active"] == False:
            print(f"  ✅ Client {client_id} soft delete verified (is_active=False)")
        else:
            print(f"  ⚠️  Client {client_id} still active")
    except Exception as e:
        print(f"  ❌ Verification failed: {e}")


async def main():
    """Main function"""
    print("=" * 70)
    print("Create Sample Data - PyIceberg & Lakekeeper")
    print("=" * 70)
    print()
    
    # Get services
    lakekeeper = get_lakekeeper_service()
    pyiceberg = get_pyiceberg_service()
    
    # Step 1: Get warehouse
    print("Step 1: Getting warehouse...")
    warehouse_id = await lakekeeper.get_warehouse_id(WAREHOUSE_NAME)
    if not warehouse_id:
        print(f"❌ Warehouse '{WAREHOUSE_NAME}' not found!")
        return
    print(f"✅ Warehouse ID: {warehouse_id}")
    
    # Step 2: Ensure namespace exists
    print("\nStep 2: Ensuring namespace exists...")
    await ensure_namespace(lakekeeper, warehouse_id)
    
    # Step 3: Create tables and load data in order
    print("\nStep 3: Creating tables and loading data...")
    
    # 3.1: Users (no dependencies)
    users_df = create_sample_users()
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "users", create_user_schema(), users_df,
        "Users table"
    )
    user_ids = users_df["id"].tolist()
    
    # 3.2: User Shares (depends on users)
    user_shares_df = pd.DataFrame()  # Empty initially, users can add shares later
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "user_shares", create_user_shares_schema(), user_shares_df,
        "User Shares table (bidirectional property sharing)"
    )
    
    # 3.3: Properties (depends on users)
    properties_df = create_sample_properties(user_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "properties", create_properties_schema(), properties_df,
        "Properties table"
    )
    property_ids = properties_df["id"].tolist()
    
    # 3.4: Property Plan (depends on properties)
    property_plan_df = create_sample_property_plan(property_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "property_plan", create_property_plan_schema(), property_plan_df,
        "Property Plan table"
    )
    
    # 3.5: Document Storage (depends on users)
    document_storage_df = create_sample_document_storage(user_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "document_storage", create_document_storage_schema(), document_storage_df,
        "Document Storage table"
    )
    document_storage_ids = document_storage_df["id"].tolist()
    
    # 3.6: Expenses (depends on properties, users, document_storage)
    expenses_df = create_sample_expenses(property_ids, user_ids, document_storage_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "expenses", create_expenses_schema(), expenses_df,
        "Expenses table"
    )
    
    # 3.7: Clients (depends on properties)
    clients_df = create_sample_clients(property_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "clients", create_clients_schema(), clients_df,
        "Clients table"
    )
    client_ids = clients_df["id"].tolist()
    
    # 3.8: Rents (depends on clients, properties, users)
    rents_df = create_sample_rents(client_ids, property_ids, user_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "rents", create_rents_schema(), rents_df,
        "Rents table"
    )
    
    # 3.9: Scenarios (depends on properties, users)
    scenarios_df = create_sample_scenarios(property_ids, user_ids)
    await create_table_with_data(
        pyiceberg, lakekeeper, warehouse_id,
        "scenarios", create_scenarios_schema(), scenarios_df,
        "Scenarios table"
    )
    
    # Step 4: Final verification
    print("\n" + "=" * 70)
    print("Final Verification - Reading all tables")
    print("=" * 70)
    
    tables = ["users", "user_shares", "properties", "property_plan", "document_storage", "expenses", "clients", "rents", "scenarios"]
    for table_name in tables:
        try:
            df = pyiceberg.read_table(NAMESPACE, table_name)
            print(f"✅ {table_name}: {len(df)} rows")
        except Exception as e:
            print(f"❌ {table_name}: Failed - {e}")
    
    # Step 5: Test Update and Delete patterns
    print("\n" + "=" * 70)
    print("Step 5: Testing Update and Delete Patterns")
    print("=" * 70)
    
    # Test 1: Update a property
    await test_update_property(pyiceberg, property_ids[0])
    
    # Test 2: Update an expense
    await test_update_expense(pyiceberg, expenses_df["id"].iloc[0])
    
    # Test 3: Soft delete a property (set is_active=False)
    await test_soft_delete_property(pyiceberg, property_ids[1])
    
    # Test 4: Soft delete a client (set is_active=False)
    await test_soft_delete_client(pyiceberg, client_ids[0])
    
    # Step 6: Verify updates and deletes
    print("\n" + "=" * 70)
    print("Step 6: Verifying Updates and Deletes")
    print("=" * 70)
    
    # Verify property update
    await verify_property_update(pyiceberg, property_ids[0])
    
    # Verify property soft delete
    await verify_property_soft_delete(pyiceberg, property_ids[1])
    
    # Verify client soft delete
    await verify_client_soft_delete(pyiceberg, client_ids[0])
    
    print("\n" + "=" * 70)
    print("✅ Data Creation and Testing Complete!")
    print("=" * 70)
    print(f"\nAll tables created in namespace: {'.'.join(NAMESPACE)}")
    print(f"Warehouse: {WAREHOUSE_NAME}")
    print("\n✅ Update and Delete patterns tested successfully!")


if __name__ == "__main__":
    asyncio.run(main())
