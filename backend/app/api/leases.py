"""API routes for lease management"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from uuid import UUID
import uuid
import pandas as pd
import pyarrow as pa
from decimal import Decimal
from datetime import datetime
import json

from app.core.dependencies import get_current_user
from app.schemas.lease import (
    LeaseCreate, LeaseUpdate, LeaseResponse, LeaseListResponse, LeaseListItem,
    TenantResponse, TenantUpdate, GeneratePDFRequest, GeneratePDFResponse,
    TerminateLeaseRequest, TerminateLeaseResponse, PropertySummary, MoveOutCostItem
)
from app.core.iceberg import read_table, append_data, table_exists, load_table, get_catalog
from app.core.logging import get_logger
from app.services.lease_defaults import apply_lease_defaults, get_default_moveout_costs_json
from app.services.lease_generator_service import LeaseGeneratorService
from app.services.adls_service import adls_service

NAMESPACE = ("investflow",)
LEASES_TABLE = "leases"
TENANTS_TABLE = "lease_tenants"

router = APIRouter(prefix="/leases", tags=["leases"])
logger = get_logger(__name__)


def _serialize_moveout_costs(moveout_costs: Optional[List[MoveOutCostItem]]) -> str:
    """Convert move-out costs list to JSON string for storage"""
    if not moveout_costs:
        return get_default_moveout_costs_json()
    
    costs = []
    for item in moveout_costs:
        costs.append({
            "item": item.item,
            "description": item.description,
            "amount": str(item.amount),
            "order": item.order
        })
    return json.dumps(costs)


def _deserialize_moveout_costs(moveout_costs_json: str) -> List[MoveOutCostItem]:
    """Convert JSON string to move-out costs list"""
    try:
        costs = json.loads(moveout_costs_json)
        return [MoveOutCostItem(**cost) for cost in costs]
    except (json.JSONDecodeError, TypeError):
        return []


def _get_property_summary(property_id: str) -> dict:
    """Get property summary for response"""
    try:
        properties_df = read_table(NAMESPACE, "properties")
        property_row = properties_df[properties_df["id"] == property_id]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        prop = property_row.iloc[0]
        return {
            "id": prop["id"],
            "display_name": prop.get("display_name", ""),
            "address": f"{prop.get('address_line1', '')}, {prop.get('city', '')}, {prop.get('state', '')}",
            "city": prop.get("city", ""),
            "state": prop.get("state", ""),
            "zip_code": prop.get("zip_code"),
            "year_built": prop.get("year_built")
        }
    except Exception as e:
        logger.error(f"Error getting property summary: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving property")


def _verify_property_ownership(property_id: str, user_id: str):
    """Verify user owns the property"""
    try:
        properties_df = read_table(NAMESPACE, "properties")
        property_row = properties_df[properties_df["id"] == property_id]
        
        if len(property_row) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        if property_row.iloc[0]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You do not own this property")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying property ownership: {e}")
        raise HTTPException(status_code=500, detail="Error verifying property ownership")


@router.post("", response_model=LeaseResponse, status_code=201)
async def create_lease(
    lease_data: LeaseCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new lease with tenants"""
    try:
        user_id = current_user["sub"]
        lease_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Verify property ownership
        _verify_property_ownership(str(lease_data.property_id), user_id)
        
        # Convert to dict and apply state defaults
        lease_dict = lease_data.model_dump(exclude={"tenants"})
        lease_dict["id"] = lease_id
        lease_dict["user_id"] = user_id
        lease_dict["lease_version"] = 1
        lease_dict["created_at"] = now
        lease_dict["updated_at"] = now
        lease_dict["is_active"] = True
        lease_dict["generated_pdf_document_id"] = None
        lease_dict["template_used"] = f"{lease_data.state}_residential_v1"
        
        # Apply state-specific defaults
        lease_dict = apply_lease_defaults(lease_dict, lease_data.state)
        
        # Serialize moveout_costs
        if lease_data.moveout_costs:
            lease_dict["moveout_costs"] = _serialize_moveout_costs(lease_data.moveout_costs)
        
        # Convert UUIDs and dates to strings for Iceberg
        lease_dict["property_id"] = str(lease_data.property_id)
        lease_dict["unit_id"] = str(lease_data.unit_id) if lease_data.unit_id else None
        lease_dict["commencement_date"] = pd.Timestamp(lease_data.commencement_date)
        lease_dict["termination_date"] = pd.Timestamp(lease_data.termination_date)
        lease_dict["lease_date"] = pd.Timestamp(lease_data.lease_date) if lease_data.lease_date else None
        lease_dict["signed_date"] = None
        
        # Append to Iceberg leases table
        df = pd.DataFrame([lease_dict])
        append_data(NAMESPACE, LEASES_TABLE, df)
        
        # Create tenants
        tenant_responses = []
        for idx, tenant in enumerate(lease_data.tenants):
            tenant_id = str(uuid.uuid4())
            tenant_dict = {
                "id": tenant_id,
                "lease_id": lease_id,
                "tenant_order": idx + 1,
                "first_name": tenant.first_name,
                "last_name": tenant.last_name,
                "email": tenant.email,
                "phone": tenant.phone,
                "signed_date": None,
                "created_at": now,
                "updated_at": now,
            }
            
            tenant_df = pd.DataFrame([tenant_dict])
            append_data(NAMESPACE, TENANTS_TABLE, tenant_df)
            
            tenant_responses.append(TenantResponse(
                id=UUID(tenant_id),
                lease_id=UUID(lease_id),
                tenant_order=idx + 1,
                first_name=tenant.first_name,
                last_name=tenant.last_name,
                email=tenant.email,
                phone=tenant.phone,
                signed_date=None,
                created_at=now.to_pydatetime(),
                updated_at=now.to_pydatetime()
            ))
        
        # Get property summary
        property_summary = _get_property_summary(str(lease_data.property_id))
        
        # Build response
        response_dict = lease_dict.copy()
        response_dict["id"] = UUID(lease_id)
        response_dict["user_id"] = UUID(user_id)
        response_dict["property_id"] = UUID(str(lease_data.property_id))
        response_dict["unit_id"] = UUID(str(lease_data.unit_id)) if lease_data.unit_id else None
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        response_dict["moveout_costs"] = lease_data.moveout_costs or _deserialize_moveout_costs(lease_dict["moveout_costs"])
        response_dict["pdf_url"] = None
        response_dict["latex_url"] = None
        
        return LeaseResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating lease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating lease: {str(e)}")


