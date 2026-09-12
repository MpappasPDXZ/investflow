"""API routes for user profile management"""
import pandas as pd
import pyarrow as pa
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_current_user
from app.schemas.user import UserResponse, UserUpdate
from app.core.iceberg import read_table, table_exists, load_table, uses_postgres
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache

NAMESPACE = ("investflow",)
TABLE_NAME = "users"

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user)
):
    """Get the current user's profile using CDC cache for fast lookup"""
    try:
        user_id = current_user["sub"]  # Already a string
        
        # Use CDC cache for fast O(1) lookup
        user = auth_cache.get_user_by_id(user_id)
        
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
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
    """Update the current user's profile in Iceberg with CDC cache update"""
    try:
        user_id = current_user["sub"]  # Already a string
        logger.info(f"Updating user profile for user_id: {user_id}")
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error("Users table does not exist")
            raise HTTPException(status_code=404, detail="User table not found")
        
        # Read table, update, and write back (Iceberg update pattern)
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"Read {len(df)} users from table")
        
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

        if uses_postgres(TABLE_NAME):
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].astype("datetime64[us]")
            arrow_table = pa.Table.from_pandas(df, preserve_index=False)
            logger.info("Overwriting users table with updated data (postgres)")
            table.overwrite(arrow_table)
            logger.info("Table overwritten successfully")
        else:
            table_schema = table.schema().as_arrow()

            # Reorder DataFrame columns to match table schema
            schema_column_order = [field.name for field in table_schema]
            df = df[[col for col in schema_column_order if col in df.columns]]

            # Convert to PyArrow and cast to table schema
            arrow_table = pa.Table.from_pandas(df, preserve_index=False)
            arrow_table = arrow_table.cast(table_schema)

            # Overwrite the table (source of truth)
            logger.info("Overwriting table with updated data")
            table.overwrite(arrow_table)
            logger.info("Table overwritten successfully")
        
        # Get the updated user row
        updated_user = df[mask].iloc[0]
        
        # Build user dict for cache update and response
        user_dict_full = updated_user.to_dict()
        
        # Update CDC cache (inline CDC)
        auth_cache.on_user_updated(user_dict_full)
        
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
