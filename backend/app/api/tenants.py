from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID, uuid4
import pandas as pd
from datetime import datetime
from decimal import Decimal
import json

from app.core.iceberg import read_table, load_table, append_data, upsert_data, upsert_data_with_schema_cast
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
        # Validate property_id is provided
        if not tenant_data.property_id:
            raise HTTPException(status_code=400, detail="property_id is required")
        
        tenant_id = str(uuid4())
        now = pd.Timestamp.now()
        
        # Convert Pydantic model to dict
        tenant_dict = tenant_data.model_dump()
        tenant_dict.update({
            "id": tenant_id,
            "created_at": now,
            "updated_at": now,
        })
        
        # Convert UUID fields to strings
        if tenant_dict.get("property_id"):
            tenant_dict["property_id"] = str(tenant_dict["property_id"])
        if tenant_dict.get("unit_id"):
            tenant_dict["unit_id"] = str(tenant_dict["unit_id"])
        
        # Convert Decimal fields
        if tenant_dict.get("monthly_income"):
            tenant_dict["monthly_income"] = Decimal(str(tenant_dict["monthly_income"]))
        
        # Convert landlord_references list to JSON string
        if tenant_dict.get("landlord_references"):
            tenant_dict["landlord_references"] = json.dumps(tenant_dict["landlord_references"])
        else:
            tenant_dict["landlord_references"] = "[]"  # Empty JSON array
        
        # Create DataFrame
        df = pd.DataFrame([tenant_dict])
        
        # Append to Iceberg table
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created tenant {tenant_id} for property {tenant_dict['property_id']}")
        
        # Parse landlord_references for response
        if tenant_dict.get("landlord_references"):
            try:
                tenant_dict["landlord_references"] = json.loads(tenant_dict["landlord_references"]) if isinstance(tenant_dict["landlord_references"], str) else tenant_dict["landlord_references"]
            except (json.JSONDecodeError, TypeError):
                tenant_dict["landlord_references"] = []
        else:
            tenant_dict["landlord_references"] = []
        
        # Return created tenant
        return TenantResponse.from_dict(tenant_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating tenant: {str(e)}")


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    property_id: UUID = Query(..., description="Filter by property ID (required)"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)  # User still needed for auth
):
    """List tenants for a property (property_id required)"""
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] list_tenants started")
    
    try:
        # Read tenants table
        read_start = time.time()
        df = read_table(NAMESPACE, TABLE_NAME)
        logger.info(f"⏱️ [PERF] read_table(tenants) took {time.time() - read_start:.2f}s")
        
        # Filter by property_id (required)
        mask = (df["property_id"] == str(property_id))
        
        if unit_id:
            mask = mask & (df["unit_id"] == str(unit_id))
        
        if status:
            mask = mask & (df["status"] == status)
        
        filtered_df = df[mask].head(limit)
        
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
            for field in ["date_of_birth"]:
                if pd.notna(tenant_dict.get(field)):
                    tenant_dict[field] = pd.Timestamp(tenant_dict[field]).date()
                else:
                    tenant_dict[field] = None
            
            # Convert UUID strings back to UUID objects
            for field in ["id", "property_id", "unit_id"]:
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
            for field in ["previous_landlord_contacted"]:
                if pd.isna(tenant_dict.get(field)):
                    tenant_dict[field] = None
            
            # Parse landlord_references JSON string
            if tenant_dict.get("landlord_references"):
                try:
                    tenant_dict["landlord_references"] = json.loads(tenant_dict["landlord_references"]) if isinstance(tenant_dict["landlord_references"], str) else tenant_dict["landlord_references"]
                except (json.JSONDecodeError, TypeError):
                    tenant_dict["landlord_references"] = []
            else:
                tenant_dict["landlord_references"] = []
            
            tenants.append(TenantResponse.from_dict(tenant_dict))
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
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID (security via property_id)
        mask = (df["id"] == str(tenant_id))
        tenant_row = df[mask]
        
        if len(tenant_row) == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        tenant_dict = tenant_row.iloc[0].to_dict()
        
        # Convert timestamps
        for field in ["created_at", "updated_at"]:
            if pd.notna(tenant_dict.get(field)):
                tenant_dict[field] = pd.Timestamp(tenant_dict[field])
        
        # Convert date fields
        for field in ["date_of_birth"]:
            if pd.notna(tenant_dict.get(field)):
                tenant_dict[field] = pd.Timestamp(tenant_dict[field]).date()
            else:
                tenant_dict[field] = None
        
        # Convert UUID strings back to UUID objects
        for field in ["id", "property_id", "unit_id"]:
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
        
        # Parse landlord_references JSON string
        if tenant_dict.get("landlord_references"):
            try:
                tenant_dict["landlord_references"] = json.loads(tenant_dict["landlord_references"]) if isinstance(tenant_dict["landlord_references"], str) else tenant_dict["landlord_references"]
            except (json.JSONDecodeError, TypeError):
                tenant_dict["landlord_references"] = []
        else:
            tenant_dict["landlord_references"] = []
        
        return TenantResponse.from_dict(tenant_dict)
        
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
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID (security via property_id)
        mask = (df["id"] == str(tenant_id))
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Get current tenant data
        current_tenant = df[mask].iloc[0].to_dict()
        
        # Update with new data (only non-None fields)
        update_dict = tenant_data.model_dump(exclude_unset=True)
        
        # Validate property_id if being updated (cannot be removed)
        if "property_id" in update_dict and update_dict["property_id"] is None:
            raise HTTPException(status_code=400, detail="property_id cannot be removed")
        
        # Convert UUID fields to strings
        for field in ["property_id", "unit_id"]:
            if field in update_dict and update_dict[field] is not None:
                update_dict[field] = str(update_dict[field])
        
        # Convert Decimal fields
        if "monthly_income" in update_dict and update_dict["monthly_income"] is not None:
            update_dict["monthly_income"] = Decimal(str(update_dict["monthly_income"]))
        
        # Convert landlord_references list to JSON string if provided
        if "landlord_references" in update_dict and update_dict["landlord_references"] is not None:
            if isinstance(update_dict["landlord_references"], list):
                update_dict["landlord_references"] = json.dumps(update_dict["landlord_references"])
            # If it's already a string, keep it as is
        elif "landlord_references" in update_dict and update_dict["landlord_references"] is None:
            update_dict["landlord_references"] = "[]"  # Empty JSON array
        
        current_tenant.update(update_dict)
        current_tenant["updated_at"] = pd.Timestamp.now()
        
        # Ensure required fields are present and non-null
        # id is always required
        current_tenant["id"] = str(tenant_id)
        
        # property_id is required
        if "property_id" in update_dict and update_dict["property_id"]:
            current_tenant["property_id"] = str(update_dict["property_id"])
        elif not current_tenant.get("property_id") or pd.isna(current_tenant.get("property_id")):
            raise HTTPException(status_code=400, detail="property_id is required and cannot be empty")
        else:
            current_tenant["property_id"] = str(current_tenant["property_id"])
        
        # first_name is required
        if "first_name" in update_dict and update_dict["first_name"]:
            current_tenant["first_name"] = str(update_dict["first_name"])
        elif not current_tenant.get("first_name") or pd.isna(current_tenant.get("first_name")):
            raise HTTPException(status_code=400, detail="first_name is required and cannot be empty")
        else:
            current_tenant["first_name"] = str(current_tenant["first_name"])
        
        # last_name is required
        if "last_name" in update_dict and update_dict["last_name"]:
            current_tenant["last_name"] = str(update_dict["last_name"])
        elif not current_tenant.get("last_name") or pd.isna(current_tenant.get("last_name")):
            raise HTTPException(status_code=400, detail="last_name is required and cannot be empty")
        else:
            current_tenant["last_name"] = str(current_tenant["last_name"])
        
        # Convert UUID fields to strings (unit_id is optional)
        if current_tenant.get("unit_id") and pd.notna(current_tenant.get("unit_id")):
            current_tenant["unit_id"] = str(current_tenant["unit_id"])
        else:
            current_tenant["unit_id"] = None  # unit_id is optional
        
        # Ensure timestamps are proper pandas Timestamps
        if "created_at" not in current_tenant or pd.isna(current_tenant.get("created_at")):
            current_tenant["created_at"] = pd.Timestamp.now()
        else:
            current_tenant["created_at"] = pd.Timestamp(current_tenant["created_at"])
        
        # Get table schema to ensure proper field ordering and types
        from app.core.iceberg import load_table
        table = load_table(NAMESPACE, TABLE_NAME)
        schema_fields = [field.name for field in table.schema().fields]
        
        # Ensure all schema fields are present in current_tenant
        for field_name in schema_fields:
            if field_name not in current_tenant:
                # Set to None for optional fields, but required fields should already be set
                if field_name in ["id", "property_id", "first_name", "last_name"]:
                    # These should already be set above, but ensure they're strings
                    if field_name == "id":
                        current_tenant[field_name] = str(tenant_id)
                    elif field_name == "property_id":
                        current_tenant[field_name] = str(current_tenant.get("property_id", ""))
                    elif field_name == "first_name":
                        current_tenant[field_name] = str(current_tenant.get("first_name", ""))
                    elif field_name == "last_name":
                        current_tenant[field_name] = str(current_tenant.get("last_name", ""))
                else:
                    current_tenant[field_name] = None
        
        # Reorder current_tenant dict to match schema order
        ordered_tenant = {field: current_tenant.get(field) for field in schema_fields}
        
        # Create update DataFrame with fields in schema order
        updated_row_df = pd.DataFrame([ordered_tenant])
        
        # Ensure required string fields are explicitly non-null strings
        required_string_fields = ["id", "property_id", "first_name", "last_name"]
        for field in required_string_fields:
            if field in updated_row_df.columns:
                # Replace any NaN with empty string, then convert to string
                updated_row_df[field] = updated_row_df[field].fillna("").astype(str)
                # Ensure no empty strings for required fields
                if updated_row_df[field].iloc[0] == "":
                    raise HTTPException(status_code=400, detail=f"{field} is required and cannot be empty")
        
        # Use the new upsert function with schema casting to ensure required fields are properly marked
        upsert_data_with_schema_cast(NAMESPACE, TABLE_NAME, updated_row_df, join_cols=["id"])
        
        logger.info(f"Updated tenant {tenant_id}")
        
        # Convert back for response
        for field in ["created_at", "updated_at"]:
            if pd.notna(current_tenant.get(field)):
                current_tenant[field] = pd.Timestamp(current_tenant[field])
        
        for field in ["date_of_birth"]:
            if pd.notna(current_tenant.get(field)):
                current_tenant[field] = pd.Timestamp(current_tenant[field]).date()
            else:
                current_tenant[field] = None
        
        for field in ["id", "property_id", "unit_id"]:
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
        
        # Parse landlord_references JSON string
        if current_tenant.get("landlord_references"):
            try:
                current_tenant["landlord_references"] = json.loads(current_tenant["landlord_references"]) if isinstance(current_tenant["landlord_references"], str) else current_tenant["landlord_references"]
            except (json.JSONDecodeError, TypeError):
                current_tenant["landlord_references"] = []
        else:
            current_tenant["landlord_references"] = []
        
        return TenantResponse.from_dict(current_tenant)
        
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
    """Delete a tenant (hard delete - is_deleted column removed)"""
    try:
        # Read tenants table
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by ID (security via property_id)
        mask = (df["id"] == str(tenant_id))
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # Hard delete - remove the row
        table = load_table(NAMESPACE, TABLE_NAME)
        table.delete(EqualTo("id", str(tenant_id)))
        
        logger.info(f"Deleted tenant {tenant_id}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting tenant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting tenant: {str(e)}")

