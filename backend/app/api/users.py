"""API routes for user profile management"""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.tables import User
from app.schemas.user import UserResponse, UserUpdate
from app.core.logging import get_logger

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the current user's profile"""
    try:
        user_id = UUID(current_user["sub"])
        
        # Get user from database
        db_user = db.query(User).filter(User.id == user_id).first()
        
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Convert to response (exclude password_hash)
        user_dict = {
            "id": str(db_user.id),
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "email": db_user.email,
            "tax_rate": float(db_user.tax_rate) if db_user.tax_rate else None,
            "created_at": db_user.created_at,
            "updated_at": db_user.updated_at,
            "is_active": db_user.is_active,
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update the current user's profile"""
    try:
        user_id = UUID(current_user["sub"])
        
        # Get user from database
        db_user = db.query(User).filter(User.id == user_id).first()
        
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields
        update_dict = user_data.model_dump(exclude_none=True)
        for key, value in update_dict.items():
            setattr(db_user, key, value)
        
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"Updated user profile {user_id}")
        
        # Convert to response (exclude password_hash)
        user_dict = {
            "id": str(db_user.id),
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "email": db_user.email,
            "tax_rate": float(db_user.tax_rate) if db_user.tax_rate else None,
            "created_at": db_user.created_at,
            "updated_at": db_user.updated_at,
            "is_active": db_user.is_active,
        }
        
        return UserResponse(**user_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
