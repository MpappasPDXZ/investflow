"""
Utility functions for managing vacancy-related expenses
"""
import uuid
import pandas as pd
from decimal import Decimal
from app.core.iceberg import append_data, read_table, load_table, table_exists
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
EXPENSES_TABLE = "scheduled_expenses"

logger = get_logger(__name__)

# Vacancy cost rates per square foot
VACANCY_RATES = {
    "Electricity": Decimal("0.10"),  # $0.10 per SF per month
    "Natural Gas": Decimal("0.07"),  # $0.07 per SF per month
    "Water": Decimal("0.02"),        # $0.02 per SF per month
}


def calculate_vacancy_annual_cost(square_feet: int, vacancy_rate: Decimal, utility_rate_per_sf: Decimal) -> Decimal:
    """
    Calculate annual vacancy cost for a utility
    Formula: 12 months × vacancy_rate × square_feet × utility_rate_per_sf
    """
    annual_cost = Decimal("12") * vacancy_rate * Decimal(str(square_feet)) * utility_rate_per_sf
    logger.info(f"  Vacancy calc: 12 × {vacancy_rate} × {square_feet} SF × ${utility_rate_per_sf}/SF = ${annual_cost:.2f}/year")
    return annual_cost


async def create_or_update_vacancy_expenses(property_id: str, square_feet: int, vacancy_rate: Decimal):
    """
    Create or update vacancy expense line items for a property
    
    Args:
        property_id: The property ID
        square_feet: Total square feet of the property
        vacancy_rate: Vacancy rate as decimal (e.g., 0.07 for 7%)
    """
    try:
        logger.info(f"🏠 Creating vacancy expenses for property {property_id}")
        logger.info(f"  Square Feet: {square_feet} SF")
        logger.info(f"  Vacancy Rate: {vacancy_rate} ({vacancy_rate*100}%)")
        
        if not square_feet or square_feet <= 0:
            logger.warning(f"  ⚠️  Property {property_id} has no square footage, skipping vacancy expenses")
            return
        
        # Check if vacancy expenses already exist
        if table_exists(NAMESPACE, EXPENSES_TABLE):
            df = read_table(NAMESPACE, EXPENSES_TABLE)
            existing_vacancy = df[
                (df["property_id"] == property_id) & 
                (df["expense_type"] == "vacancy")
            ]
            
            # Delete existing vacancy expenses for this property
            if not existing_vacancy.empty:
                logger.info(f"Removing {len(existing_vacancy)} existing vacancy expenses for property {property_id}")
                df = df[~((df["property_id"] == property_id) & (df["expense_type"] == "vacancy"))]
                
                # Overwrite table without the old vacancy expenses
                table = load_table(NAMESPACE, EXPENSES_TABLE)
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
                
                # Convert to PyArrow and cast to table schema
                import pyarrow as pa
                arrow_table = pa.Table.from_pandas(df, preserve_index=False)
                arrow_table = arrow_table.cast(table_schema)
                table.overwrite(arrow_table)
        
        # Create new vacancy expenses
        now = pd.Timestamp.now()
        vacancy_expenses = []
        
        for utility_name, rate_per_sf in VACANCY_RATES.items():
            logger.info(f"  📊 Calculating {utility_name} (${rate_per_sf}/SF/month):")
            annual_cost = calculate_vacancy_annual_cost(square_feet, vacancy_rate, rate_per_sf)
            
            expense_dict = {
                "id": str(uuid.uuid4()),
                "property_id": property_id,
                "expense_type": "vacancy",
                "item_name": utility_name,
                "purchase_price": None,
                "depreciation_rate": None,
                "count": None,
                "annual_cost": annual_cost,
                "principal": None,
                "interest_rate": None,
                "notes": f"Auto-generated vacancy cost: ${rate_per_sf}/SF × {square_feet} SF × {vacancy_rate*100}% vacancy",
                "created_at": now,
                "updated_at": now,
                "is_active": True,
            }
            vacancy_expenses.append(expense_dict)
            logger.info(f"  ✅ {utility_name}: ${annual_cost:.2f}/year")
        
        # Append new vacancy expenses to table
        if vacancy_expenses:
            df_new = pd.DataFrame(vacancy_expenses)
            append_data(NAMESPACE, EXPENSES_TABLE, df_new)
            logger.info(f"✅ Created {len(vacancy_expenses)} vacancy expenses for property {property_id}")
        else:
            logger.warning(f"⚠️  No vacancy expenses created for property {property_id}")
        
    except Exception as e:
        logger.error(f"❌ Error creating vacancy expenses: {e}", exc_info=True)
        # Don't raise - this is a background operation that shouldn't break property creation


async def delete_vacancy_expenses(property_id: str):
    """
    Delete all vacancy expenses for a property
    """
    try:
        if not table_exists(NAMESPACE, EXPENSES_TABLE):
            return
        
        df = read_table(NAMESPACE, EXPENSES_TABLE)
        existing_vacancy = df[
            (df["property_id"] == property_id) & 
            (df["expense_type"] == "vacancy")
        ]
        
        if existing_vacancy.empty:
            return
        
        logger.info(f"Deleting {len(existing_vacancy)} vacancy expenses for property {property_id}")
        df = df[~((df["property_id"] == property_id) & (df["expense_type"] == "vacancy"))]
        
        # Overwrite table
        table = load_table(NAMESPACE, EXPENSES_TABLE)
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
        
        logger.info(f"✅ Deleted vacancy expenses for property {property_id}")
        
    except Exception as e:
        logger.error(f"❌ Error deleting vacancy expenses: {e}", exc_info=True)

