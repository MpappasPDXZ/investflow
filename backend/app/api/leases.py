"""API routes for lease management"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional, Union
from uuid import UUID
import uuid
import pandas as pd
import pyarrow as pa
from decimal import Decimal
from datetime import datetime, date, time
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
LEASES_TABLE = "leases_full"
TENANTS_TABLE = "lease_tenants"
PROPERTIES_TABLE = "properties"

router = APIRouter(prefix="/leases", tags=["leases"])
logger = get_logger(__name__)


def parse_date_midday(date_value: Union[str, date, datetime, pd.Timestamp]) -> pd.Timestamp:
    """
    Parse date using Midday Strategy to prevent timezone shifting.
    Sets time to 12:00:00 (noon) to provide buffer against timezone offsets.
    """
    if date_value is None:
        return None
    
    # If already a pandas Timestamp, extract the date part
    if isinstance(date_value, pd.Timestamp):
        date_value = date_value.date()
    
    # If it's a datetime, extract the date part
    if isinstance(date_value, datetime):
        date_value = date_value.date()
    
    # If it's a string, parse it to a date
    if isinstance(date_value, str):
        date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
    
    # Now date_value should be a date object
    # Combine with midday time (12:00:00)
    midday_datetime = datetime.combine(date_value, time(12, 0, 0))
    
    # Convert to pandas Timestamp
    return pd.Timestamp(midday_datetime)


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


def _serialize_pets(pets: Optional[List[dict]]) -> Optional[str]:
    """Convert pets list to JSON string for storage"""
    if not pets:
        return None
    return json.dumps(pets)


def _deserialize_pets(pets_json: Optional[str]) -> Optional[List[dict]]:
    """Convert JSON string to pets list"""
    if not pets_json:
        return None
    try:
        return json.loads(pets_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _get_property_summary(property_id: str, unit_id: Optional[str] = None) -> dict:
    """Get property summary for response, including unit info if provided"""
    try:
        properties_df = read_table(NAMESPACE, "properties")
        
        # Filter for active properties only - handle None/NaN as True
        if "is_active" in properties_df.columns:
            properties_df = properties_df[properties_df["is_active"].fillna(True) == True]
        
        property_row = properties_df[properties_df["id"] == property_id]
        
        if len(property_row) == 0:
            logger.warning(f"Property not found: {property_id}")
            # Return a default instead of raising exception to prevent lease list from breaking
            return {
                "id": property_id,
                "display_name": "Unknown Property",
                "address": "",
                "city": "",
                "state": "",
                "zip_code": None,
                "year_built": None
            }
        
        prop = property_row.iloc[0]
        display_name = prop.get("display_name", "")
        
        # If unit_id is provided and property is multi-family, get unit info
        unit_number = None
        if unit_id and prop.get("property_type") != "single_family":
            try:
                units_df = read_table(NAMESPACE, "units")
                # Filter for active units - handle None/NaN as True
                if "is_active" in units_df.columns:
                    units_df = units_df[units_df["is_active"].fillna(True) == True]
                
                unit_row = units_df[units_df["id"] == unit_id]
                
                if len(unit_row) > 0:
                    unit = unit_row.iloc[0]
                    unit_number = unit.get("unit_number", "")
                    display_name = f"{display_name} - Unit {unit_number}"
            except Exception as e:
                logger.warning(f"Error fetching unit {unit_id}: {e}")
        
        # Build address - include unit number if present
        base_address = prop.get('address_line1', '')
        city = prop.get('city', '')
        state = prop.get('state', '')
        zip_code = prop.get('zip_code', '')
        
        if unit_number:
            # The unit number (e.g., "316 1/2") replaces the street number in the address
            # Base: "316 S 50th Ave" + Unit: "316 1/2" -> "316 1/2 S 50th Ave"
            # Extract the street name part (everything after the first space-separated number)
            address_parts = base_address.split(' ', 1)
            if len(address_parts) > 1:
                street_part = address_parts[1]  # "S 50th Ave"
                full_address = f"{unit_number} {street_part}, {city}, {state} {zip_code}".strip()
            else:
                full_address = f"{unit_number}, {city}, {state} {zip_code}".strip()
        else:
            full_address = f"{base_address}, {city}, {state} {zip_code}".strip()
        
        # Handle NaN values for Pydantic validation
        year_built = prop.get("year_built")
        if pd.isna(year_built):
            year_built = None
        
        return {
            "id": prop["id"],
            "display_name": display_name,
            "address": full_address,
            "city": prop.get("city", ""),
            "state": prop.get("state", ""),
            "zip_code": prop.get("zip_code"),
            "year_built": year_built
        }
    except Exception as e:
        logger.error(f"Error getting property summary for {property_id}: {e}", exc_info=True)
        # Return a default instead of raising to prevent breaking lease list
        return {
            "id": property_id,
            "display_name": "Unknown Property",
            "address": "",
            "city": "",
            "state": "",
            "zip_code": None,
            "year_built": None
        }


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
        
        # Generate lease_number: get max lease_number for this user and increment
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        user_leases = leases_df[leases_df["user_id"] == user_id]
        if len(user_leases) > 0 and "lease_number" in user_leases.columns:
            # Convert to numeric, coercing errors to NaN (handles mixed str/float types)
            numeric_lease_numbers = pd.to_numeric(user_leases["lease_number"], errors='coerce')
            max_lease_number = numeric_lease_numbers.max()
            lease_number = int(max_lease_number) + 1 if pd.notna(max_lease_number) else 1
        else:
            lease_number = 1
        
        # Convert to dict and apply state defaults
        lease_dict = lease_data.model_dump(exclude={"tenants"})
        lease_dict["id"] = lease_id
        lease_dict["user_id"] = user_id
        lease_dict["lease_number"] = lease_number
        lease_dict["is_official"] = False  # Default to not official
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
        
        # Serialize pets
        if lease_data.pets:
            lease_dict["pets"] = _serialize_pets([p.model_dump() if hasattr(p, 'model_dump') else p for p in lease_data.pets])
        
        # Convert UUIDs and dates to strings for Iceberg
        lease_dict["property_id"] = str(lease_data.property_id)
        lease_dict["unit_id"] = str(lease_data.unit_id) if lease_data.unit_id else None
        # Parse dates using Midday Strategy (12:00 PM) to prevent timezone shifting
        lease_dict["commencement_date"] = parse_date_midday(lease_data.commencement_date)
        lease_dict["termination_date"] = parse_date_midday(lease_data.termination_date)
        lease_dict["lease_date"] = parse_date_midday(lease_data.lease_date) if lease_data.lease_date else None
        lease_dict["signed_date"] = None
        
        # Append to Iceberg leases table
        df = pd.DataFrame([lease_dict])
        
        # Ensure column order matches the Iceberg table schema
        # Read the table to get the correct column order
        existing_df = read_table(NAMESPACE, LEASES_TABLE)
        if len(existing_df) > 0:
            # Reorder columns to match existing table
            df = df.reindex(columns=existing_df.columns, fill_value=None)
        
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
        property_summary = _get_property_summary(str(lease_data.property_id), str(lease_data.unit_id) if lease_data.unit_id else None)
        
        # Build response
        response_dict = lease_dict.copy()
        response_dict["id"] = UUID(lease_id)
        response_dict["user_id"] = UUID(user_id)
        response_dict["property_id"] = UUID(str(lease_data.property_id))
        response_dict["unit_id"] = UUID(str(lease_data.unit_id)) if lease_data.unit_id else None
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        response_dict["moveout_costs"] = lease_data.moveout_costs or _deserialize_moveout_costs(lease_dict["moveout_costs"])
        response_dict["pets"] = lease_data.pets or _deserialize_pets(lease_dict.get("pets"))
        response_dict["pdf_url"] = None
        response_dict["latex_url"] = None
        # Convert midday timestamps to dates for Pydantic response
        response_dict["commencement_date"] = pd.Timestamp(lease_dict["commencement_date"]).date()
        response_dict["termination_date"] = pd.Timestamp(lease_dict["termination_date"]).date()
        response_dict["lease_date"] = pd.Timestamp(lease_dict["lease_date"]).date() if lease_dict.get("lease_date") and pd.notna(lease_dict.get("lease_date")) else None
        response_dict["signed_date"] = None
        response_dict["created_at"] = now.to_pydatetime()
        response_dict["updated_at"] = now.to_pydatetime()
        
        return LeaseResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating lease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating lease: {str(e)}")


@router.put("/{lease_id}", response_model=LeaseResponse)
async def update_lease(
    lease_id: UUID,
    lease_data: LeaseUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing lease"""
    try:
        user_id = current_user["sub"]
        now = pd.Timestamp.now()
        
        # Get existing lease
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_rows = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_rows) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version (highest updated_at) for append-only pattern
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        existing_lease = lease_rows.iloc[0]
        
        # Check if already deleted
        if hasattr(existing_lease, 'is_active') and not existing_lease.get("is_active", True):
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Verify ownership
        if existing_lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Convert to dict and merge with existing data
        update_dict = lease_data.model_dump(exclude_unset=True, exclude={"tenants"})
        lease_dict = existing_lease.to_dict()
        
        # Update fields
        for key, value in update_dict.items():
            if value is not None:
                lease_dict[key] = value
        
        lease_dict["id"] = str(lease_id)
        lease_dict["updated_at"] = now
        lease_dict["lease_version"] = existing_lease["lease_version"] + 1
        
        # Serialize moveout_costs if provided
        if lease_data.moveout_costs is not None:
            lease_dict["moveout_costs"] = _serialize_moveout_costs(lease_data.moveout_costs)
        
        # Serialize pets if provided
        if hasattr(lease_data, 'pets') and lease_data.pets is not None:
            lease_dict["pets"] = _serialize_pets([p.model_dump() if hasattr(p, 'model_dump') else p for p in lease_data.pets])
        
        # Convert dates if provided using Midday Strategy
        if hasattr(lease_data, 'commencement_date') and lease_data.commencement_date:
            lease_dict["commencement_date"] = parse_date_midday(lease_data.commencement_date)
        if hasattr(lease_data, 'termination_date') and lease_data.termination_date:
            lease_dict["termination_date"] = parse_date_midday(lease_data.termination_date)
        if hasattr(lease_data, 'lease_date') and lease_data.lease_date:
            lease_dict["lease_date"] = parse_date_midday(lease_data.lease_date)
        
        # TRUE UPSERT: Delete all old rows for this lease ID, then append the new one
        # This prevents data duplication from the old append-only pattern
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import get_catalog
        
        catalog = get_catalog()
        table = catalog.load_table((*NAMESPACE, LEASES_TABLE))
        schema_columns = [field.name for field in table.schema().fields]
        
        # Delete ALL existing rows for this lease ID
        table.delete(EqualTo("id", str(lease_id)))
        logger.info(f"Deleted old lease rows for ID {lease_id} before upsert")
        
        # Ensure the new record has is_active = True
        lease_dict["is_active"] = True
        
        # Append updated lease
        df = pd.DataFrame([lease_dict])
        
        # Ensure column order matches the Iceberg table schema
        df = df.reindex(columns=schema_columns, fill_value=None)
        
        append_data(NAMESPACE, LEASES_TABLE, df)
        logger.info(f"Appended updated lease {lease_id} (version {lease_dict['lease_version']})")
        
        # Update tenants if provided
        tenant_responses = []
        if hasattr(lease_data, 'tenants') and lease_data.tenants is not None:
            # TRUE UPSERT for tenants: Delete all old tenants for this lease, then add new ones
            tenants_table = catalog.load_table((*NAMESPACE, TENANTS_TABLE))
            tenants_table.delete(EqualTo("lease_id", str(lease_id)))
            logger.info(f"Deleted old tenants for lease {lease_id} before upsert")
            
            # Create new tenant records
            for idx, tenant in enumerate(lease_data.tenants):
                tenant_id = str(uuid.uuid4())
                tenant_dict = {
                    "id": tenant_id,
                    "lease_id": str(lease_id),
                    "tenant_order": idx + 1,
                    "first_name": tenant.first_name,
                    "last_name": tenant.last_name,
                    "email": tenant.email,
                    "phone": tenant.phone,
                    "signed_date": None,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
                
                tenant_df = pd.DataFrame([tenant_dict])
                append_data(NAMESPACE, TENANTS_TABLE, tenant_df)
                
                tenant_responses.append(TenantResponse(
                    id=UUID(tenant_id),
                    lease_id=lease_id,
                    tenant_order=idx + 1,
                    first_name=tenant.first_name,
                    last_name=tenant.last_name,
                    email=tenant.email,
                    phone=tenant.phone,
                    signed_date=None,
                    created_at=now.to_pydatetime(),
                    updated_at=now.to_pydatetime()
                ))
        else:
            # Get existing tenants
            tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
            lease_tenants = tenants_df[(tenants_df["lease_id"] == str(lease_id)) & (tenants_df.get("is_active", True) == True)]
            for _, tenant in lease_tenants.iterrows():
                tenant_responses.append(TenantResponse(
                    id=UUID(tenant["id"]),
                    lease_id=lease_id,
                    tenant_order=tenant["tenant_order"],
                    first_name=tenant["first_name"],
                    last_name=tenant["last_name"],
                    email=tenant.get("email"),
                    phone=tenant.get("phone"),
                    signed_date=tenant.get("signed_date"),
                    created_at=pd.Timestamp(tenant["created_at"]).to_pydatetime(),
                    updated_at=pd.Timestamp(tenant["updated_at"]).to_pydatetime()
                ))
        
        # Get property summary
        property_summary = _get_property_summary(lease_dict["property_id"], lease_dict.get("unit_id"))
        
        # Build response
        response_dict = lease_dict.copy()
        
        # Replace NaN values with None for numeric fields before Pydantic validation
        for key, value in response_dict.items():
            if pd.isna(value):
                response_dict[key] = None
        
        response_dict["id"] = lease_id
        response_dict["user_id"] = UUID(user_id)
        response_dict["property_id"] = UUID(lease_dict["property_id"])
        response_dict["unit_id"] = UUID(lease_dict["unit_id"]) if lease_dict.get("unit_id") else None
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        response_dict["moveout_costs"] = lease_data.moveout_costs if lease_data.moveout_costs is not None else _deserialize_moveout_costs(lease_dict["moveout_costs"])
        response_dict["pets"] = lease_data.pets if hasattr(lease_data, 'pets') and lease_data.pets is not None else _deserialize_pets(lease_dict.get("pets"))
        
        # Convert Timestamp dates to date objects for Pydantic
        for date_field in ["commencement_date", "termination_date", "lease_date"]:
            if date_field in response_dict and response_dict[date_field] is not None:
                if isinstance(response_dict[date_field], pd.Timestamp):
                    response_dict[date_field] = response_dict[date_field].date()
        
        # Get PDF URL if exists
        if lease_dict.get("generated_pdf_document_id"):
            response_dict["pdf_url"] = adls_service.get_blob_download_url(lease_dict["generated_pdf_document_id"])
            latex_blob = lease_dict["generated_pdf_document_id"].replace('.pdf', '.tex')
            if adls_service.blob_exists(latex_blob):
                response_dict["latex_url"] = adls_service.get_blob_download_url(latex_blob)
        else:
            response_dict["pdf_url"] = None
            response_dict["latex_url"] = None
        
        return LeaseResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lease: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating lease: {str(e)}")


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
        
        # Get user's properties first (leases are filtered by property ownership)
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        user_property_ids = properties_df[properties_df["user_id"] == user_id]["id"].tolist()
        
        if not user_property_ids:
            return {"leases": [], "total": 0}
        
        # Read leases and filter by user's properties
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        leases_df = leases_df[leases_df["property_id"].isin(user_property_ids)]
        
        # For Iceberg append-only pattern: get only the latest version of each lease
        # Sort by updated_at descending and drop duplicates keeping first (most recent)
        if len(leases_df) > 0:
            leases_df = leases_df.sort_values("updated_at", ascending=False)
            leases_df = leases_df.drop_duplicates(subset=["id"], keep="first")
        
        # ALWAYS filter for active leases (is_active=True) to handle soft deletes
        # This must come AFTER deduplication to get the latest version's is_active status
        if "is_active" in leases_df.columns:
            leases_df = leases_df[leases_df["is_active"].fillna(True) == True]
        
        if property_id:
            leases_df = leases_df[leases_df["property_id"] == str(property_id)]
        
        if status:
            leases_df = leases_df[leases_df["status"] == status]
        
        if state:
            leases_df = leases_df[leases_df["state"] == state]
        
        # Read tenants
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        # Also filter tenants for active only
        if "is_active" in tenants_df.columns:
            tenants_df = tenants_df[tenants_df["is_active"].fillna(True) == True]
        
        # Build response
        lease_items = []
        for _, lease in leases_df.iterrows():
            try:
                # Get property summary
                property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"))
                
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
                    property_id=UUID(lease["property_id"]),
                    unit_id=UUID(lease["unit_id"]) if lease.get("unit_id") else None,
                    lease_number=int(lease.get("lease_number", 0)),
                    is_official=bool(lease.get("is_official", False)),
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
        lease_rows = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_rows) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version (highest updated_at) for append-only pattern
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        lease = lease_rows.iloc[0]
        
        # Check if lease is active - handle pandas Series properly
        if hasattr(lease, 'is_active') and not lease.get("is_active", True):
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Verify ownership
        if lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this lease")
        
        # Get property summary
        property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"))
        
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
        
        # Replace NaN values with None for numeric fields
        for key, value in response_dict.items():
            if pd.isna(value):
                response_dict[key] = None
        
        response_dict["id"] = UUID(lease["id"])
        response_dict["user_id"] = UUID(lease["user_id"])
        response_dict["property_id"] = UUID(lease["property_id"])
        response_dict["unit_id"] = UUID(lease["unit_id"]) if lease.get("unit_id") else None
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        response_dict["moveout_costs"] = _deserialize_moveout_costs(lease.get("moveout_costs", "[]"))
        response_dict["pets"] = _deserialize_pets(lease.get("pets"))
        response_dict["pdf_url"] = pdf_url
        response_dict["latex_url"] = latex_url
        response_dict["commencement_date"] = pd.Timestamp(lease["commencement_date"]).date()
        response_dict["termination_date"] = pd.Timestamp(lease["termination_date"]).date()
        response_dict["lease_date"] = pd.Timestamp(lease["lease_date"]).date() if lease.get("lease_date") and pd.notna(lease.get("lease_date")) else None
        response_dict["signed_date"] = pd.Timestamp(lease["signed_date"]).date() if lease.get("signed_date") and pd.notna(lease.get("signed_date")) else None
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
        lease_rows = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_rows) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version (highest updated_at) for append-only pattern
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        lease = lease_rows.iloc[0]
        
        # Check if lease is active - handle pandas Series properly
        if hasattr(lease, 'is_active') and not lease.get("is_active", True):
            raise HTTPException(status_code=404, detail="Lease not found")
        
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
        property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"))
        
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
        
        # Generate holding fee addendum if enabled
        holding_fee_pdf_url = None
        holding_fee_latex_url = None
        holding_fee_pdf_blob_name = None
        holding_fee_latex_blob_name = None
        
        if lease_dict.get("include_holding_fee_addendum"):
            holding_fee_pdf_bytes, holding_fee_pdf_blob_name, holding_fee_latex_blob_name = generator.generate_holding_fee_addendum_pdf(
                lease_data=lease_dict,
                tenants=tenants,
                property_data=property_summary,
                user_id=user_id
            )
            holding_fee_pdf_url = adls_service.get_blob_download_url(holding_fee_pdf_blob_name)
            holding_fee_latex_url = adls_service.get_blob_download_url(holding_fee_latex_blob_name)
        
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
            status="pending_signature",
            holding_fee_pdf_url=holding_fee_pdf_url,
            holding_fee_latex_url=holding_fee_latex_url,
            holding_fee_pdf_blob_name=holding_fee_pdf_blob_name,
            holding_fee_latex_blob_name=holding_fee_latex_blob_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.delete("/{lease_id}/pdf", status_code=204)
