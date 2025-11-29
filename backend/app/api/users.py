"""API routes for user profile management"""
from typing import Optional, Dict, Any
import uuid
import pandas as pd
import pyarrow as pa
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.schemas.user import UserResponse, UserUpdate, UserCreate
from app.core.security import get_password_hash
from app.core.exceptions import ConflictError
from app.core.iceberg import read_table, append_data, table_exists, load_table
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
TABLE_NAME = "users"

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
):
    """Create a new user in Iceberg"""
    logger.info(f"Creating user with email: {user_data.email}")
    
    try:
        # Check if user already exists
        if table_exists(NAMESPACE, TABLE_NAME):
            df = read_table(NAMESPACE, TABLE_NAME)
            existing = df[df["email"] == user_data.email]
            if len(existing) > 0:
                logger.warning(f"Attempted to create user with existing email: {user_data.email}")
                raise ConflictError("User with this email already exists")
        
        # Create user with string UUID
        user_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        logger.info(f"Creating user with ID: {user_id}, email: {user_data.email}")
        
        # Create user record
        user_dict = {
            "id": user_id,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "email": user_data.email,
            "password_hash": get_password_hash(user_data.password),
            "tax_rate": float(user_data.tax_rate) if user_data.tax_rate else None,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }
        
        # Append to Iceberg table
        df = pd.DataFrame([user_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Successfully created user {user_id} with email {user_data.email}")
        
        # Return response (exclude password_hash)
        response_dict = {k: v for k, v in user_dict.items() if k != "password_hash"}
        return UserResponse(**response_dict)
        
    except ConflictError:
        raise
    except Exception as e:
        logger.error(f"Error creating user {user_data.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user)
):
    """Get the current user's profile from Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user from Iceberg
        df = read_table(NAMESPACE, TABLE_NAME)
        user_row = df[df["id"] == user_id]
        
        if len(user_row) == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_row.iloc[0]
        
        # Convert to response (exclude password_hash)
        user_dict = {
            "id": str(user["id"]),
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "tax_rate": float(user["tax_rate"]) if pd.notna(user.get("tax_rate")) else None,
            "created_at": user["created_at"] if pd.notna(user.get("created_at")) else datetime.now(),
            "updated_at": user["updated_at"] if pd.notna(user.get("updated_at")) else datetime.now(),
            "is_active": bool(user["is_active"]) if pd.notna(user.get("is_active")) else True,
        }
        
        return UserResponse(**user_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the current user's profile in Iceberg"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="User not found")
        
        # Read table, update, and write back (Iceberg update pattern)
        df = read_table(NAMESPACE, TABLE_NAME)
        mask = df["id"] == user_id
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields
        update_dict = user_data.model_dump(exclude_none=True)
        for key, value in update_dict.items():
            if key in df.columns:
                df.loc[mask, key] = value
        
        # Update timestamp
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Truncate and reload (Iceberg update pattern)
        table = load_table(NAMESPACE, TABLE_NAME)
        table.truncate()
        arrow_table = pa.Table.from_pandas(df)
        table.append(arrow_table)
        
        # Get updated user
        updated_user = df[mask].iloc[0]
        
        # Convert to response (exclude password_hash)
        user_dict = {
            "id": str(updated_user["id"]),
            "first_name": updated_user["first_name"],
            "last_name": updated_user["last_name"],
            "email": updated_user["email"],
            "tax_rate": float(updated_user["tax_rate"]) if pd.notna(updated_user.get("tax_rate")) else None,
            "created_at": updated_user["created_at"] if pd.notna(updated_user.get("created_at")) else datetime.now(),
            "updated_at": updated_user["updated_at"] if pd.notna(updated_user.get("updated_at")) else datetime.now(),
            "is_active": bool(updated_user["is_active"]) if pd.notna(updated_user.get("is_active")) else True,
        }
        
        return UserResponse(**user_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