@router.get("", response_model=LeaseListResponse)
async def list_leases(
    property_id: Optional[UUID] = Query(None, description="Filter by property"),
    status: Optional[str] = Query(None, description="Filter by status"),
    state: Optional[str] = Query(None, description="Filter by state"),
    active_only: bool = Query(False, description="Only active leases"),
    current_user: dict = Depends(get_current_user)
):
    """List all leases for the current user"""
    try:
        user_id = current_user["sub"]
        
        # Read leases
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        leases_df = leases_df[leases_df["user_id"] == user_id]
        
        if active_only:
            leases_df = leases_df[leases_df["is_active"] == True]
        
        if property_id:
            leases_df = leases_df[leases_df["property_id"] == str(property_id)]
        
        if status:
            leases_df = leases_df[leases_df["status"] == status]
        
        if state:
            leases_df = leases_df[leases_df["state"] == state]
        
        # Read tenants
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        
        # Build response
        lease_items = []
        for _, lease in leases_df.iterrows():
            try:
                # Get property summary
                property_summary = _get_property_summary(lease["property_id"])
            
            # Get tenants for this lease
            lease_tenants = tenants_df[tenants_df["lease_id"] == lease["id"]]
            tenant_list = [
                {"first_name": t["first_name"], "last_name": t["last_name"]}
                for _, t in lease_tenants.iterrows()
            ]
            
            # Get PDF URL if exists
            pdf_url = None
            if lease["generated_pdf_document_id"]:
                pdf_url = adls_service.get_blob_download_url(lease["generated_pdf_document_id"])
            
                lease_items.append(LeaseListItem(
                    id=UUID(lease["id"]),
                    property=PropertySummary(**property_summary),
                    tenants=tenant_list,
                    commencement_date=pd.Timestamp(lease["commencement_date"]).date(),
                    termination_date=pd.Timestamp(lease["termination_date"]).date(),
                    monthly_rent=Decimal(str(lease["monthly_rent"])),
                    status=lease["status"],
                    pdf_url=pdf_url,
                    created_at=pd.Timestamp(lease["created_at"]).to_pydatetime()
                ))
            except Exception as e:
                logger.error(f"Error building lease item {lease['id']}: {e}")
                # Skip this lease if there's an error
                continue
        
        return LeaseListResponse(leases=lease_items, total=len(lease_items))
        
    except Exception as e:
        logger.error(f"Error listing leases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing leases: {str(e)}")


