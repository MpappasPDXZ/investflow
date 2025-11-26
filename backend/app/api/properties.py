"""API routes for property management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from uuid import UUID

from app.core.dependencies import get_current_user
from app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyResponse, PropertyListResponse
)
from app.services.property_service import (
    create_property,
    get_property,
    list_properties,
    update_property,
    delete_property
)
from app.core.logging import get_logger

router = APIRouter(prefix="/properties", tags=["properties"])
logger = get_logger(__name__)


@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property_endpoint(
    property_data: PropertyCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new property"""
    try:
        user_id = UUID(current_user["sub"])
        property_dict = create_property(
            user_id=user_id,
            property_data=property_data
        )
        return PropertyResponse(**property_dict)
    except Exception as e:
        logger.error(f"Error creating property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=PropertyListResponse)
async def list_properties_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List all properties for the current user"""
    try:
        user_id = UUID(current_user["sub"])
        properties, total = list_properties(
            user_id=user_id,
            skip=skip,
            limit=limit
        )
        
        # Convert to PropertyResponse objects
        items = [PropertyResponse(**prop) for prop in properties]
        
        return PropertyListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing properties: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property_endpoint(
    property_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a property by ID"""
    try:
        user_id = UUID(current_user["sub"])
        property_dict = get_property(
            property_id=property_id,
            user_id=user_id
        )
        
        if not property_dict:
            raise HTTPException(status_code=404, detail="Property not found")
        
        return PropertyResponse(**property_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property_endpoint(
    property_id: UUID,
    property_data: PropertyUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a property"""
    try:
        user_id = UUID(current_user["sub"])
        property_dict = update_property(
            property_id=property_id,
            user_id=user_id,
            property_data=property_data
        )
        
        if not property_dict:
            raise HTTPException(status_code=404, detail="Property not found")
        
        return PropertyResponse(**property_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{property_id}", status_code=204)
async def delete_property_endpoint(
    property_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete a property (soft delete)"""
    try:
        user_id = UUID(current_user["sub"])
        success = delete_property(
            property_id=property_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Property not found")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting property: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
