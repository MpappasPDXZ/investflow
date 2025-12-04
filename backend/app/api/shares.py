"""API routes for user sharing (bidirectional property access)"""
import uuid
from typing import List
import pandas as pd
import pyarrow as pa
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.schemas.share import UserShareCreate, UserShareResponse
from app.core.iceberg import read_table, append_data, load_table, table_exists
from app.core.logging import get_logger
from app.services.auth_cache_service import auth_cache

router = APIRouter(prefix="/users/me/shares", tags=["shares"])
logger = get_logger(__name__)

NAMESPACE = ("investflow",)
TABLE_NAME = "user_shares"


@router.post("", response_model=UserShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    share_data: UserShareCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add an email to share properties with (bidirectional) with CDC cache update"""
    try:
        user_id = current_user["sub"]
        user_email = current_user["email"]
        
        # Prevent self-sharing
        if share_data.shared_email.lower() == user_email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot share with yourself"
            )
        
        # Check if share already exists using cache
        existing_shares = auth_cache.get_shares_by_user(user_id)
        if share_data.shared_email in existing_shares:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Already sharing with {share_data.shared_email}"
            )
        
        # Create share
        share_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        share_dict = {
            "id": share_id,
            "user_id": user_id,
            "shared_email": share_data.shared_email,
            "created_at": now,
            "updated_at": now
        }
        
        # Append to Iceberg table (source of truth)
        df = pd.DataFrame([share_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        # Update CDC cache (inline CDC)
        auth_cache.on_share_created(user_id, share_data.shared_email)
        
        logger.info(f"User {user_id} created share with {share_data.shared_email}")
        
        return UserShareResponse(**share_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating share: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[UserShareResponse])
async def get_my_shares(
    current_user: dict = Depends(get_current_user)
):
    """Get list of emails I'm sharing my properties with"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            return []
        
        df = read_table(NAMESPACE, TABLE_NAME)
        my_shares = df[df["user_id"] == user_id]
        
        result = []
        for _, row in my_shares.iterrows():
            result.append(UserShareResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                shared_email=row["shared_email"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting shares: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/shared-with-me", response_model=List[UserShareResponse])
async def get_shared_with_me(
    current_user: dict = Depends(get_current_user)
):
    """Get list of users who are sharing their properties with me"""
    try:
        user_email = current_user["email"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            return []
        
        df = read_table(NAMESPACE, TABLE_NAME)
        shared_with_me = df[df["shared_email"] == user_email]
        
        result = []
        for _, row in shared_with_me.iterrows():
            result.append(UserShareResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]),
                shared_email=row["shared_email"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting shared-with-me: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a share (stop sharing with an email) with CDC cache update"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share not found"
            )
        
        # Read table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Check if share exists and belongs to user
        mask = (df["id"] == share_id) & (df["user_id"] == user_id)
        
        if not mask.any():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Share not found"
            )
        
        # Get the shared_email before deletion (for cache update)
        deleted_share = df[mask].iloc[0]
        shared_email = deleted_share["shared_email"]
        
        # Remove the share from dataframe
        df_filtered = df[~mask]
        
        # Convert timestamps to microseconds
        for col in df_filtered.columns:
            if pd.api.types.is_datetime64_any_dtype(df_filtered[col]):
                df_filtered[col] = df_filtered[col].astype('datetime64[us]')
        
        # Overwrite table without the deleted share (source of truth)
        table = load_table(NAMESPACE, TABLE_NAME)
        table_schema = table.schema().as_arrow()
        
        # Reorder columns to match schema
        schema_column_order = [field.name for field in table_schema]
        df_filtered = df_filtered[[col for col in schema_column_order if col in df_filtered.columns]]
        
        # Convert to PyArrow and overwrite
        arrow_table = pa.Table.from_pandas(df_filtered, preserve_index=False)
        arrow_table = arrow_table.cast(table_schema)
        table.overwrite(arrow_table)
        
        # Update CDC cache (inline CDC)
        auth_cache.on_share_deleted(user_id, shared_email)
        
        logger.info(f"User {user_id} deleted share {share_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting share: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

