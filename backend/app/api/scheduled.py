"""
API endpoints for scheduled expenses and revenue
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.dependencies import get_current_user
from app.schemas.scheduled import (
    ScheduledExpenseCreate, ScheduledExpenseUpdate, ScheduledExpenseResponse, ScheduledExpenseListResponse,
    ScheduledRevenueCreate, ScheduledRevenueUpdate, ScheduledRevenueResponse, ScheduledRevenueListResponse
)
from app.core.iceberg import get_catalog, read_table, table_exists
from app.core.logging import get_logger
from decimal import Decimal
from datetime import datetime
import uuid
import pandas as pd
import pyarrow as pa
from pyiceberg.types import DecimalType, StringType, TimestampType, BooleanType, DoubleType

logger = get_logger(__name__)
router = APIRouter()

NAMESPACE = ("investflow",)
EXPENSES_TABLE = "scheduled_expenses"
REVENUE_TABLE = "scheduled_revenue"

# Strict field order for scheduled_expenses table (must match Iceberg schema exactly)
# ACTUAL TABLE ORDER (from error message):
# id, property_id, expense_type, item_name, purchase_price, depreciation_rate,
# count, annual_cost, principal, interest_rate, notes, created_at, updated_at, is_active
SCHEDULED_EXPENSES_FIELD_ORDER = [
    "id",
    "property_id",
    "expense_type",
    "item_name",
    "purchase_price",
    "depreciation_rate",
    "count",
    "annual_cost",
    "principal",
    "interest_rate",
    "notes",
    "created_at",
    "updated_at",
    "is_active",
]

# Strict field order for scheduled_revenue table (must match Iceberg schema exactly)
# ACTUAL TABLE ORDER (from error message):
# id, property_id, revenue_type, item_name, annual_amount, appreciation_rate,
# property_value, value_added_amount, notes, created_at, updated_at, is_active
SCHEDULED_REVENUE_FIELD_ORDER = [
    "id",
    "property_id",
    "revenue_type",
    "item_name",
    "annual_amount",
    "appreciation_rate",
    "property_value",
    "value_added_amount",
    "notes",
    "created_at",
    "updated_at",
    "is_active",
]


# ========== DEDICATED SCHEDULED REVENUE ICEBERG FUNCTIONS ==========

def _load_scheduled_revenue_table():
    """Load the scheduled_revenue Iceberg table (dedicated function)"""
    catalog = get_catalog()
    table_identifier = (*NAMESPACE, REVENUE_TABLE)
    return catalog.load_table(table_identifier)


def _append_scheduled_revenue(revenue_dict: dict):
    """Append a scheduled revenue with strict field ordering (dedicated function)"""
    try:
        table = _load_scheduled_revenue_table()
        current_schema = table.schema()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        logger.info(f"📋 [SCHEDULED_REVENUE] Actual table schema order: {actual_field_order}")
        logger.info(f"📋 [SCHEDULED_REVENUE] Expected field order: {SCHEDULED_REVENUE_FIELD_ORDER}")
        logger.info(f"📋 [SCHEDULED_REVENUE] Revenue dict keys: {list(revenue_dict.keys())}")
        
        # Verify order matches
        if actual_field_order != SCHEDULED_REVENUE_FIELD_ORDER:
            logger.warning(f"⚠️ [SCHEDULED_REVENUE] Field order mismatch! Using actual table order.")
            logger.warning(f"   Expected: {SCHEDULED_REVENUE_FIELD_ORDER}")
            logger.warning(f"   Actual:   {actual_field_order}")
        
        # Build DataFrame with fields in exact order matching ACTUAL table schema
        ordered_dict = {}
        for field_name in actual_field_order:
            if field_name in revenue_dict:
                ordered_dict[field_name] = revenue_dict[field_name]
            else:
                ordered_dict[field_name] = None
        
        df = pd.DataFrame([ordered_dict])
        
        # Ensure DataFrame columns are in exact order matching table schema
        df = df[actual_field_order]
        
        # Convert timestamp columns to microseconds (handle both timezone-aware and naive)
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                # Convert to datetime if not already, handling both timezone-aware and naive
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                # Ensure microseconds precision
                df[col] = df[col].dt.floor('us')
        
        # Convert decimal columns to float64 (double) for PyArrow compatibility
        decimal_cols = ['annual_amount', 'appreciation_rate', 'property_value', 'value_added_amount']
        for col in decimal_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        table.append(arrow_table)
    except Exception as e:
        logger.error(f"Failed to append scheduled revenue: {e}", exc_info=True)
        raise


def _overwrite_scheduled_revenue_table(revenue_df: pd.DataFrame):
    """Overwrite scheduled revenue table with strict field ordering (dedicated function)"""
    try:
        table = _load_scheduled_revenue_table()
        current_schema = table.schema()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        logger.info(f"📋 [SCHEDULED_REVENUE] Overwrite - Actual table schema order: {actual_field_order}")
        logger.info(f"📋 [SCHEDULED_REVENUE] Overwrite - DataFrame columns: {list(revenue_df.columns)}")
        
        # Ensure DataFrame has all required fields in exact order
        for field_name in actual_field_order:
            if field_name not in revenue_df.columns:
                revenue_df[field_name] = None
        
        # Reorder columns to match exact schema order
        revenue_df = revenue_df[actual_field_order]
        
        # Convert timestamp columns to microseconds (handle both timezone-aware and naive)
        for col in ['created_at', 'updated_at']:
            if col in revenue_df.columns:
                # Convert to datetime if not already, handling both timezone-aware and naive
                revenue_df[col] = pd.to_datetime(revenue_df[col], utc=True).dt.tz_localize(None)
                # Ensure microseconds precision
                revenue_df[col] = revenue_df[col].dt.floor('us')
        
        # Convert decimal columns to float64 for PyArrow compatibility
        decimal_cols = ['annual_amount', 'appreciation_rate', 'property_value', 'value_added_amount']
        for col in decimal_cols:
            if col in revenue_df.columns:
                # Convert object/Decimal columns to float64
                revenue_df[col] = pd.to_numeric(revenue_df[col], errors='coerce')
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(revenue_df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        table.overwrite(arrow_table)
    except Exception as e:
        logger.error(f"Failed to overwrite scheduled revenue table: {e}", exc_info=True)
        raise


# ========== DEDICATED SCHEDULED EXPENSES ICEBERG FUNCTIONS ==========

def _load_scheduled_expenses_table():
    """Load the scheduled_expenses Iceberg table (dedicated function)"""
    catalog = get_catalog()
    table_identifier = (*NAMESPACE, EXPENSES_TABLE)
    return catalog.load_table(table_identifier)


def _log_scheduled_expenses_schema():
    """Log the actual scheduled_expenses table schema for verification"""
    try:
        table = _load_scheduled_expenses_table()
        table_schema = table.schema().as_arrow()
        actual_field_order = [f.name for f in table_schema]
        logger.info("=" * 80)
        logger.info("📋 [SCHEDULED_EXPENSES] ACTUAL TABLE SCHEMA ORDER:")
        logger.info("=" * 80)
        for i, field in enumerate(table_schema, 1):
            field_type = str(field.type)
            nullable = "nullable" if field.nullable else "required"
            logger.info(f"  {i:2d}. {field.name:<30} {field_type:<25} ({nullable})")
        logger.info("=" * 80)
        logger.info(f"Total columns: {len(actual_field_order)}")
        logger.info(f"Expected order: {SCHEDULED_EXPENSES_FIELD_ORDER}")
        logger.info(f"Actual order:   {actual_field_order}")
        logger.info("=" * 80)
        return actual_field_order
    except Exception as e:
        logger.error(f"Failed to log scheduled_expenses schema: {e}", exc_info=True)
        return None


def _read_scheduled_expenses_table() -> pd.DataFrame:
    """Read all scheduled expenses from Iceberg table (dedicated function)"""
    try:
        table = _load_scheduled_expenses_table()
        scan = table.scan()
        arrow_table = scan.to_arrow()
        return arrow_table.to_pandas()
    except Exception as e:
        logger.error(f"Failed to read scheduled_expenses table: {e}", exc_info=True)
        raise


def _append_scheduled_expense(expense_dict: dict):
    """Append a scheduled expense with strict field ordering (dedicated function)"""
    try:
        table = _load_scheduled_expenses_table()
        current_schema = table.schema()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        logger.info(f"📋 [SCHEDULED_EXPENSE] Actual table schema order: {actual_field_order}")
        logger.info(f"📋 [SCHEDULED_EXPENSE] Expected field order: {SCHEDULED_EXPENSES_FIELD_ORDER}")
        logger.info(f"📋 [SCHEDULED_EXPENSE] Expense dict keys: {list(expense_dict.keys())}")
        
        # Verify order matches
        if actual_field_order != SCHEDULED_EXPENSES_FIELD_ORDER:
            logger.warning(f"⚠️ [SCHEDULED_EXPENSE] Field order mismatch! Using actual table order.")
            logger.warning(f"   Expected: {SCHEDULED_EXPENSES_FIELD_ORDER}")
            logger.warning(f"   Actual:   {actual_field_order}")
        
        # Build DataFrame with fields in exact order matching ACTUAL table schema
        ordered_dict = {}
        for field_name in actual_field_order:
            if field_name in expense_dict:
                ordered_dict[field_name] = expense_dict[field_name]
            else:
                ordered_dict[field_name] = None
        
        df = pd.DataFrame([ordered_dict])
        
        # Ensure DataFrame columns are in exact order matching table schema
        df = df[actual_field_order]
        
        # Convert timestamp columns to microseconds (handle both timezone-aware and naive)
        for col in ['created_at', 'updated_at']:
            if col in df.columns:
                # Convert to datetime if not already, handling both timezone-aware and naive
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
                # Ensure microseconds precision
                df[col] = df[col].dt.floor('us')
        
        # Convert decimal columns
        from decimal import Decimal as PythonDecimal
        decimal_cols = ['purchase_price', 'depreciation_rate', 'annual_cost', 'principal', 'interest_rate']
        for col in decimal_cols:
            if col in df.columns:
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(float(x)))
                    except (ValueError, TypeError):
                        return None
                df[col] = df[col].apply(to_decimal)
        
        # Convert count to float64 (double)
        if 'count' in df.columns:
            df['count'] = pd.to_numeric(df['count'], errors='coerce')
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        table.append(arrow_table)
    except Exception as e:
        logger.error(f"Failed to append scheduled expense: {e}", exc_info=True)
        raise


def _overwrite_scheduled_expenses_table(expenses_df: pd.DataFrame):
    """Overwrite scheduled expenses table with strict field ordering (dedicated function)"""
    try:
        table = _load_scheduled_expenses_table()
        current_schema = table.schema()
        table_schema = table.schema().as_arrow()
        
        # Get actual table schema field order
        actual_field_order = [f.name for f in table_schema]
        logger.info(f"📋 [SCHEDULED_EXPENSE] Overwrite - Actual table schema order: {actual_field_order}")
        
        # Ensure DataFrame has all required fields in exact order
        for field_name in actual_field_order:
            if field_name not in expenses_df.columns:
                expenses_df[field_name] = None
        
        # Reorder columns to match exact schema order
        expenses_df = expenses_df[actual_field_order]
        
        # Convert timestamp columns to microseconds (handle both timezone-aware and naive)
        for col in ['created_at', 'updated_at']:
            if col in expenses_df.columns:
                # Convert to datetime if not already, handling both timezone-aware and naive
                expenses_df[col] = pd.to_datetime(expenses_df[col], utc=True).dt.tz_localize(None)
                # Ensure microseconds precision
                expenses_df[col] = expenses_df[col].dt.floor('us')
        
        # Convert decimal columns
        from decimal import Decimal as PythonDecimal
        decimal_cols = ['purchase_price', 'depreciation_rate', 'annual_cost', 'principal', 'interest_rate']
        for col in decimal_cols:
            if col in expenses_df.columns:
                expenses_df[col] = pd.to_numeric(expenses_df[col], errors='coerce')
                def to_decimal(x):
                    if pd.isna(x) or x is None:
                        return None
                    try:
                        return PythonDecimal(str(float(x)))
                    except (ValueError, TypeError):
                        return None
                expenses_df[col] = expenses_df[col].apply(to_decimal)
        
        # Convert count to float64 (double)
        if 'count' in expenses_df.columns:
            expenses_df['count'] = pd.to_numeric(expenses_df['count'], errors='coerce')
        
        # Convert to PyArrow and cast to schema
        arrow_table = pa.Table.from_pandas(expenses_df)
        table_schema = table.schema().as_arrow()
        arrow_table = arrow_table.cast(table_schema)
        
        table.overwrite(arrow_table)
    except Exception as e:
        logger.error(f"Failed to overwrite scheduled expenses table: {e}", exc_info=True)
        raise


# ========== SCHEDULED EXPENSES ENDPOINTS ==========

@router.post("/scheduled-expenses", response_model=ScheduledExpenseResponse)
async def create_scheduled_expense(
    expense_data: ScheduledExpenseCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new scheduled expense"""
    try:
        # Log actual table schema for verification (first time only, cached)
        if not hasattr(create_scheduled_expense, '_schema_logged'):
            _log_scheduled_expenses_schema()
            create_scheduled_expense._schema_logged = True
        user_id = current_user["sub"]
        user_email = current_user["email"]
        logger.info(f"Creating scheduled expense for property {expense_data.property_id}")
        
        # Verify property exists and user has access
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            raise HTTPException(status_code=404, detail="Properties table is empty")
        
        property_match = properties_df[properties_df['id'] == expense_data.property_id]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_user_id = str(property_match.iloc[0]['user_id'])
        
        # Check access: owner OR bidirectional share
        from app.api.sharing_utils import user_has_property_access
        if not user_has_property_access(property_user_id, user_id, user_email):
            raise HTTPException(status_code=404, detail="Property not found or no access")
        
        # Create expense record with strict field ordering
        expense_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Build expense_dict in EXACT field order (matching ACTUAL table schema)
        # Order: id, property_id, expense_type, item_name, purchase_price, depreciation_rate,
        # count, annual_cost, principal, interest_rate, notes, created_at, updated_at, is_active
        expense_dict = {}
        for field_name in SCHEDULED_EXPENSES_FIELD_ORDER:
            if field_name == "id":
                expense_dict[field_name] = expense_id
            elif field_name == "property_id":
                expense_dict[field_name] = expense_data.property_id
            elif field_name == "expense_type":
                expense_dict[field_name] = expense_data.expense_type
            elif field_name == "item_name":
                expense_dict[field_name] = expense_data.item_name
            elif field_name == "purchase_price":
                expense_dict[field_name] = expense_data.purchase_price
            elif field_name == "depreciation_rate":
                expense_dict[field_name] = expense_data.depreciation_rate
            elif field_name == "count":
                expense_dict[field_name] = expense_data.count
            elif field_name == "annual_cost":
                expense_dict[field_name] = expense_data.annual_cost
            elif field_name == "principal":
                expense_dict[field_name] = expense_data.principal
            elif field_name == "interest_rate":
                expense_dict[field_name] = expense_data.interest_rate
            elif field_name == "notes":
                expense_dict[field_name] = expense_data.notes
            elif field_name == "created_at":
                expense_dict[field_name] = now
            elif field_name == "updated_at":
                expense_dict[field_name] = now
            elif field_name == "is_active":
                expense_dict[field_name] = True
        
        # Append using dedicated function
        _append_scheduled_expense(expense_dict)
        
        logger.info(f"✅ Scheduled expense created: {expense_id}")
        
        # If P&I expense, automatically create/update principal paydown revenue
        if expense_data.expense_type == 'pi' and expense_data.principal and expense_data.interest_rate:
            try:
                logger.info(f"💰 Processing P&I expense - creating/updating principal paydown revenue")
                principal_decimal = Decimal(str(expense_data.principal))
                interest_rate_decimal = Decimal(str(expense_data.interest_rate))
                logger.info(f"   Principal: {principal_decimal}, Interest Rate: {interest_rate_decimal}")
                
                # Calculate amortized payment
                monthly_payment = calculate_monthly_amortized_payment(principal_decimal, interest_rate_decimal)
                annual_payment = monthly_payment * Decimal('12')
                logger.info(f"   Monthly payment: {monthly_payment}, Annual payment: {annual_payment}")
                
                # Calculate principal paydown (annual payment - annual interest)
                annual_interest = principal_decimal * interest_rate_decimal
                principal_paydown = annual_payment - annual_interest
                logger.info(f"   Annual interest: {annual_interest}, Principal paydown: {principal_paydown}")
                
                # Check if principal_paydown revenue already exists for this property
                revenue_df = read_table(NAMESPACE, REVENUE_TABLE)
                logger.info(f"   Revenue table read: {len(revenue_df) if revenue_df is not None and not revenue_df.empty else 0} rows")
                
                existing_revenue = None
                if revenue_df is not None and not revenue_df.empty:
                    existing_revenue = revenue_df[
                        (revenue_df['property_id'] == expense_data.property_id) &
                        (revenue_df['revenue_type'] == 'principal_paydown') &
                        (revenue_df['is_active'] == True)
                    ]
                    logger.info(f"   Found existing principal_paydown revenue: {len(existing_revenue)} rows")
                
                if existing_revenue is not None and not existing_revenue.empty:
                    # Update existing revenue
                    revenue_id = existing_revenue.iloc[0]['id']
                    revenue_idx = revenue_df[revenue_df['id'] == revenue_id].index[0]
                    revenue_df.loc[revenue_idx, 'annual_amount'] = float(principal_paydown)
                    revenue_df.loc[revenue_idx, 'updated_at'] = datetime.utcnow()
                    _overwrite_scheduled_revenue_table(revenue_df)
                    logger.info(f"✅ Updated principal paydown revenue: {revenue_id} with amount: {principal_paydown}")
                else:
                    # Create new revenue
                    revenue_id = str(uuid.uuid4())
                    revenue_dict = {}
                    for field_name in SCHEDULED_REVENUE_FIELD_ORDER:
                        if field_name == "id":
                            revenue_dict[field_name] = revenue_id
                        elif field_name == "property_id":
                            revenue_dict[field_name] = expense_data.property_id
                        elif field_name == "revenue_type":
                            revenue_dict[field_name] = "principal_paydown"
                        elif field_name == "item_name":
                            revenue_dict[field_name] = "Principal Paydown"
                        elif field_name == "annual_amount":
                            revenue_dict[field_name] = float(principal_paydown)
                        elif field_name == "appreciation_rate":
                            revenue_dict[field_name] = None
                        elif field_name == "property_value":
                            revenue_dict[field_name] = None
                        elif field_name == "value_added_amount":
                            revenue_dict[field_name] = None
                        elif field_name == "notes":
                            revenue_dict[field_name] = f"Auto-generated from P&I expense: {expense_data.item_name}"
                        elif field_name == "created_at":
                            revenue_dict[field_name] = datetime.utcnow()
                        elif field_name == "updated_at":
                            revenue_dict[field_name] = datetime.utcnow()
                        elif field_name == "is_active":
                            revenue_dict[field_name] = True
                    
                    logger.info(f"   Creating revenue with dict: {revenue_dict}")
                    _append_scheduled_revenue(revenue_dict)
                    logger.info(f"✅ Created principal paydown revenue: {revenue_id} with amount: {principal_paydown}")
            except Exception as e:
                logger.error(f"❌ Failed to create/update principal paydown revenue: {e}", exc_info=True)
                # Don't fail the expense creation if revenue creation fails
        
        # Calculate annual cost
        calculated_cost = calculate_expense_annual_cost(expense_dict)
        
        return ScheduledExpenseResponse(
            **expense_dict,
            calculated_annual_cost=calculated_cost
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating scheduled expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-expenses", response_model=ScheduledExpenseListResponse)
async def list_scheduled_expenses(
    property_id: str = Query(..., description="Property ID"),
    current_user: dict = Depends(get_current_user)
):
    """List all scheduled expenses for a property"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Fetching scheduled expenses for property {property_id}")
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            return ScheduledExpenseListResponse(items=[], total=0)
        
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read expenses using dedicated function
        expenses_df = _read_scheduled_expenses_table()
        if expenses_df is None or expenses_df.empty:
            return ScheduledExpenseListResponse(items=[], total=0)
        
        # Filter by property_id and is_active
        expenses_df = expenses_df[
            (expenses_df['property_id'] == property_id) & 
            (expenses_df['is_active'] == True)
        ]
        
        if expenses_df.empty:
            return ScheduledExpenseListResponse(items=[], total=0)
        
        # Convert to response models
        items = []
        for _, row in expenses_df.iterrows():
            expense_dict = row.to_dict()
            # Replace NaN with None for Pydantic validation
            expense_dict = {k: (None if pd.isna(v) else v) for k, v in expense_dict.items()}
            calculated_cost = calculate_expense_annual_cost(expense_dict)
            items.append(ScheduledExpenseResponse(**expense_dict, calculated_annual_cost=calculated_cost))
        
        return ScheduledExpenseListResponse(items=items, total=len(items))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing scheduled expenses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-expenses/{expense_id}", response_model=ScheduledExpenseResponse)
async def get_scheduled_expense(
    expense_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific scheduled expense"""
    try:
        user_id = current_user["sub"]
        expenses_df = _read_scheduled_expenses_table()
        if expenses_df is None or expenses_df.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        expense_row = expenses_df[expenses_df['id'] == expense_id]
        if expense_row.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Verify property belongs to user
        property_id = expense_row.iloc[0]['property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        expense_dict = expense_row.iloc[0].to_dict()
        # Replace NaN with None for Pydantic validation
        expense_dict = {k: (None if pd.isna(v) else v) for k, v in expense_dict.items()}
        calculated_cost = calculate_expense_annual_cost(expense_dict)
        
        return ScheduledExpenseResponse(**expense_dict, calculated_annual_cost=calculated_cost)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching scheduled expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scheduled-expenses/{expense_id}", response_model=ScheduledExpenseResponse)
async def update_scheduled_expense(
    expense_id: str,
    expense_update: ScheduledExpenseUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a scheduled expense"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Updating scheduled expense {expense_id}")
        
        # Read all expenses using dedicated function
        expenses_df = _read_scheduled_expenses_table()
        
        if expenses_df is None or expenses_df.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Find the expense
        expense_idx = expenses_df[expenses_df['id'] == expense_id].index
        if expense_idx.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Verify property belongs to user
        property_id = expenses_df.loc[expense_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Update fields
        update_data = expense_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            expenses_df.loc[expense_idx[0], field] = value
        
        # Update timestamp
        expenses_df.loc[expense_idx[0], 'updated_at'] = datetime.utcnow()
        
        # Overwrite using dedicated function (handles field ordering and type conversion)
        _overwrite_scheduled_expenses_table(expenses_df)
        
        logger.info(f"✅ Scheduled expense updated: {expense_id}")
        
        # Return updated expense
        updated_row = expenses_df.loc[expense_idx[0]].to_dict()
        # Replace NaN with None for Pydantic validation
        updated_row = {k: (None if pd.isna(v) else v) for k, v in updated_row.items()}
        
        # If P&I expense was updated, automatically update principal paydown revenue
        if updated_row.get('expense_type') == 'pi' and updated_row.get('principal') and updated_row.get('interest_rate'):
            try:
                logger.info(f"💰 Processing P&I expense update - creating/updating principal paydown revenue")
                principal_decimal = Decimal(str(updated_row['principal']))
                interest_rate_decimal = Decimal(str(updated_row['interest_rate']))
                logger.info(f"   Principal: {principal_decimal}, Interest Rate: {interest_rate_decimal}")
                
                # Calculate amortized payment
                monthly_payment = calculate_monthly_amortized_payment(principal_decimal, interest_rate_decimal)
                annual_payment = monthly_payment * Decimal('12')
                logger.info(f"   Monthly payment: {monthly_payment}, Annual payment: {annual_payment}")
                
                # Calculate principal paydown (annual payment - annual interest)
                annual_interest = principal_decimal * interest_rate_decimal
                principal_paydown = annual_payment - annual_interest
                logger.info(f"   Annual interest: {annual_interest}, Principal paydown: {principal_paydown}")
                
                # Check if principal_paydown revenue exists for this property
                revenue_df = read_table(NAMESPACE, REVENUE_TABLE)
                logger.info(f"   Revenue table read: {len(revenue_df) if revenue_df is not None and not revenue_df.empty else 0} rows")
                
                if revenue_df is not None and not revenue_df.empty:
                    existing_revenue = revenue_df[
                        (revenue_df['property_id'] == updated_row['property_id']) &
                        (revenue_df['revenue_type'] == 'principal_paydown') &
                        (revenue_df['is_active'] == True)
                    ]
                    logger.info(f"   Found existing principal_paydown revenue: {len(existing_revenue)} rows")
                    
                    if not existing_revenue.empty:
                        # Update existing revenue
                        revenue_id = existing_revenue.iloc[0]['id']
                        revenue_idx = revenue_df[revenue_df['id'] == revenue_id].index[0]
                        revenue_df.loc[revenue_idx, 'annual_amount'] = float(principal_paydown)
                        revenue_df.loc[revenue_idx, 'updated_at'] = datetime.utcnow()
                        _overwrite_scheduled_revenue_table(revenue_df)
                        logger.info(f"✅ Updated principal paydown revenue: {revenue_id} with amount: {principal_paydown}")
                    else:
                        # Create new revenue
                        revenue_id = str(uuid.uuid4())
                        revenue_dict = {}
                        for field_name in SCHEDULED_REVENUE_FIELD_ORDER:
                            if field_name == "id":
                                revenue_dict[field_name] = revenue_id
                            elif field_name == "property_id":
                                revenue_dict[field_name] = updated_row['property_id']
                            elif field_name == "revenue_type":
                                revenue_dict[field_name] = "principal_paydown"
                            elif field_name == "item_name":
                                revenue_dict[field_name] = "Principal Paydown"
                            elif field_name == "annual_amount":
                                revenue_dict[field_name] = float(principal_paydown)
                            elif field_name == "appreciation_rate":
                                revenue_dict[field_name] = None
                            elif field_name == "property_value":
                                revenue_dict[field_name] = None
                            elif field_name == "value_added_amount":
                                revenue_dict[field_name] = None
                            elif field_name == "notes":
                                revenue_dict[field_name] = f"Auto-generated from P&I expense: {updated_row.get('item_name', 'P&I')}"
                            elif field_name == "created_at":
                                revenue_dict[field_name] = datetime.utcnow()
                            elif field_name == "updated_at":
                                revenue_dict[field_name] = datetime.utcnow()
                            elif field_name == "is_active":
                                revenue_dict[field_name] = True
                        
                        logger.info(f"   Creating revenue with dict: {revenue_dict}")
                        _append_scheduled_revenue(revenue_dict)
                        logger.info(f"✅ Created principal paydown revenue: {revenue_id} with amount: {principal_paydown}")
                else:
                    # Create new revenue if table is empty
                    revenue_id = str(uuid.uuid4())
                    revenue_dict = {}
                    for field_name in SCHEDULED_REVENUE_FIELD_ORDER:
                        if field_name == "id":
                            revenue_dict[field_name] = revenue_id
                        elif field_name == "property_id":
                            revenue_dict[field_name] = updated_row['property_id']
                        elif field_name == "revenue_type":
                            revenue_dict[field_name] = "principal_paydown"
                        elif field_name == "item_name":
                            revenue_dict[field_name] = "Principal Paydown"
                        elif field_name == "annual_amount":
                            revenue_dict[field_name] = float(principal_paydown)
                        elif field_name == "appreciation_rate":
                            revenue_dict[field_name] = None
                        elif field_name == "property_value":
                            revenue_dict[field_name] = None
                        elif field_name == "value_added_amount":
                            revenue_dict[field_name] = None
                        elif field_name == "notes":
                            revenue_dict[field_name] = f"Auto-generated from P&I expense: {updated_row.get('item_name', 'P&I')}"
                        elif field_name == "created_at":
                            revenue_dict[field_name] = datetime.utcnow()
                        elif field_name == "updated_at":
                            revenue_dict[field_name] = datetime.utcnow()
                        elif field_name == "is_active":
                            revenue_dict[field_name] = True
                    
                    logger.info(f"   Creating revenue with dict: {revenue_dict}")
                    _append_scheduled_revenue(revenue_dict)
                    logger.info(f"✅ Created principal paydown revenue: {revenue_id} with amount: {principal_paydown}")
            except Exception as e:
                logger.error(f"❌ Failed to create/update principal paydown revenue: {e}", exc_info=True)
                # Don't fail the expense update if revenue update fails
        
        calculated_cost = calculate_expense_annual_cost(updated_row)
        
        return ScheduledExpenseResponse(**updated_row, calculated_annual_cost=calculated_cost)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating scheduled expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled-expenses/{expense_id}")
async def delete_scheduled_expense(
    expense_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete (soft delete) a scheduled expense"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Deleting scheduled expense {expense_id}")
        
        # Read all expenses using dedicated function
        expenses_df = _read_scheduled_expenses_table()
        
        if expenses_df is None or expenses_df.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Find the expense
        expense_idx = expenses_df[expenses_df['id'] == expense_id].index
        if expense_idx.empty:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Verify property belongs to user
        property_id = expenses_df.loc[expense_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Soft delete
        expenses_df.loc[expense_idx[0], 'is_active'] = False
        # Update timestamp
        expenses_df.loc[expense_idx[0], 'updated_at'] = datetime.utcnow()
        
        # Overwrite using dedicated function (handles field ordering and type conversion)
        _overwrite_scheduled_expenses_table(expenses_df)
        
        logger.info(f"✅ Scheduled expense deleted: {expense_id}")
        
        return {"message": "Scheduled expense deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting scheduled expense: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== SCHEDULED REVENUE ENDPOINTS ==========

@router.post("/scheduled-revenue", response_model=ScheduledRevenueResponse)
async def create_scheduled_revenue(
    revenue_data: ScheduledRevenueCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new scheduled revenue"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Creating scheduled revenue for property {revenue_data.property_id}")
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            raise HTTPException(status_code=404, detail="Properties table is empty")
        
        property_match = properties_df[
            (properties_df['id'] == revenue_data.property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Create revenue record with strict field ordering
        revenue_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Build revenue_dict in EXACT field order (matching SCHEDULED_REVENUE_FIELD_ORDER)
        revenue_dict = {}
        for field_name in SCHEDULED_REVENUE_FIELD_ORDER:
            if field_name == "id":
                revenue_dict[field_name] = revenue_id
            elif field_name == "property_id":
                revenue_dict[field_name] = revenue_data.property_id
            elif field_name == "revenue_type":
                revenue_dict[field_name] = revenue_data.revenue_type
            elif field_name == "item_name":
                revenue_dict[field_name] = revenue_data.item_name
            elif field_name == "notes":
                revenue_dict[field_name] = revenue_data.notes
            elif field_name == "is_active":
                revenue_dict[field_name] = True
            elif field_name == "annual_amount":
                revenue_dict[field_name] = revenue_data.annual_amount
            elif field_name == "appreciation_rate":
                revenue_dict[field_name] = revenue_data.appreciation_rate
            elif field_name == "property_value":
                revenue_dict[field_name] = revenue_data.property_value
            elif field_name == "value_added_amount":
                revenue_dict[field_name] = revenue_data.value_added_amount
            elif field_name == "created_at":
                revenue_dict[field_name] = now
            elif field_name == "updated_at":
                revenue_dict[field_name] = now
        
        # Append using dedicated function (handles field ordering and type conversion)
        _append_scheduled_revenue(revenue_dict)
        
        logger.info(f"✅ Scheduled revenue created: {revenue_id}")
        
        # Calculate annual amount
        calculated_amount = calculate_revenue_annual_amount(revenue_dict)
        
        return ScheduledRevenueResponse(
            **revenue_dict,
            calculated_annual_amount=calculated_amount
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating scheduled revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-revenue", response_model=ScheduledRevenueListResponse)
async def list_scheduled_revenue(
    property_id: str = Query(..., description="Property ID"),
    current_user: dict = Depends(get_current_user)
):
    """List all scheduled revenue for a property"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Fetching scheduled revenue for property {property_id}")
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            return ScheduledRevenueListResponse(items=[], total=0)
        
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Read revenue
        revenue_df = read_table(NAMESPACE, REVENUE_TABLE)
        if revenue_df is None or revenue_df.empty:
            return ScheduledRevenueListResponse(items=[], total=0)
        
        # Filter by property_id and is_active
        revenue_df = revenue_df[
            (revenue_df['property_id'] == property_id) & 
            (revenue_df['is_active'] == True)
        ]
        
        if revenue_df.empty:
            return ScheduledRevenueListResponse(items=[], total=0)
        
        # Convert to response models
        items = []
        for _, row in revenue_df.iterrows():
            revenue_dict = row.to_dict()
            # Replace NaN with None for Pydantic validation
            revenue_dict = {k: (None if pd.isna(v) else v) for k, v in revenue_dict.items()}
            calculated_amount = calculate_revenue_annual_amount(revenue_dict)
            items.append(ScheduledRevenueResponse(**revenue_dict, calculated_annual_amount=calculated_amount))
        
        return ScheduledRevenueListResponse(items=items, total=len(items))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing scheduled revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scheduled-revenue/{revenue_id}", response_model=ScheduledRevenueResponse)
async def update_scheduled_revenue(
    revenue_id: str,
    revenue_update: ScheduledRevenueUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a scheduled revenue"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Updating scheduled revenue {revenue_id}")
        
        # Read all revenue using dedicated function
        table = _load_scheduled_revenue_table()
        revenue_df = read_table(NAMESPACE, REVENUE_TABLE)
        
        if revenue_df is None or revenue_df.empty:
            raise HTTPException(status_code=404, detail="Revenue not found")
        
        # Find the revenue
        revenue_idx = revenue_df[revenue_df['id'] == revenue_id].index
        if revenue_idx.empty:
            raise HTTPException(status_code=404, detail="Revenue not found")
        
        # Verify property belongs to user
        property_id = revenue_df.loc[revenue_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Update fields
        update_data = revenue_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            revenue_df.loc[revenue_idx[0], field] = value
        
        # Update timestamp
        revenue_df.loc[revenue_idx[0], 'updated_at'] = datetime.utcnow()
        
        # Overwrite using dedicated function (handles field ordering and type conversion)
        _overwrite_scheduled_revenue_table(revenue_df)
        
        logger.info(f"✅ Scheduled revenue updated: {revenue_id}")
        
        # Return updated revenue
        updated_row = revenue_df.loc[revenue_idx[0]].to_dict()
        # Replace NaN with None for Pydantic validation
        updated_row = {k: (None if pd.isna(v) else v) for k, v in updated_row.items()}
        calculated_amount = calculate_revenue_annual_amount(updated_row)
        
        return ScheduledRevenueResponse(**updated_row, calculated_annual_amount=calculated_amount)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating scheduled revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scheduled-revenue/{revenue_id}")
async def delete_scheduled_revenue(
    revenue_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete (soft delete) a scheduled revenue"""
    try:
        user_id = current_user["sub"]
        logger.info(f"Deleting scheduled revenue {revenue_id}")
        
        # Read all revenue using dedicated function
        table = _load_scheduled_revenue_table()
        revenue_df = read_table(NAMESPACE, REVENUE_TABLE)
        
        if revenue_df is None or revenue_df.empty:
            raise HTTPException(status_code=404, detail="Revenue not found")
        
        # Find the revenue
        revenue_idx = revenue_df[revenue_df['id'] == revenue_id].index
        if revenue_idx.empty:
            raise HTTPException(status_code=404, detail="Revenue not found")
        
        # Verify property belongs to user
        property_id = revenue_df.loc[revenue_idx[0], 'property_id']
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Soft delete
        revenue_df.loc[revenue_idx[0], 'is_active'] = False
        # Update timestamp
        revenue_df.loc[revenue_idx[0], 'updated_at'] = datetime.utcnow()
        
        # Overwrite using dedicated function (handles field ordering and type conversion)
        _overwrite_scheduled_revenue_table(revenue_df)
        
        logger.info(f"✅ Scheduled revenue deleted: {revenue_id}")
        
        return {"message": "Scheduled revenue deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting scheduled revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== HELPER FUNCTIONS ==========

def calculate_monthly_amortized_payment(principal: Decimal, interest_rate: Decimal, loan_term_years: int = 30) -> Decimal:
    """Calculate monthly amortized payment using standard mortgage formula"""
    if principal == 0 or interest_rate == 0:
        return Decimal('0')
    
    monthly_rate = interest_rate / Decimal('12')
    num_payments = loan_term_years * 12
    
    # Standard amortization formula: P * (r * (1+r)^n) / ((1+r)^n - 1)
    one_plus_rate = Decimal('1') + monthly_rate
    rate_power = one_plus_rate ** num_payments
    
    monthly_payment = principal * (monthly_rate * rate_power) / (rate_power - Decimal('1'))
    return monthly_payment


def calculate_expense_annual_cost(expense: dict) -> Decimal | None:
    """Calculate the annual cost based on expense type"""
    expense_type = expense.get('expense_type')
    
    if expense_type == 'capex':
        # CapEx: purchase_price * depreciation_rate * count
        purchase = expense.get('purchase_price')
        depreciation = expense.get('depreciation_rate')
        count = expense.get('count', 1)
        
        if purchase and depreciation:
            return Decimal(str(purchase)) * Decimal(str(depreciation)) * Decimal(str(count))
    
    elif expense_type == 'pti':
        # PTI: direct annual_cost
        return expense.get('annual_cost')
    
    elif expense_type == 'maintenance' or expense_type == 'vacancy':
        # Maintenance and Vacancy: direct annual_cost (same as PTI)
        return expense.get('annual_cost')
    
    elif expense_type == 'pi':
        # P&I: Calculate full amortized payment (principal + interest)
        principal = expense.get('principal')
        interest_rate = expense.get('interest_rate')
        
        if principal and interest_rate:
            principal_decimal = Decimal(str(principal))
            interest_rate_decimal = Decimal(str(interest_rate))
            monthly_payment = calculate_monthly_amortized_payment(principal_decimal, interest_rate_decimal)
            annual_payment = monthly_payment * Decimal('12')
            return annual_payment
    
    return None


def calculate_revenue_annual_amount(revenue: dict) -> Decimal | None:
    """Calculate the annual revenue amount based on revenue type"""
    revenue_type = revenue.get('revenue_type')
    
    if revenue_type == 'principal_paydown':
        # Direct annual_amount
        return revenue.get('annual_amount')
    
    elif revenue_type == 'appreciation':
        # property_value * appreciation_rate
        property_value = revenue.get('property_value')
        appreciation_rate = revenue.get('appreciation_rate', Decimal('0.025'))  # Default 2.5%
        
        if property_value:
            return Decimal(str(property_value)) * Decimal(str(appreciation_rate))
    
    elif revenue_type == 'value_added':
        # Direct value_added_amount
        return revenue.get('value_added_amount')
    
    elif revenue_type == 'tax_savings':
        # Direct annual_amount (tax savings from depreciation)
        return revenue.get('annual_amount')
    
    return None