async def delete_lease_pdf(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete generated PDF and LaTeX files for a lease"""
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
        
        # Get PDF blob name
        pdf_blob_name = lease.get("generated_pdf_document_id")
        if not pdf_blob_name:
            raise HTTPException(status_code=404, detail="No PDF found for this lease")
        
        # Delete PDF from ADLS
        try:
            adls_service.delete_blob(pdf_blob_name)
            logger.info(f"Deleted PDF: {pdf_blob_name}")
        except Exception as e:
            logger.warning(f"Failed to delete PDF blob: {e}")
        
        # Delete LaTeX source from ADLS
        latex_blob_name = pdf_blob_name.replace('.pdf', '.tex')
        try:
            adls_service.delete_blob(latex_blob_name)
            logger.info(f"Deleted LaTeX: {latex_blob_name}")
        except Exception as e:
            logger.warning(f"Failed to delete LaTeX blob: {e}")
        
        # Update lease record to clear PDF reference using delete + append pattern
        from pyiceberg.expressions import EqualTo
        
        table = load_table(NAMESPACE, LEASES_TABLE)
        table.delete(EqualTo("id", str(lease_id)))
        
        update_dict = lease.to_dict()
        update_dict["generated_pdf_document_id"] = None
        update_dict["status"] = "draft"  # Reset to draft
        update_dict["updated_at"] = pd.Timestamp.now()
        
        df = pd.DataFrame([update_dict])
        append_data(NAMESPACE, LEASES_TABLE, df)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lease PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting lease PDF: {str(e)}")


@router.delete("/{lease_id}", status_code=204)
async def delete_lease(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Hard delete a lease (only if draft)"""
    try:
        user_id = current_user["sub"]
        
        # Get lease to verify it exists and check permissions
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_rows = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_rows) == 0:
            logger.warning(f"Delete attempt: Lease {lease_id} not found in table")
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version to check permissions and status
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        lease = lease_rows.iloc[0]
        
        # Check if already deleted
        is_active = lease.get("is_active", True)
        if not is_active:
            logger.warning(f"Delete attempt: Lease {lease_id} already deleted")
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Verify ownership
        if lease["user_id"] != user_id:
            logger.warning(f"Delete attempt: Lease {lease_id} unauthorized for user {user_id}")
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Can only delete drafts
        if lease["status"] != "draft":
            logger.warning(f"Delete attempt: Lease {lease_id} status is {lease['status']}, not draft")
            raise HTTPException(
                status_code=400,
                detail="Can only delete leases in draft status"
            )
        
        # HARD DELETE: Remove all rows for this lease ID from Iceberg
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import get_catalog
        
        catalog = get_catalog()
        table = catalog.load_table((*NAMESPACE, LEASES_TABLE))
        table.delete(EqualTo("id", str(lease_id)))
        logger.info(f"Hard deleted all rows for lease {lease_id}")
        
        # Also delete associated tenants
        try:
            tenants_table = catalog.load_table((*NAMESPACE, TENANTS_TABLE))
            tenants_table.delete(EqualTo("lease_id", str(lease_id)))
            logger.info(f"Hard deleted all tenants for lease {lease_id}")
        except Exception as e:
            logger.warning(f"Failed to delete tenants for lease {lease_id}: {e}")
        
        logger.info(f"Successfully hard-deleted lease {lease_id}")
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

