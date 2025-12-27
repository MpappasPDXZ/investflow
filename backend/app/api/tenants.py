from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID, uuid4
import pandas as pd
from datetime import datetime
from decimal import Decimal

from app.core.iceberg import read_table, load_table, append_data, upsert_data
from app.core.logging import get_logger
from app.core.dependencies import get_current_user
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse, TenantListResponse
from pyiceberg.expressions import EqualTo, And

logger = get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])

NAMESPACE = ("investflow",)
TABLE_NAME = "tenants"


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new tenant profile"""
    try:
        user_id = current_user["sub"]
        tenant_id = str(uuid4())
        now = pd.Timestamp.now()
        
        # Convert Pydantic model to dict
        tenant_dict = tenant_data.model_dump()
        tenant_dict.update({
            "id": tenant_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False
        })
        
        # Convert UUID fields to strings
        if tenant_dict.get("property_id"):
            tenant_dict["property_id"] = str(tenant_dict["property_id"])
        if tenant_dict.get("unit_id"):
            tenant_dict["unit_id"] = str(tenant_dict["unit_id"])
        if tenant_dict.get("lease_id"):
            tenant_dict["lease_id"] = str(tenant_dict["lease_id"])
        
        # Convert Decimal fields
        if tenant_dict.get("monthly_income"):
            tenant_dict["monthly_income"] = Decimal(str(tenant_dict["monthly_income"]))
        
        # Create DataFrame
        df = pd.DataFrame([tenant_dict])
        
        # Append to Iceberg table
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created tenant {tenant_id} for user {user_id}")
        
        # Return created tenant
        return TenantResponse(**tenant_dict)
        
    except Exception as e:
        logger.error(f"Error creating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating tenant: {str(e)}")


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    current_user: dict = Depends(get_current_user),
    property_id: Optional[UUID] = Query(None, description="Filter by property ID"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000)
):
    """List all tenants for the current user"""
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] list_tenants started")
    
    try:
        user_id = current_user["sub"]
        
        # Read tenants table
        read_start = time.time()
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"⏱️ [PERF] read_table(tenants) took {time.time() - read_start:.2f}s")
        
        # Filter by user and non-deleted
        mask = (df["user_id"] == user_id) & (~df["is_deleted"])
        
        if property_id:
            mask = mask & (df["property_id"] == str(property_id))
        
        if unit_id:
            mask = mask & (df["unit_id"] == str(unit_id))
        
        if status:
            mask = mask & (df["status"] == status)
        
        filtered_df = df[mask].head(limit)
        
        # Get landlord references count for each tenant
        ref_start = time.time()
        try:
            ref_df = read_table(NAMESPACE, "tenant_landlord_references")
            ref_df = ref_df[ref_df["user_id"] == user_id]
        except:
            ref_df = pd.DataFrame()  # Table might not exist yet
        logger.info(f"⏱️ [PERF] read_table(tenant_landlord_references) took {time.time() - ref_start:.2f}s")
        
        # Convert to list of dicts
        convert_start = time.time()
        tenants = []
        for _, row in filtered_df.iterrows():
            tenant_dict = row.to_dict()
            
            # Convert timestamps
            for field in ["created_at", "updated_at"]:
                if pd.notna(tenant_dict.get(field)):
                    tenant_dict[field] = pd.Timestamp(tenant_dict[field])
            
            # Convert date fields
            for field in ["date_of_birth", "employment_start_date", "background_check_date"]:
                if pd.notna(tenant_dict.get(field)):
                    tenant_dict[field] = pd.Timestamp(tenant_dict[field]).date()
                else:
                    tenant_dict[field] = None
            
            # Convert UUID strings back to UUID objects
            for field in ["id", "property_id", "unit_id", "lease_id"]:
                if tenant_dict.get(field) and tenant_dict[field] != "None":
                    try:
                        tenant_dict[field] = UUID(tenant_dict[field])
                    except:
                        tenant_dict[field] = None
                else:
                    tenant_dict[field] = None
            
            # Handle NaN values for optional integer/numeric fields
            for field in ["credit_score"]:
                if pd.isna(tenant_dict.get(field)):
                    tenant_dict[field] = None
            
            # Handle NaN values for optional Decimal fields
            for field in ["monthly_income"]:
                if pd.isna(tenant_dict.get(field)):
                    tenant_dict[field] = None
            
            # Handle NaN values for boolean fields
            for field in ["has_evictions", "previous_landlord_contacted"]:
                if pd.isna(tenant_dict.get(field)):
                    tenant_dict[field] = None
            
            # Count passed landlord references for this tenant
            if not ref_df.empty:
                tenant_refs = ref_df[(ref_df["tenant_id"] == str(tenant_dict["id"])) & (ref_df["status"] == "pass")]
                tenant_dict["landlord_references_passed"] = len(tenant_refs)
            else:
                tenant_dict["landlord_references_passed"] = 0
            
            tenants.append(TenantResponse(**tenant_dict))
        logger.info(f"⏱️ [PERF] Converting to TenantResponse objects took {time.time() - convert_start:.2f}s")
        
        total_time = time.time() - endpoint_start
        logger.info(f"⏱️ [PERF] list_tenants completed in {total_time:.2f}s")
        
        return TenantListResponse(tenants=tenants, total=len(filtered_df))
        
    except Exception as e:
        total_time = time.time() - endpoint_start
        logger.error(f"⏱️ [PERF] list_tenants failed after {total_time:.2f}s: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing tenants: {str(e)}")


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific tenant by ID"""
    try:
        user_id = current_user["sub"]
        
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID and user
        mask = (df["id"] == str(tenant_id)) & (df["user_id"] == user_id) & (~df["is_deleted"])
        tenant_row = df[mask]
        
        if len(tenant_row) == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        tenant_dict = tenant_row.iloc[0].to_dict()
        
        # Convert timestamps
        for field in ["created_at", "updated_at"]:
            if pd.notna(tenant_dict.get(field)):
                tenant_dict[field] = pd.Timestamp(tenant_dict[field])
        
        # Convert date fields
        for field in ["date_of_birth", "employment_start_date", "background_check_date"]:
            if pd.notna(tenant_dict.get(field)):
                tenant_dict[field] = pd.Timestamp(tenant_dict[field]).date()
            else:
                tenant_dict[field] = None
        
        # Convert UUID strings back to UUID objects
        for field in ["id", "property_id", "unit_id", "lease_id"]:
            if tenant_dict.get(field) and tenant_dict[field] != "None":
                try:
                    tenant_dict[field] = UUID(tenant_dict[field])
                except:
                    tenant_dict[field] = None
            else:
                tenant_dict[field] = None
        
        # Handle NaN values for optional integer/numeric fields
        for field in ["credit_score"]:
            if pd.isna(tenant_dict.get(field)):
                tenant_dict[field] = None
        
        # Handle NaN values for optional Decimal fields
        for field in ["monthly_income"]:
            if pd.isna(tenant_dict.get(field)):
                tenant_dict[field] = None
        
        return TenantResponse(**tenant_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting tenant: {str(e)}")


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update tenant information"""
    try:
        user_id = current_user["sub"]
        
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID and user
        mask = (df["id"] == str(tenant_id)) & (df["user_id"] == user_id) & (~df["is_deleted"])
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get current tenant data
        current_tenant = df[mask].iloc[0].to_dict()
        
        # Update with new data (only non-None fields)
        update_dict = tenant_data.model_dump(exclude_unset=True)
        
        # Convert UUID fields to strings
        for field in ["property_id", "unit_id", "lease_id"]:
            if field in update_dict and update_dict[field] is not None:
                update_dict[field] = str(update_dict[field])
        
        # Convert Decimal fields
        if "monthly_income" in update_dict and update_dict["monthly_income"] is not None:
            update_dict["monthly_income"] = Decimal(str(update_dict["monthly_income"]))
        
        current_tenant.update(update_dict)
        current_tenant["updated_at"] = pd.Timestamp.now()
        
        # Create update DataFrame
        updated_row_df = pd.DataFrame([current_tenant])
        
        # Upsert using the helper
        upsert_data(NAMESPACE, TABLE_NAME, updated_row_df, join_cols=["id"])
        
        logger.info(f"Updated tenant {tenant_id}")
        
        # Convert back for response
        for field in ["created_at", "updated_at"]:
            if pd.notna(current_tenant.get(field)):
                current_tenant[field] = pd.Timestamp(current_tenant[field])
        
        for field in ["date_of_birth", "employment_start_date", "background_check_date"]:
            if pd.notna(current_tenant.get(field)):
                current_tenant[field] = pd.Timestamp(current_tenant[field]).date()
            else:
                current_tenant[field] = None
        
        for field in ["id", "property_id", "unit_id", "lease_id"]:
            if current_tenant.get(field) and current_tenant[field] != "None":
                try:
                    current_tenant[field] = UUID(current_tenant[field])
                except:
                    current_tenant[field] = None
            else:
                current_tenant[field] = None
        
        # Handle NaN values
        for field in ["credit_score"]:
            if pd.isna(current_tenant.get(field)):
                current_tenant[field] = None
        
        for field in ["monthly_income"]:
            if pd.isna(current_tenant.get(field)):
                current_tenant[field] = None
        
        return TenantResponse(**current_tenant)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating tenant: {str(e)}")


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a tenant"""
    try:
        user_id = current_user["sub"]
        
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID and user
        mask = (df["id"] == str(tenant_id)) & (df["user_id"] == user_id) & (~df["is_deleted"])
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Mark as deleted
        tenant_dict = df[mask].iloc[0].to_dict()
        tenant_dict["is_deleted"] = True
        tenant_dict["updated_at"] = pd.Timestamp.now()
        
        updated_row_df = pd.DataFrame([tenant_dict])
        
        # Upsert using the helper
        upsert_data(NAMESPACE, TABLE_NAME, updated_row_df, join_cols=["id"])
        
        logger.info(f"Deleted tenant {tenant_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting tenant: {str(e)}")

