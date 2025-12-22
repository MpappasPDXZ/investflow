from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from uuid import UUID, uuid4
import pandas as pd
from datetime import datetime

from app.core.iceberg import read_table, append_data, upsert_data, table_exists
from app.core.logging import get_logger
from app.core.dependencies import get_current_user
from app.schemas.landlord_reference import (
    LandlordReferenceCreate, 
    LandlordReferenceUpdate, 
    LandlordReferenceResponse,
    LandlordReferenceListResponse
)

logger = get_logger(__name__)

router = APIRouter(prefix="/landlord-references", tags=["landlord-references"])

NAMESPACE = ("investflow",)
TABLE_NAME = "tenant_landlord_references"


@router.post("", response_model=LandlordReferenceResponse, status_code=201)
async def create_landlord_reference(
    reference_data: LandlordReferenceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new landlord reference check"""
    try:
        # Check if table exists, if not provide helpful error
        if not table_exists(NAMESPACE, TABLE_NAME):
            logger.error(f"Table {'.'.join((*NAMESPACE, TABLE_NAME))} does not exist. Please run migration script.")
            raise HTTPException(
                status_code=500, 
                detail=f"Table tenant_landlord_references does not exist. Please run: docker-compose exec backend uv run app/scripts/migrate_add_fields.py"
            )
        
        user_id = current_user["sub"]
        reference_id = str(uuid4())
        now = pd.Timestamp.now()
        
        # Convert Pydantic model to dict
        reference_dict = reference_data.model_dump()
        
        # Convert contact_date to pandas date if it's a date object
        if "contact_date" in reference_dict and reference_dict["contact_date"]:
            if isinstance(reference_dict["contact_date"], str):
                # Parse string date to date object
                from datetime import datetime
                reference_dict["contact_date"] = datetime.strptime(reference_dict["contact_date"], "%Y-%m-%d").date()
            # Convert date to pandas Timestamp then to date
            reference_dict["contact_date"] = pd.Timestamp(reference_dict["contact_date"]).date()
        
        reference_dict.update({
            "id": reference_id,
            "user_id": user_id,
            "tenant_id": str(reference_dict["tenant_id"]),
            "created_at": now,
            "updated_at": now,
        })
        
        # Create DataFrame
        df = pd.DataFrame([reference_dict])
        
        # Append to Iceberg table
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created landlord reference {reference_id} for tenant {reference_dict['tenant_id']}")
        
        # Return created reference
        reference_dict["created_at"] = now
        reference_dict["updated_at"] = now
        reference_dict["id"] = UUID(reference_id)
        reference_dict["tenant_id"] = UUID(reference_dict["tenant_id"])
        
        return LandlordReferenceResponse(**reference_dict)
        
    except Exception as e:
        logger.error(f"Error creating landlord reference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating landlord reference: {str(e)}")


@router.get("", response_model=LandlordReferenceListResponse)
async def list_landlord_references(
    current_user: dict = Depends(get_current_user),
    tenant_id: Optional[UUID] = Query(None, description="Filter by tenant ID"),
    limit: int = Query(100, ge=1, le=1000)
):
    """List all landlord references for the current user"""
    try:
        user_id = current_user["sub"]
        
        # Read references table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by user
        mask = (df["user_id"] == user_id)
        
        if tenant_id:
            mask = mask & (df["tenant_id"] == str(tenant_id))
        
        filtered_df = df[mask].head(limit)
        
        # Convert to list of dicts
        references = []
        passed_count = 0
        
        for _, row in filtered_df.iterrows():
            ref_dict = row.to_dict()
            
            # Convert timestamps
            for field in ["created_at", "updated_at"]:
                if pd.notna(ref_dict.get(field)):
                    ref_dict[field] = pd.Timestamp(ref_dict[field])
            
            # Convert date fields
            for field in ["contact_date"]:
                if pd.notna(ref_dict.get(field)):
                    ref_dict[field] = pd.Timestamp(ref_dict[field]).date()
                else:
                    ref_dict[field] = None
            
            # Convert UUID strings back to UUID objects
            for field in ["id", "tenant_id"]:
                if ref_dict.get(field) and ref_dict[field] != "None":
                    try:
                        ref_dict[field] = UUID(ref_dict[field])
                    except:
                        ref_dict[field] = None
                else:
                    ref_dict[field] = None
            
            # Count passed references
            if ref_dict.get("status") == "pass":
                passed_count += 1
            
            references.append(LandlordReferenceResponse(**ref_dict))
        
        return LandlordReferenceListResponse(
            references=references, 
            total=len(filtered_df),
            passed_count=passed_count
        )
        
    except Exception as e:
        logger.error(f"Error listing landlord references: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing landlord references: {str(e)}")


@router.get("/{reference_id}", response_model=LandlordReferenceResponse)
async def get_landlord_reference(
    reference_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific landlord reference by ID"""
    try:
        user_id = current_user["sub"]
        
        # Read references table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID and user
        mask = (df["id"] == str(reference_id)) & (df["user_id"] == user_id)
        reference_row = df[mask]
        
        if len(reference_row) == 0:
            raise HTTPException(status_code=404, detail="Landlord reference not found")
        
        ref_dict = reference_row.iloc[0].to_dict()
        
        # Convert timestamps
        for field in ["created_at", "updated_at"]:
            if pd.notna(ref_dict.get(field)):
                ref_dict[field] = pd.Timestamp(ref_dict[field])
        
        # Convert date fields
        for field in ["contact_date"]:
            if pd.notna(ref_dict.get(field)):
                ref_dict[field] = pd.Timestamp(ref_dict[field]).date()
            else:
                ref_dict[field] = None
        
        # Convert UUID strings
        for field in ["id", "tenant_id"]:
            if ref_dict.get(field) and ref_dict[field] != "None":
                try:
                    ref_dict[field] = UUID(ref_dict[field])
                except:
                    ref_dict[field] = None
            else:
                ref_dict[field] = None
        
        return LandlordReferenceResponse(**ref_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting landlord reference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting landlord reference: {str(e)}")


@router.put("/{reference_id}", response_model=LandlordReferenceResponse)
async def update_landlord_reference(
    reference_id: UUID,
    reference_data: LandlordReferenceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update landlord reference information"""
    try:
        user_id = current_user["sub"]
        
        # Read references table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID and user
        mask = (df["id"] == str(reference_id)) & (df["user_id"] == user_id)
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Landlord reference not found")
        
        # Get current reference data
        current_ref = df[mask].iloc[0].to_dict()
        
        # Update with new data (only non-None fields)
        update_dict = reference_data.model_dump(exclude_unset=True)
        
        current_ref.update(update_dict)
        current_ref["updated_at"] = pd.Timestamp.now()
        
        # Create update DataFrame
        updated_row_df = pd.DataFrame([current_ref])
        
        # Upsert using the helper
        upsert_data(NAMESPACE, TABLE_NAME, updated_row_df, join_cols=["id"])
        
        logger.info(f"Updated landlord reference {reference_id}")
        
        # Convert back for response
        for field in ["created_at", "updated_at"]:
            if pd.notna(current_ref.get(field)):
                current_ref[field] = pd.Timestamp(current_ref[field])
        
        for field in ["contact_date"]:
            if pd.notna(current_ref.get(field)):
                current_ref[field] = pd.Timestamp(current_ref[field]).date()
            else:
                current_ref[field] = None
        
        for field in ["id", "tenant_id"]:
            if current_ref.get(field) and current_ref[field] != "None":
                try:
                    current_ref[field] = UUID(current_ref[field])
                except:
                    current_ref[field] = None
            else:
                current_ref[field] = None
        
        return LandlordReferenceResponse(**current_ref)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating landlord reference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating landlord reference: {str(e)}")


@router.delete("/{reference_id}", status_code=204)
async def delete_landlord_reference(
    reference_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete a landlord reference"""
    try:
        user_id = current_user["sub"]
        
        # Read references table
        from app.core.iceberg import load_table
        from pyiceberg.expressions import EqualTo, And
        
        table = load_table(NAMESPACE, TABLE_NAME)
        
        # Delete the reference
        table.delete(And(
            EqualTo("id", str(reference_id)),
            EqualTo("user_id", user_id)
        ))
        
        logger.info(f"Deleted landlord reference {reference_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting landlord reference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting landlord reference: {str(e)}")

