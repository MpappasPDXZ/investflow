"""
API endpoints for scheduled financials template management
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from app.core.dependencies import get_current_user
from app.services.scheduled_financials_template_service import scheduled_financials_template
from app.core.iceberg import read_table, append_data, table_exists
from app.core.logging import get_logger
from typing import Dict, Any, List
import uuid
import pandas as pd
from datetime import timezone
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter()

NAMESPACE = ("investflow",)


class ApplyTemplateRequest(BaseModel):
    expenses: List[Dict[str, Any]]
    revenue: List[Dict[str, Any]]


@router.get("/scheduled-financials/preview-template/{property_id}")
async def preview_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Preview the template for a property with scaling applied (without saving).
    Returns the scaled expenses and revenue items for user selection.
    """
    try:
        user_id = current_user["sub"]
        
        # Get target property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = property_match.iloc[0].to_dict()
        
        # Get scaled template
        from uuid import UUID
        result = scheduled_financials_template.apply_template_to_property(
            UUID(property_id),
            property_data
        )
        
        return {
            "expenses": result["expenses"],
            "revenue": result["revenue"],
            "scaling_factors": result["scaling_factors"]
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-financials/apply-template/{property_id}")
async def apply_template(
    property_id: str,
    request: ApplyTemplateRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Apply selected template items to a property.
    Accepts a list of expenses and revenue items to apply.
    """
    try:
        user_id = current_user["sub"]
        
        # Get target property data (verify ownership)
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Insert selected expenses
        expenses_created = 0
        if request.expenses:
            for expense in request.expenses:
                expense["id"] = str(uuid.uuid4())
                expense["is_active"] = True
                expense["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                expense["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
            
            df = pd.DataFrame(request.expenses)
            append_data(NAMESPACE, "scheduled_expenses", df)
            expenses_created = len(request.expenses)
        
        # Insert selected revenue
        revenue_created = 0
        if request.revenue:
            for rev in request.revenue:
                rev["id"] = str(uuid.uuid4())
                rev["is_active"] = True
                rev["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                rev["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
            
            df = pd.DataFrame(request.revenue)
            append_data(NAMESPACE, "scheduled_revenue", df)
            revenue_created = len(request.revenue)
        
        return {
            "message": "Template applied successfully",
            "property_id": property_id,
            "expenses_created": expenses_created,
            "revenue_created": revenue_created
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
async def save_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Save a property's scheduled financials as the template.
    This should be called on the reference property (316 S 50th Ave).
    """
    try:
        user_id = current_user["sub"]
        
        # Get property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = property_match.iloc[0].to_dict()
        
        # Save as template
        from uuid import UUID
        success = scheduled_financials_template.save_template_from_property(
            UUID(property_id),
            property_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save template")
        
        return {
            "message": "Template saved successfully",
            "property_id": property_id,
            "property_address": property_data.get("address_line1")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-financials/apply-template/{property_id}")
async def apply_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Apply the template to a property with intelligent scaling.
    Scales based on purchase price, bedrooms, bathrooms, and square footage.
    """
    try:
        user_id = current_user["sub"]
        
        # Get target property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = property_match.iloc[0].to_dict()
        
        # Apply template with scaling
        from uuid import UUID
        result = scheduled_financials_template.apply_template_to_property(
            UUID(property_id),
            property_data
        )
        
        # Insert scaled expenses
        expenses_created = 0
        if result["expenses"]:
            for expense in result["expenses"]:
                expense["id"] = str(uuid.uuid4())
                expense["is_active"] = True
                expense["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                expense["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
            
            df = pd.DataFrame(result["expenses"])
            append_data(NAMESPACE, "scheduled_expenses", df)
            expenses_created = len(result["expenses"])
        
        # Insert scaled revenue
        revenue_created = 0
        if result["revenue"]:
            for rev in result["revenue"]:
                rev["id"] = str(uuid.uuid4())
                rev["is_active"] = True
                rev["created_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
                rev["updated_at"] = pd.Timestamp.now(tz=timezone.utc).floor('us')
            
            df = pd.DataFrame(result["revenue"])
            append_data(NAMESPACE, "scheduled_revenue", df)
            revenue_created = len(result["revenue"])
        
        return {
            "message": "Template applied successfully",
            "property_id": property_id,
            "expenses_created": expenses_created,
            "revenue_created": revenue_created,
            "scaling_factors": result["scaling_factors"]
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduled-financials/save-template/{property_id}")
async def save_template(
    property_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Save a property's scheduled financials as the template.
    This should be called on the reference property (316 S 50th Ave).
    """
    try:
        user_id = current_user["sub"]
        
        # Get property data
        properties_df = read_table(NAMESPACE, "properties")
        property_match = properties_df[
            (properties_df['id'] == property_id) & 
            (properties_df['user_id'] == user_id)
        ]
        
        if property_match.empty:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = property_match.iloc[0].to_dict()
        
        # Save as template
        from uuid import UUID
        success = scheduled_financials_template.save_template_from_property(
            UUID(property_id),
            property_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save template")
        
        return {
            "message": "Template saved successfully",
            "property_id": property_id,
            "property_address": property_data.get("address_line1")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduled-financials/template-info")
async def get_template_info(
    current_user: dict = Depends(get_current_user)
):
    """Get information about the current template"""
    try:
        scheduled_financials_template.initialize()
        
        if not scheduled_financials_template._template_metadata:
            return {
                "template_available": False,
                "message": "No template configured. Use 'save-template' on a reference property first."
            }
        
        return {
            "template_available": True,
            "template_property_id": scheduled_financials_template._template_metadata.get("template_property_id"),
            "purchase_price": float(scheduled_financials_template._template_metadata.get("purchase_price", 0)),
            "bedrooms": float(scheduled_financials_template._template_metadata.get("bedrooms", 0)),
            "bathrooms": float(scheduled_financials_template._template_metadata.get("bathrooms", 0)),
            "square_feet": float(scheduled_financials_template._template_metadata.get("square_feet", 0)),
            "expenses_count": len(scheduled_financials_template._expenses_template),
            "revenue_count": len(scheduled_financials_template._revenue_template)
        }
        
    except Exception as e:
        logger.error(f"Error getting template info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

