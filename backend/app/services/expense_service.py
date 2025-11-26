"""Service layer for expense operations using PyIceberg"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
import pandas as pd
import uuid

from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.logging import get_logger
from app.schemas.expense import ExpenseCreate, ExpenseUpdate

logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)
TABLE_NAME = "expenses"


def _expense_to_dict(expense_data: ExpenseCreate | ExpenseUpdate, user_id: UUID, expense_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Convert expense schema to dictionary for Iceberg table"""
    now = pd.Timestamp.now()
    
    data = {
        "id": str(expense_id) if expense_id else str(uuid.uuid4()),
        "created_by_user_id": str(user_id),
        "created_at": now,
        "updated_at": now,
    }
    
    # Add fields from schema
    expense_dict = expense_data.model_dump(exclude_none=True)
    for key, value in expense_dict.items():
        if value is not None:
            # Convert UUIDs to strings
            if isinstance(value, UUID):
                data[key] = str(value)
            # Convert Decimal to float for pandas
            elif isinstance(value, Decimal):
                data[key] = float(value)
            # Convert date to pandas Timestamp
            elif isinstance(value, date):
                data[key] = pd.Timestamp(value)
            # Convert enum to string
            elif hasattr(value, 'value'):
                data[key] = value.value
            else:
                data[key] = value
    
    return data


def _df_to_expense_dict(df_row: pd.Series) -> Dict[str, Any]:
    """Convert DataFrame row to expense dictionary"""
    result = {
        "id": UUID(df_row["id"]),
        "property_id": UUID(df_row["property_id"]),
        "description": str(df_row["description"]),
        "date": df_row["date"].date() if pd.notna(df_row["date"]) else None,
        "amount": Decimal(str(df_row["amount"])),
        "expense_type": str(df_row["expense_type"]),
        "is_planned": bool(df_row["is_planned"]) if pd.notna(df_row["is_planned"]) else False,
        "created_at": df_row["created_at"].to_pydatetime() if pd.notna(df_row["created_at"]) else None,
        "updated_at": df_row["updated_at"].to_pydatetime() if pd.notna(df_row["updated_at"]) else None,
    }
    
    # Add optional fields
    for field in ["vendor", "document_storage_id", "notes", "created_by_user_id"]:
        if field in df_row and pd.notna(df_row[field]):
            value = df_row[field]
            if field == "document_storage_id" or field == "created_by_user_id":
                result[field] = UUID(value) if value else None
            else:
                result[field] = value
        else:
            result[field] = None
    
    return result


def create_expense(
    user_id: UUID,
    expense_data: ExpenseCreate
) -> Dict[str, Any]:
    """Create a new expense in Iceberg table"""
    pyiceberg = get_pyiceberg_service()
    
    # Convert to dict
    expense_dict = _expense_to_dict(expense_data, user_id)
    
    # Create DataFrame with single row
    df = pd.DataFrame([expense_dict])
    
    # Append to table
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, df)
    
    logger.info(f"Created expense {expense_dict['id']} for user {user_id}")
    
    # Read back the created expense
    return get_expense(UUID(expense_dict['id']), user_id)


def get_expense(
    expense_id: UUID,
    user_id: UUID
) -> Optional[Dict[str, Any]]:
    """Get an expense by ID (ensuring it belongs to the user)"""
    pyiceberg = get_pyiceberg_service()
    
    # Read table and filter
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    
    # Filter by id and user_id
    filtered = df[(df["id"] == str(expense_id)) & (df["created_by_user_id"] == str(user_id))]
    
    if len(filtered) == 0:
        return None
    
    return _df_to_expense_dict(filtered.iloc[0])


def list_expenses(
    user_id: UUID,
    property_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List expenses for a user with optional property filter and pagination"""
    pyiceberg = get_pyiceberg_service()
    
    # Read table and filter
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    
    # Filter by user_id
    filtered = df[df["created_by_user_id"] == str(user_id)]
    
    # Optional property filter
    if property_id:
        filtered = filtered[filtered["property_id"] == str(property_id)]
    
    total = len(filtered)
    
    # Apply pagination
    df_paginated = filtered.iloc[skip:skip + limit]
    
    # Convert to list of dicts
    expenses = [_df_to_expense_dict(row) for _, row in df_paginated.iterrows()]
    
    return expenses, total


def update_expense(
    expense_id: UUID,
    user_id: UUID,
    expense_data: ExpenseUpdate
) -> Optional[Dict[str, Any]]:
    """Update an expense in Iceberg table"""
    # Get existing expense
    existing = get_expense(expense_id, user_id)
    if not existing:
        return None
    
    pyiceberg = get_pyiceberg_service()
    
    # Read all expenses for this user
    all_df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    all_df = all_df[all_df["created_by_user_id"] == str(user_id)].copy()
    
    # Update the specific row
    mask = all_df["id"] == str(expense_id)
    if not mask.any():
        return None
    
    update_dict = expense_data.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        if key in all_df.columns:
            if isinstance(value, UUID):
                all_df.loc[mask, key] = str(value)
            elif isinstance(value, Decimal):
                all_df.loc[mask, key] = float(value)
            elif isinstance(value, date):
                all_df.loc[mask, key] = pd.Timestamp(value)
            elif hasattr(value, 'value'):
                all_df.loc[mask, key] = value.value
            else:
                all_df.loc[mask, key] = value
    
    # Update timestamp
    all_df.loc[mask, "updated_at"] = pd.Timestamp.now()
    
    # Get table schema
    table = pyiceberg.load_table(NAMESPACE, TABLE_NAME)
    schema = table.schema().as_arrow()
    
    # Truncate and reload
    pyiceberg.truncate_table(NAMESPACE, TABLE_NAME, schema)
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, all_df)
    
    logger.info(f"Updated expense {expense_id} for user {user_id}")
    return get_expense(expense_id, user_id)


def delete_expense(
    expense_id: UUID,
    user_id: UUID
) -> bool:
    """Delete an expense (hard delete - removes from table)"""
    pyiceberg = get_pyiceberg_service()
    
    # Read all expenses for this user
    all_df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    all_df = all_df[all_df["created_by_user_id"] == str(user_id)].copy()
    
    # Remove the expense
    original_count = len(all_df)
    all_df = all_df[all_df["id"] != str(expense_id)]
    
    if len(all_df) == original_count:
        return False  # Expense not found
    
    # Get table schema
    table = pyiceberg.load_table(NAMESPACE, TABLE_NAME)
    schema = table.schema().as_arrow()
    
    # Truncate and reload
    pyiceberg.truncate_table(NAMESPACE, TABLE_NAME, schema)
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, all_df)
    
    logger.info(f"Deleted expense {expense_id} for user {user_id}")
    return True

