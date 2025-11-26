"""Service layer for property operations using PyIceberg"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal
import pandas as pd
import uuid

from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.logging import get_logger
from app.schemas.property import PropertyCreate, PropertyUpdate

logger = get_logger(__name__)

# Namespace for all tables
NAMESPACE = ("investflow",)
TABLE_NAME = "properties"


def _property_to_dict(property_data: PropertyCreate | PropertyUpdate, user_id: UUID, property_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Convert property schema to dictionary for Iceberg table"""
    now = pd.Timestamp.now()
    
    data = {
        "id": str(property_id) if property_id else str(uuid.uuid4()),
        "user_id": str(user_id),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    
    # Add fields from schema
    property_dict = property_data.model_dump(exclude_none=True)
    for key, value in property_dict.items():
        if value is not None:
            # Convert Decimal to float for pandas
            if isinstance(value, Decimal):
                data[key] = float(value)
            else:
                data[key] = value
    
    return data


def _df_to_property_dict(df_row: pd.Series) -> Dict[str, Any]:
    """Convert DataFrame row to property dictionary"""
    result = {
        "id": UUID(df_row["id"]),
        "user_id": UUID(df_row["user_id"]),
        "is_active": bool(df_row["is_active"]),
        "created_at": df_row["created_at"].to_pydatetime() if pd.notna(df_row["created_at"]) else None,
        "updated_at": df_row["updated_at"].to_pydatetime() if pd.notna(df_row["updated_at"]) else None,
    }
    
    # Add optional fields
    for field in ["display_name", "purchase_price", "monthly_rent_to_income_ratio", 
                  "address_line1", "address_line2", "city", "state", "zip_code",
                  "property_type", "bedrooms", "bathrooms", "square_feet", 
                  "year_built", "current_monthly_rent", "notes"]:
        if field in df_row and pd.notna(df_row[field]):
            value = df_row[field]
            # Convert Decimal fields
            if field in ["purchase_price", "monthly_rent_to_income_ratio", "bathrooms", "current_monthly_rent"]:
                result[field] = Decimal(str(value))
            else:
                result[field] = value
        else:
            result[field] = None
    
    return result


def create_property(
    user_id: UUID,
    property_data: PropertyCreate
) -> Dict[str, Any]:
    """Create a new property in Iceberg table"""
    pyiceberg = get_pyiceberg_service()
    
    # Convert to dict
    property_dict = _property_to_dict(property_data, user_id)
    
    # Create DataFrame with single row
    df = pd.DataFrame([property_dict])
    
    # Append to table
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, df)
    
    logger.info(f"Created property {property_dict['id']} for user {user_id}")
    
    # Read back the created property
    return get_property(UUID(property_dict['id']), user_id)


def get_property(
    property_id: UUID,
    user_id: UUID
) -> Optional[Dict[str, Any]]:
    """Get a property by ID (ensuring it belongs to the user)"""
    pyiceberg = get_pyiceberg_service()
    
    # Read table and filter in pandas
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    
    # Filter by id and user_id
    filtered = df[(df["id"] == str(property_id)) & (df["user_id"] == str(user_id))]
    
    if len(filtered) == 0:
        return None
    
    return _df_to_property_dict(filtered.iloc[0])


def list_properties(
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Dict[str, Any]], int]:
    """List properties for a user with pagination"""
    pyiceberg = get_pyiceberg_service()
    
    # Read table and filter in pandas
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    
    # Filter by user_id and is_active
    filtered = df[(df["user_id"] == str(user_id)) & (df["is_active"] == True)]
    
    total = len(filtered)
    
    # Apply pagination
    df_paginated = filtered.iloc[skip:skip + limit]
    
    # Convert to list of dicts
    properties = [_df_to_property_dict(row) for _, row in df_paginated.iterrows()]
    
    return properties, total


def update_property(
    property_id: UUID,
    user_id: UUID,
    property_data: PropertyUpdate
) -> Optional[Dict[str, Any]]:
    """Update a property in Iceberg table
    
    Note: Iceberg doesn't support direct row updates. This implementation:
    1. Reads all properties for the user
    2. Updates the target row in memory
    3. Truncates and reloads all user properties
    
    For better performance, consider using Iceberg's merge capabilities
    or partitioning strategies.
    """
    # Get existing property to verify it exists
    existing = get_property(property_id, user_id)
    if not existing:
        return None
    
    pyiceberg = get_pyiceberg_service()
    
    # Read all properties for this user
    all_df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    all_df = all_df[all_df["user_id"] == str(user_id)].copy()
    
    # Update the specific row
    mask = all_df["id"] == str(property_id)
    if not mask.any():
        return None
    
    update_dict = property_data.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        if key in all_df.columns:
            if isinstance(value, Decimal):
                all_df.loc[mask, key] = float(value)
            else:
                all_df.loc[mask, key] = value
    
    # Update timestamp
    all_df.loc[mask, "updated_at"] = pd.Timestamp.now()
    
    # Get table schema for truncate
    table = pyiceberg.load_table(NAMESPACE, TABLE_NAME)
    schema = table.schema().as_arrow()
    
    # Truncate and reload all user properties
    # Note: This is inefficient but necessary for Iceberg updates
    # In production, consider using Iceberg's merge capabilities
    pyiceberg.truncate_table(NAMESPACE, TABLE_NAME, schema)
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, all_df)
    
    logger.info(f"Updated property {property_id} for user {user_id}")
    return get_property(property_id, user_id)


def delete_property(
    property_id: UUID,
    user_id: UUID
) -> bool:
    """Soft delete a property (set is_active to False)"""
    # Use update to set is_active to False
    from app.schemas.property import PropertyUpdate
    update_data = PropertyUpdate(is_active=False)
    
    result = update_property(property_id, user_id, update_data)
    
    if result:
        logger.info(f"Soft deleted property {property_id} for user {user_id}")
        return True
    
    return False
