"""
Utility functions for managing tax savings (depreciation) revenue
"""
import uuid
import pandas as pd
from decimal import Decimal
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from app.core.iceberg import append_data, read_table, load_table, table_exists
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache

NAMESPACE = ("investflow",)
REVENUE_TABLE = "scheduled_revenue"

logger = get_logger(__name__)

# Residential rental property depreciation period per IRS
DEPRECIATION_YEARS = Decimal("27.5")


def calculate_annual_depreciation(property_value: Decimal, tax_rate: Decimal) -> Decimal:
    """
    Calculate annual tax savings from depreciation for residential rental property
    Formula: (property_value / 27.5 years) × tax_rate
    
    Note: Uses current_market_value (what the property is worth), not purchase_price.
    Purchase date is NOT used in this calculation.
    
    Args:
        property_value: Property current market value (what the property is worth)
        tax_rate: User's tax rate (e.g., 0.25 for 25%)
    """
    annual_depreciation = property_value / DEPRECIATION_YEARS
    tax_savings = annual_depreciation * tax_rate
    # Round to 2 decimal places to match table schema precision
    tax_savings = tax_savings.quantize(Decimal('0.01'))
    logger.info(f"  Tax savings calc: (${property_value} ÷ 27.5 years) × {tax_rate*100}% = ${tax_savings:.2f}/year")
    return tax_savings


async def create_or_update_tax_savings(property_id: str, user_id: str, current_market_value: Decimal, purchase_date: date = None):
    """
    Create or update tax savings (depreciation) revenue item for a property
    
    Args:
        property_id: The property ID
        user_id: The user ID (to get their tax rate)
        current_market_value: Property current market value (what the property is worth - used in calculation)
        purchase_date: Date property was purchased (optional, only used in notes, not in calculation)
    """
    try:
        logger.info(f"💰 Creating/updating tax savings for property {property_id}")
        logger.info(f"  Current Market Value: ${current_market_value}")
        if purchase_date:
            logger.info(f"  Purchase Date: {purchase_date} (not used in calculation)")
        
        # Get user's tax rate from CDC cache (fast O(1) lookup)
        user = auth_cache.get_user_by_id(user_id)
        if user is None:
            logger.warning(f"  ⚠️  User {user_id} not found, cannot calculate tax savings")
            return
        
        tax_rate = Decimal(str(user.get("tax_rate", 0)))
        logger.info(f"  User Tax Rate: {tax_rate*100}%")
        
        # Check if tax savings revenue already exists
        if table_exists(NAMESPACE, REVENUE_TABLE):
            df = read_table(NAMESPACE, REVENUE_TABLE)
            existing_tax_savings = df[
                (df["property_id"] == property_id) & 
                (df["revenue_type"] == "tax_savings")
            ]
            
            # Delete existing tax savings for this property
            if not existing_tax_savings.empty:
                logger.info(f"  Removing existing tax savings for property {property_id}")
                df = df[~((df["property_id"] == property_id) & (df["revenue_type"] == "tax_savings"))]
                
                # Overwrite table without the old tax savings
                table = load_table(NAMESPACE, REVENUE_TABLE)
                table_schema = table.schema().as_arrow()
                
                # Convert timestamps to microseconds
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].astype('datetime64[us]')
                
                # Reorder columns to match schema
                schema_column_order = [field.name for field in table_schema]
                df = df[[col for col in schema_column_order if col in df.columns]]
                
                # Reset index to avoid __index_level_0__ column
                df = df.reset_index(drop=True)
                
                import pyarrow as pa
                arrow_table = pa.Table.from_pandas(df, preserve_index=False)
                arrow_table = arrow_table.cast(table_schema)
                table.overwrite(arrow_table)
        
        # Calculate annual tax savings from depreciation
        annual_amount = calculate_annual_depreciation(current_market_value, tax_rate)
        
        # Create new tax savings revenue
        now = pd.Timestamp.now()
        depreciation_amount = (current_market_value / DEPRECIATION_YEARS).quantize(Decimal('0.01'))
        notes = f"Tax savings from depreciation: (${current_market_value} ÷ 27.5 years = ${depreciation_amount}) × {tax_rate*100}% tax rate"
        if purchase_date:
            notes += f" (purchased {purchase_date})"
        
        revenue_dict = {
            "id": str(uuid.uuid4()),
            "property_id": property_id,
            "revenue_type": "tax_savings",
            "item_name": "Tax Depreciation",
            "annual_amount": annual_amount,
            "appreciation_rate": None,
            "property_value": None,
            "value_added_amount": None,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        logger.info(f"  ✅ Tax Savings: ${annual_amount:.2f}/year (${depreciation_amount} × {tax_rate*100}%)")
        
        # Append new tax savings to table
        df_new = pd.DataFrame([revenue_dict])
        append_data(NAMESPACE, REVENUE_TABLE, df_new)
        logger.info(f"✅ Created tax savings revenue for property {property_id}")
        
    except Exception as e:
        logger.error(f"❌ Error creating tax savings: {e}", exc_info=True)
        # Don't raise - this is a background operation that shouldn't break property creation


async def delete_tax_savings(property_id: str):
    """
    Delete tax savings revenue for a property
    """
    try:
        if not table_exists(NAMESPACE, REVENUE_TABLE):
            return
        
        df = read_table(NAMESPACE, REVENUE_TABLE)
        existing_tax_savings = df[
            (df["property_id"] == property_id) & 
            (df["revenue_type"] == "tax_savings")
        ]
        
        if existing_tax_savings.empty:
            return
        
        logger.info(f"Deleting tax savings for property {property_id}")
        df = df[~((df["property_id"] == property_id) & (df["revenue_type"] == "tax_savings"))]
        
        # Overwrite table
        table = load_table(NAMESPACE, REVENUE_TABLE)
        table_schema = table.schema().as_arrow()
        
        # Convert timestamps
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype('datetime64[us]')
        
        schema_column_order = [field.name for field in table_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Reset index to avoid __index_level_0__ column
        df = df.reset_index(drop=True)
        
        import pyarrow as pa
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        arrow_table = arrow_table.cast(table_schema)
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Deleted tax savings for property {property_id}")
        
    except Exception as e:
        logger.error(f"❌ Error deleting tax savings: {e}", exc_info=True)