@router.get("/{lease_id}", response_model=LeaseResponse)
async def get_lease(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed lease information"""
    try:
        user_id = current_user["sub"]
        
        # Read lease
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_row = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_row) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        lease = lease_row.iloc[0]
        
        # Verify ownership
        if lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this lease")
        
        # Get property summary
        property_summary = _get_property_summary(lease["property_id"])
        
        # Get tenants
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        lease_tenants = tenants_df[tenants_df["lease_id"] == str(lease_id)]
        
        tenant_responses = []
        for _, tenant in lease_tenants.iterrows():
            tenant_responses.append(TenantResponse(
                id=UUID(tenant["id"]),
                lease_id=UUID(tenant["lease_id"]),
                tenant_order=tenant["tenant_order"],
                first_name=tenant["first_name"],
                last_name=tenant["last_name"],
                email=tenant.get("email"),
                phone=tenant.get("phone"),
                signed_date=pd.Timestamp(tenant["signed_date"]).date() if tenant.get("signed_date") else None,
                created_at=pd.Timestamp(tenant["created_at"]).to_pydatetime(),
                updated_at=pd.Timestamp(tenant["updated_at"]).to_pydatetime()
            ))
        
        # Get PDF and LaTeX URLs if they exist
        pdf_url = None
        latex_url = None
        if lease.get("generated_pdf_document_id"):
            pdf_blob = lease["generated_pdf_document_id"]
            latex_blob = pdf_blob.replace('.pdf', '.tex')
            
            if adls_service.blob_exists(pdf_blob):
                pdf_url = adls_service.get_blob_download_url(pdf_blob)
            if adls_service.blob_exists(latex_blob):
                latex_url = adls_service.get_blob_download_url(latex_blob)
        
        # Build response
        response_dict = lease.to_dict()
        response_dict["id"] = UUID(lease["id"])
        response_dict["user_id"] = UUID(lease["user_id"])
        response_dict["property_id"] = UUID(lease["property_id"])
        response_dict["unit_id"] = UUID(lease["unit_id"]) if lease.get("unit_id") else None
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        response_dict["moveout_costs"] = _deserialize_moveout_costs(lease.get("moveout_costs", "[]"))
        response_dict["pdf_url"] = pdf_url
        response_dict["latex_url"] = latex_url
        response_dict["commencement_date"] = pd.Timestamp(lease["commencement_date"]).date()
        response_dict["termination_date"] = pd.Timestamp(lease["termination_date"]).date()
        response_dict["lease_date"] = pd.Timestamp(lease["lease_date"]).date() if lease.get("lease_date") else None
        response_dict["signed_date"] = pd.Timestamp(lease["signed_date"]).date() if lease.get("signed_date") else None
        response_dict["created_at"] = pd.Timestamp(lease["created_at"]).to_pydatetime()
        response_dict["updated_at"] = pd.Timestamp(lease["updated_at"]).to_pydatetime()
        
        return LeaseResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting lease: {str(e)}")


@router.post("/{lease_id}/generate-pdf", response_model=GeneratePDFResponse)
async def generate_lease_pdf(
    lease_id: UUID,
    request: GeneratePDFRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate PDF for lease"""
    try:
        user_id = current_user["sub"]
        
        # Get lease
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_row = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_row) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        lease = lease_row.iloc[0]
        
        # Verify ownership
        if lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Check if PDF already exists (unless regenerate is True)
        if not request.regenerate and lease.get("generated_pdf_document_id"):
            pdf_blob = lease["generated_pdf_document_id"]
            if adls_service.blob_exists(pdf_blob):
                latex_blob = pdf_blob.replace('.pdf', '.tex')
                pdf_url = adls_service.get_blob_download_url(pdf_blob)
                latex_url = adls_service.get_blob_download_url(latex_blob) if adls_service.blob_exists(latex_blob) else None
                
                return GeneratePDFResponse(
                    lease_id=lease_id,
                    pdf_url=pdf_url,
                    latex_url=latex_url,
                    pdf_blob_name=pdf_blob,
                    latex_blob_name=latex_blob,
                    generated_at=datetime.now(),
                    status=lease["status"]
                )
        
        # Get property data
        property_summary = _get_property_summary(lease["property_id"])
        
        # Get tenants
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        lease_tenants = tenants_df[tenants_df["lease_id"] == str(lease_id)]
        tenants = [
            {
                "first_name": t["first_name"],
                "last_name": t["last_name"],
                "email": t.get("email"),
                "phone": t.get("phone")
            }
            for _, t in lease_tenants.iterrows()
        ]
        
        # Generate PDF
        generator = LeaseGeneratorService()
        lease_dict = lease.to_dict()
        
        pdf_bytes, pdf_blob_name, latex_blob_name = generator.generate_lease_pdf(
            lease_data=lease_dict,
            tenants=tenants,
            property_data=property_summary,
            user_id=user_id
        )
        
        # Update lease record with PDF location
        catalog = get_catalog()
        leases_table = catalog.load_table(f"{NAMESPACE[0]}.{LEASES_TABLE}")
        
        # Update the record (using Iceberg update pattern)
        update_dict = {
            "id": str(lease_id),
            "generated_pdf_document_id": pdf_blob_name,
            "status": "pending_signature",
            "updated_at": pd.Timestamp.now()
        }
        
        update_df = pd.DataFrame([update_dict])
        # Note: Iceberg doesn't support in-place updates, we append and filter on read
        # For production, implement proper merge/upsert logic
        
        # Get download URLs
        pdf_url = adls_service.get_blob_download_url(pdf_blob_name)
        latex_url = adls_service.get_blob_download_url(latex_blob_name)
        
        return GeneratePDFResponse(
            lease_id=lease_id,
            pdf_url=pdf_url,
            latex_url=latex_url,
            pdf_blob_name=pdf_blob_name,
            latex_blob_name=latex_blob_name,
            generated_at=datetime.now(),
            status="pending_signature"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.delete("/{lease_id}", status_code=204)
async def delete_lease(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a lease (only if draft)"""
    try:
        user_id = current_user["sub"]
        
        # Get lease
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_row = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_row) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        lease = lease_row.iloc[0]
        
        # Verify ownership
        if lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Can only delete drafts
        if lease["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Can only delete leases in draft status"
            )
        
        # Soft delete (append new record with is_active=False)
        delete_dict = lease.to_dict()
        delete_dict["is_active"] = False
        delete_dict["updated_at"] = pd.Timestamp.now()
        
        df = pd.DataFrame([delete_dict])
        append_data(NAMESPACE, LEASES_TABLE, df)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting lease: {str(e)}")


@router.get("/{lease_id}/tenants", response_model=List[TenantResponse])
async def list_tenants(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """List all tenants for a lease"""
    try:
        user_id = current_user["sub"]
        
        # Verify lease ownership
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_row = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_row) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        if lease_row.iloc[0]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get tenants
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        lease_tenants = tenants_df[tenants_df["lease_id"] == str(lease_id)]
        
        tenant_responses = []
        for _, tenant in lease_tenants.iterrows():
            tenant_responses.append(TenantResponse(
                id=UUID(tenant["id"]),
                lease_id=UUID(tenant["lease_id"]),
                tenant_order=tenant["tenant_order"],
                first_name=tenant["first_name"],
                last_name=tenant["last_name"],
                email=tenant.get("email"),
                phone=tenant.get("phone"),
                signed_date=pd.Timestamp(tenant["signed_date"]).date() if tenant.get("signed_date") else None,
                created_at=pd.Timestamp(tenant["created_at"]).to_pydatetime(),
                updated_at=pd.Timestamp(tenant["updated_at"]).to_pydatetime()
            ))
        
        return tenant_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tenants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing tenants: {str(e)}")

