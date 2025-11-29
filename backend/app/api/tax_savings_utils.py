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

NAMESPACE = ("investflow",)
REVENUE_TABLE = "scheduled_revenue"

logger = get_logger(__name__)

# Residential rental property depreciation period per IRS
DEPRECIATION_YEARS = Decimal("27.5")


def calculate_annual_depreciation(purchase_price: Decimal) -> Decimal:
    """
    Calculate annual tax depreciation for residential rental property
    Formula: purchase_price / 27.5 years
    """
    annual_depreciation = purchase_price / DEPRECIATION_YEARS
    logger.info(f"  Tax savings calc: ${purchase_price} ÷ 27.5 years = ${annual_depreciation:.2f}/year")
    return annual_depreciation


async def create_or_update_tax_savings(property_id: str, purchase_price: Decimal, purchase_date: date = None):
    """
    Create or update tax savings (depreciation) revenue item for a property
    
    Args:
        property_id: The property ID
        purchase_price: Property purchase price
        purchase_date: Date property was purchased (optional)
    """
    try:
        logger.info(f"💰 Creating/updating tax savings for property {property_id}")
        logger.info(f"  Purchase Price: ${purchase_price}")
        if purchase_date:
            logger.info(f"  Purchase Date: {purchase_date}")
        
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
                
                import pyarrow as pa
                arrow_table = pa.Table.from_pandas(df, preserve_index=False)
                arrow_table = arrow_table.cast(table_schema)
                table.overwrite(arrow_table)
        
        # Calculate annual depreciation
        annual_amount = calculate_annual_depreciation(purchase_price)
        
        # Create new tax savings revenue
        now = pd.Timestamp.now()
        notes = f"Residential rental depreciation: ${purchase_price} ÷ 27.5 years"
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
        
        logger.info(f"  ✅ Tax Depreciation: ${annual_amount:.2f}/year")
        
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
        
        import pyarrow as pa
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        arrow_table = arrow_table.cast(table_schema)
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Deleted tax savings for property {property_id}")
        
    except Exception as e:
        logger.error(f"❌ Error deleting tax savings: {e}", exc_info=True)

