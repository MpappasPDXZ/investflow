"""API routes for user profile management"""
from typing import Optional, Dict, Any, List
import uuid
import pandas as pd
import pyarrow as pa
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pyiceberg.expressions import EqualTo

from app.core.dependencies import get_current_user
from app.schemas.user import UserResponse, UserUpdate, UserCreate
from app.core.security import get_password_hash
from app.core.exceptions import ConflictError
from app.core.iceberg import read_table, read_table_filtered, append_data, table_exists, load_table
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
TABLE_NAME = "users"
SHARES_TABLE = "user_shares"

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
):
    """Create a new user in Iceberg"""
    logger.info(f"Creating user with email: {user_data.email}")
    
    try:
        # Check if user already exists using filtered lookup (fast)
        if table_exists(NAMESPACE, TABLE_NAME):
            existing = read_table_filtered(
                NAMESPACE, 
                TABLE_NAME,
                row_filter=EqualTo("email", user_data.email),
                selected_columns=["id"]  # Only need to know if row exists
            )
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
        
        # Use filtered lookup for fast retrieval
        try:
            user_row = read_table_filtered(
                NAMESPACE, 
                TABLE_NAME,
                row_filter=EqualTo("id", user_id)
            )
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")
        
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
            "mortgage_interest_rate": float(user["mortgage_interest_rate"]) if pd.notna(user.get("mortgage_interest_rate")) else None,
            "loc_interest_rate": float(user["loc_interest_rate"]) if pd.notna(user.get("loc_interest_rate")) else None,
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
        logger.info(f"Updating user profile for user_id: {user_id}")
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("Users table does not exist")
            raise HTTPException(status_code=404, detail="User table not found")
        
        # Read table, update, and write back (Iceberg update pattern)
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"Read {len(df)} users from table")
        logger.info(f"User IDs in table: {df['id'].tolist()}")
        logger.info(f"Looking for user_id: {user_id} (type: {type(user_id)})")
        
        mask = df["id"] == user_id
        
        if not mask.any():
            logger.error(f"User {user_id} not found in table")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Found user {user_id}, updating fields: {user_data.model_dump(exclude_none=True)}")
        
        # Update fields
        update_dict = user_data.model_dump(exclude_none=True)
        for key, value in update_dict.items():
            if key in df.columns:
                df.loc[mask, key] = value
                logger.info(f"Updated {key} to {value}")
            else:
                logger.warning(f"Column {key} not in dataframe, skipping")
        
        # Update timestamp
        df.loc[mask, "updated_at"] = pd.Timestamp.now()
        
        # Convert timestamps to microseconds
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype('datetime64[us]')
        
        # Load table and overwrite (Iceberg update pattern)
        table = load_table(NAMESPACE, TABLE_NAME)
        table_schema = table.schema().as_arrow()
        
        logger.info(f"Table schema columns: {[field.name for field in table_schema]}")
        logger.info(f"DataFrame columns: {df.columns.tolist()}")
        
        # Reorder DataFrame columns to match table schema
        schema_column_order = [field.name for field in table_schema]
        df = df[[col for col in schema_column_order if col in df.columns]]
        
        # Convert to PyArrow and cast to table schema
        arrow_table = pa.Table.from_pandas(df, preserve_index=False)
        arrow_table = arrow_table.cast(table_schema)
        
        # Overwrite the table
        logger.info("Overwriting table with updated data")
        table.overwrite(arrow_table)
        logger.info("Table overwritten successfully")
        
        # Re-read the table to get the updated user
        df_updated = read_table(NAMESPACE, TABLE_NAME)
        mask_updated = df_updated["id"] == user_id
        updated_user = df_updated[mask_updated].iloc[0]
        
        # Convert to response (exclude password_hash)
        user_dict = {
            "id": str(updated_user["id"]),
            "first_name": updated_user["first_name"],
            "last_name": updated_user["last_name"],
            "email": updated_user["email"],
            "tax_rate": float(updated_user["tax_rate"]) if pd.notna(updated_user.get("tax_rate")) else None,
            "mortgage_interest_rate": float(updated_user["mortgage_interest_rate"]) if pd.notna(updated_user.get("mortgage_interest_rate")) else None,
            "loc_interest_rate": float(updated_user["loc_interest_rate"]) if pd.notna(updated_user.get("loc_interest_rate")) else None,
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


@router.get("/shared", response_model=List[UserResponse])
async def get_shared_users(
    current_user: dict = Depends(get_current_user)
):
    """Get list of users who have bidirectional sharing with the current user (from Iceberg)"""
    try:
        user_id = current_user["sub"]
        user_email = current_user["email"]
        
        # Use the sharing utility to get shared user IDs
        from app.api.sharing_utils import get_shared_user_ids
        shared_user_ids = get_shared_user_ids(user_id, user_email)
        
        if len(shared_user_ids) == 0:
            return []
        
        # Read users table and filter by shared user IDs
        if not table_exists(NAMESPACE, TABLE_NAME):
            return []
        
        df = read_table(NAMESPACE, TABLE_NAME)
        shared_users = df[df["id"].isin(shared_user_ids)]
        
        # Convert to UserResponse objects (exclude password_hash)
        result = []
        for _, user in shared_users.iterrows():
            user_dict = {
                "id": str(user["id"]),
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
                "tax_rate": float(user["tax_rate"]) if pd.notna(user.get("tax_rate")) else None,
                "mortgage_interest_rate": float(user["mortgage_interest_rate"]) if pd.notna(user.get("mortgage_interest_rate")) else None,
                "loc_interest_rate": float(user["loc_interest_rate"]) if pd.notna(user.get("loc_interest_rate")) else None,
                "created_at": user["created_at"] if pd.notna(user.get("created_at")) else datetime.now(),
                "updated_at": user["updated_at"] if pd.notna(user.get("updated_at")) else datetime.now(),
                "is_active": bool(user["is_active"]) if pd.notna(user.get("is_active")) else True,
            }
            result.append(UserResponse(**user_dict))
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting shared users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
