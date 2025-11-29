"""
API endpoints for scheduled expenses and revenue
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.dependencies import get_current_user_id
from app.schemas.scheduled import (
    ScheduledExpenseCreate, ScheduledExpenseUpdate, ScheduledExpenseResponse, ScheduledExpenseListResponse,
    ScheduledRevenueCreate, ScheduledRevenueUpdate, ScheduledRevenueResponse, ScheduledRevenueListResponse
)
from app.core.iceberg import get_catalog, read_table, append_data, table_exists, load_table
from app.core.logging import get_logger
from decimal import Decimal
from datetime import datetime, timezone
import uuid
import pandas as pd
import pyarrow as pa

logger = get_logger(__name__)
router = APIRouter()

NAMESPACE = ("investflow",)
EXPENSES_TABLE = "scheduled_expenses"
REVENUE_TABLE = "scheduled_revenue"


# ========== SCHEDULED EXPENSES ENDPOINTS ==========

@router.post("/scheduled-expenses", response_model=ScheduledExpenseResponse)
async def create_scheduled_expense(
    expense_data: ScheduledExpenseCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Create a new scheduled expense"""
    try:
        logger.info(f"Creating scheduled expense for property {expense_data.property_id}")
        
        # Verify property belongs to user
        properties_df = read_table(NAMESPACE, "properties")
        if properties_df is None or properties_df.empty:
            raise HTTPException(status_code=404, detail="Properties table is empty")
        
        property_match = properties_df[
            (properties_df['id'] == expense_data.property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Create expense record
        expense_id = str(uuid.uuid4())
        now = pd.Timestamp.now(tz=timezone.utc).floor('us')
        
        expense_dict = {
            "id": expense_id,
            "property_id": expense_data.property_id,
            "expense_type": expense_data.expense_type,
            "item_name": expense_data.item_name,
            "purchase_price": expense_data.purchase_price,
            "depreciation_rate": expense_data.depreciation_rate,
            "count": expense_data.count,
            "annual_cost": expense_data.annual_cost,
            "principal": expense_data.principal,
            "interest_rate": expense_data.interest_rate,
            "notes": expense_data.notes,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Convert to DataFrame and append
        df = pd.DataFrame([expense_dict])
        append_data(NAMESPACE, EXPENSES_TABLE, df)
        
        logger.info(f"✅ Scheduled expense created: {expense_id}")
        
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
    user_id: str = Depends(get_current_user_id)
):
    """List all scheduled expenses for a property"""
    try:
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
        
        # Read expenses
        expenses_df = read_table(NAMESPACE, EXPENSES_TABLE)
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
    user_id: str = Depends(get_current_user_id)
):
    """Get a specific scheduled expense"""
    try:
        expenses_df = read_table(NAMESPACE, EXPENSES_TABLE)
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
    user_id: str = Depends(get_current_user_id)
):
    """Update a scheduled expense"""
    try:
        logger.info(f"Updating scheduled expense {expense_id}")
        
        # Read all expenses
        table = load_table(NAMESPACE, EXPENSES_TABLE)
        expenses_df = read_table(NAMESPACE, EXPENSES_TABLE)
        
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
        
        # Use timezone-naive UTC timestamp
        expenses_df.loc[expense_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert timestamps to microseconds (ensure timezone-naive)
        for col in ['created_at', 'updated_at']:
            if col in expenses_df.columns:
                expenses_df[col] = pd.to_datetime(expenses_df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(expenses_df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Scheduled expense updated: {expense_id}")
        
        # Return updated expense
        updated_row = expenses_df.loc[expense_idx[0]].to_dict()
        # Replace NaN with None for Pydantic validation
        updated_row = {k: (None if pd.isna(v) else v) for k, v in updated_row.items()}
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
    user_id: str = Depends(get_current_user_id)
):
    """Delete (soft delete) a scheduled expense"""
    try:
        logger.info(f"Deleting scheduled expense {expense_id}")
        
        # Read all expenses
        table = load_table(NAMESPACE, EXPENSES_TABLE)
        expenses_df = read_table(NAMESPACE, EXPENSES_TABLE)
        
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
        # Use timezone-naive UTC timestamp
        expenses_df.loc[expense_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert timestamps to microseconds (ensure timezone-naive)
        for col in ['created_at', 'updated_at']:
            if col in expenses_df.columns:
                expenses_df[col] = pd.to_datetime(expenses_df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(expenses_df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
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
    user_id: str = Depends(get_current_user_id)
):
    """Create a new scheduled revenue"""
    try:
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
        
        # Create revenue record
        revenue_id = str(uuid.uuid4())
        now = pd.Timestamp.now(tz=timezone.utc).floor('us')
        
        revenue_dict = {
            "id": revenue_id,
            "property_id": revenue_data.property_id,
            "revenue_type": revenue_data.revenue_type,
            "item_name": revenue_data.item_name,
            "annual_amount": revenue_data.annual_amount,
            "appreciation_rate": revenue_data.appreciation_rate,
            "property_value": revenue_data.property_value,
            "value_added_amount": revenue_data.value_added_amount,
            "notes": revenue_data.notes,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Convert to DataFrame and append
        df = pd.DataFrame([revenue_dict])
        append_data(NAMESPACE, REVENUE_TABLE, df)
        
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
    user_id: str = Depends(get_current_user_id)
):
    """List all scheduled revenue for a property"""
    try:
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
    user_id: str = Depends(get_current_user_id)
):
    """Update a scheduled revenue"""
    try:
        logger.info(f"Updating scheduled revenue {revenue_id}")
        
        # Read all revenue
        table = load_table(NAMESPACE, REVENUE_TABLE)
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
        
        # Use timezone-naive UTC timestamp
        revenue_df.loc[revenue_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert timestamps to microseconds (ensure timezone-naive)
        for col in ['created_at', 'updated_at']:
            if col in revenue_df.columns:
                revenue_df[col] = pd.to_datetime(revenue_df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(revenue_df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
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
    user_id: str = Depends(get_current_user_id)
):
    """Delete (soft delete) a scheduled revenue"""
    try:
        logger.info(f"Deleting scheduled revenue {revenue_id}")
        
        # Read all revenue
        table = load_table(NAMESPACE, REVENUE_TABLE)
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
        # Use timezone-naive UTC timestamp
        revenue_df.loc[revenue_idx[0], 'updated_at'] = pd.Timestamp.now(tz=timezone.utc).tz_localize(None)
        
        # Convert timestamps to microseconds (ensure timezone-naive)
        for col in ['created_at', 'updated_at']:
            if col in revenue_df.columns:
                revenue_df[col] = pd.to_datetime(revenue_df[col], utc=True).dt.tz_localize(None).dt.floor('us')
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(revenue_df)
        arrow_table = arrow_table.cast(table.schema().as_arrow())
        table.overwrite(arrow_table)
        
        logger.info(f"✅ Scheduled revenue deleted: {revenue_id}")
        
        return {"message": "Scheduled revenue deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting scheduled revenue: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== HELPER FUNCTIONS ==========

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
    
    elif expense_type == 'pi':
        # P&I: principal * interest_rate
        principal = expense.get('principal')
        interest_rate = expense.get('interest_rate')
        
        if principal and interest_rate:
            return Decimal(str(principal)) * Decimal(str(interest_rate))
    
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
    
    return None

