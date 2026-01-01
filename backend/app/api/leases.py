"""API routes for lease management"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from typing import List, Optional, Union
from uuid import UUID
import uuid
import io
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
from app.core.iceberg import read_table, append_data, upsert_data, table_exists, load_table, get_catalog
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



def _prepare_lease_for_iceberg(lease_dict: dict, table_schema) -> dict:
    """
    Prepare lease dict for Iceberg by converting all values to proper types.
    This is the SINGLE place where all data conversions happen uniformly.
    
    Args:
        lease_dict: Raw dictionary with mixed types
        table_schema: PyArrow schema from the Iceberg table
        
    Returns:
        Dictionary with properly typed values ready for DataFrame creation
    """
    import json
    from datetime import date as date_type, datetime as datetime_type
    
    prepared = {}
    
    for field in table_schema:
        col_name = field.name
        if col_name not in lease_dict:
            continue
            
        value = lease_dict[col_name]
        field_type = field.type
        
        # Handle None/NaN uniformly
        if value is None or (isinstance(value, float) and pd.isna(value)):
            prepared[col_name] = None
            continue
        
        # Date fields (date32) - convert timestamps to date objects
        if pa.types.is_date(field_type):
            if isinstance(value, (datetime_type, pd.Timestamp)):
                prepared[col_name] = value.date()
            elif isinstance(value, date_type):
                prepared[col_name] = value
            elif isinstance(value, str):
                prepared[col_name] = datetime_type.fromisoformat(value).date()
            else:
                prepared[col_name] = None
                
        # Timestamp fields (timestamp[us]) - ensure datetime objects
        elif pa.types.is_timestamp(field_type):
            if isinstance(value, pd.Timestamp):
                prepared[col_name] = value.to_pydatetime()
            elif isinstance(value, datetime_type):
                prepared[col_name] = value
            elif isinstance(value, str):
                prepared[col_name] = pd.to_datetime(value).to_pydatetime()
            else:
                prepared[col_name] = value
                
        # String fields (utf8/large_utf8) - handle lists/dicts by JSON encoding
        elif pa.types.is_string(field_type) or pa.types.is_large_string(field_type):
            if isinstance(value, (list, dict)):
                # JSON-encode lists/dicts for string fields
                prepared[col_name] = json.dumps(value) if value else None
            elif isinstance(value, str):
                prepared[col_name] = value
            else:
                prepared[col_name] = str(value) if value is not None else None
                
        # Decimal fields - ensure Decimal type
        elif pa.types.is_decimal(field_type):
            if value is not None:
                prepared[col_name] = Decimal(str(value))
            else:
                prepared[col_name] = None
                
        # Integer fields
        elif pa.types.is_integer(field_type):
            if value is not None:
                prepared[col_name] = int(value)
            else:
                prepared[col_name] = None
                
        # Boolean fields
        elif pa.types.is_boolean(field_type):
            prepared[col_name] = bool(value) if value is not None else None
            
        # Everything else - pass through
        else:
            prepared[col_name] = value
    
    return prepared


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


def _get_property_summary(property_id: str, unit_id: Optional[str] = None, properties_df: Optional[pd.DataFrame] = None) -> dict:
    """Get property summary for response, including unit info if provided
    
    Args:
        property_id: The property ID to get summary for
        unit_id: Optional unit ID for multi-unit properties
        properties_df: Optional pre-loaded properties DataFrame to avoid re-reading the table
    """
    import time
    summary_start = time.time()
    try:
        # Use provided DataFrame or read it if not provided
        if properties_df is None:
            prop_read_start = time.time()
            properties_df = read_table(NAMESPACE, "properties")
            logger.info(f"⏱️ [PERF] _get_property_summary read_table(properties) took {time.time() - prop_read_start:.2f}s")
        
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
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] create_lease started")
    
    try:
        user_id = current_user["sub"]
        lease_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Verify property ownership
        verify_start = time.time()
        _verify_property_ownership(str(lease_data.property_id), user_id)
        logger.info(f"⏱️ [PERF] _verify_property_ownership took {time.time() - verify_start:.2f}s")
        
        # Generate lease_number: Auto-incrementing per user (1, 2, 3, ...)
        # PRIMARY KEY: lease_number is unique per user and used for identification
        # With <10 rows per user, this is fast
        lease_number_start = time.time()
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import read_table_filtered
        
        # Read only this user's leases to get max lease_number
        user_leases_df = read_table_filtered(
            NAMESPACE, 
            LEASES_TABLE, 
            EqualTo("user_id", user_id)
        )
        
        # Filter to active leases and get latest version per lease
        if len(user_leases_df) > 0:
            user_leases_df = user_leases_df[user_leases_df["is_active"] == True]
            user_leases_df = user_leases_df.sort_values("updated_at", ascending=False)
            user_leases_df = user_leases_df.drop_duplicates(subset=["id"], keep="first")
            
            # Get max lease_number for this user
            if "lease_number" in user_leases_df.columns and len(user_leases_df) > 0:
                max_lease_number = user_leases_df["lease_number"].max()
                # Handle case where lease_number might be 0 or NaN
                if pd.isna(max_lease_number) or max_lease_number == 0:
                    lease_number = 1
                else:
                    lease_number = int(max_lease_number) + 1
            else:
                lease_number = 1
        else:
            lease_number = 1
        
        logger.info(f"⏱️ [PERF] Lease number generation (auto-increment) took {time.time() - lease_number_start:.2f}s")
        logger.info(f"📋 Generated lease_number: {lease_number} for user {user_id}")
        
        # Convert to dict and apply state defaults
        lease_dict = lease_data.model_dump(exclude={"tenants"})
        lease_dict["id"] = lease_id
        lease_dict["user_id"] = user_id
        lease_dict["lease_number"] = lease_number
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
        # Handle signed_date - it's a date field, not a timestamp
        # Check if signed_date exists in the request (it might be in lease_data as an attribute)
        signed_date_value = getattr(lease_data, 'signed_date', None)
        if signed_date_value:
            # Parse as date (not timestamp) - use date part only
            if isinstance(signed_date_value, str):
                signed_date_value = datetime.strptime(signed_date_value, "%Y-%m-%d").date()
            elif isinstance(signed_date_value, (datetime, pd.Timestamp)):
                signed_date_value = signed_date_value.date() if hasattr(signed_date_value, 'date') else signed_date_value
            lease_dict["signed_date"] = signed_date_value
        else:
            lease_dict["signed_date"] = None
        
        # Append to Iceberg leases table
        # CRITICAL: Get table schema FIRST, then prepare data according to schema
        table = load_table(NAMESPACE, LEASES_TABLE)
        table_schema = table.schema().as_arrow()
        
        # Use the unified preparation function to convert ALL data properly
        prepared_lease = _prepare_lease_for_iceberg(lease_dict, table_schema)
        
        # Create PyArrow table DIRECTLY from prepared data with explicit schema
        # Build a single record (dictionary) with all fields in schema order
        record = {}
        for field in table_schema:
            col_name = field.name
            value = prepared_lease.get(col_name)
            field_type = field.type
            
            # CRITICAL: For date fields, ensure date objects (not datetime/timestamp)
            if pa.types.is_date(field_type):
                if value is None:
                    record[col_name] = None
                elif isinstance(value, (datetime, pd.Timestamp)):
                    record[col_name] = value.date()
                elif isinstance(value, date):
                    record[col_name] = value
                else:
                    record[col_name] = None
            # For timestamp fields, ensure datetime objects
            elif pa.types.is_timestamp(field_type):
                if value is None:
                    record[col_name] = None
                elif isinstance(value, pd.Timestamp):
                    record[col_name] = value.to_pydatetime()
                elif isinstance(value, datetime):
                    record[col_name] = value
                else:
                    record[col_name] = value
            else:
                record[col_name] = value
        
        # Create table from single record with explicit schema - this ensures exact types
        arrow_table = pa.Table.from_pylist([record], schema=table_schema)
        
        upsert_start = time.time()
        # Pass PyArrow table directly to avoid pandas type inference issues
        table.upsert(arrow_table, join_cols=["id"])
        logger.info(f"⏱️ [PERF] upsert_data(leases) took {time.time() - upsert_start:.2f}s")
        
        # Create tenants
        tenants_start = time.time()
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
        logger.info(f"⏱️ [PERF] Creating {len(lease_data.tenants)} tenants took {time.time() - tenants_start:.2f}s")
        
        # Get property summary
        property_summary_start = time.time()
        property_summary = _get_property_summary(str(lease_data.property_id), str(lease_data.unit_id) if lease_data.unit_id else None)
        logger.info(f"⏱️ [PERF] _get_property_summary took {time.time() - property_summary_start:.2f}s")
        
        # Build response
        response_start = time.time()
        response_dict = lease_dict.copy()
        response_dict["id"] = UUID(lease_id)
        response_dict["user_id"] = UUID(user_id)
        response_dict["property_id"] = UUID(str(lease_data.property_id))
        response_dict["unit_id"] = UUID(str(lease_data.unit_id)) if lease_data.unit_id else None
        # lease_number is already set in lease_dict during creation
        response_dict["lease_number"] = int(lease_dict.get("lease_number", 0))
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
        logger.info(f"⏱️ [PERF] Building response took {time.time() - response_start:.2f}s")
        
        total_time = time.time() - endpoint_start
        logger.info(f"⏱️ [PERF] create_lease completed in {total_time:.2f}s")
        
        return LeaseResponse(**response_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - endpoint_start
        logger.error(f"⏱️ [PERF] create_lease failed after {total_time:.2f}s: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating lease: {str(e)}")


@router.put("/{lease_id}", response_model=LeaseResponse)
async def update_lease(
    lease_id: UUID,
    lease_data: LeaseUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing lease"""
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] update_lease started")
    
    try:
        user_id = current_user["sub"]
        now = pd.Timestamp.now()
        
        # OPTIMIZATION: Use predicate pushdown to find existing lease instead of reading all leases
        # This is much faster than reading the entire table
        read_start = time.time()
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import read_table_filtered
        
        try:
            leases_df = read_table_filtered(NAMESPACE, LEASES_TABLE, EqualTo("id", str(lease_id)))
            logger.info(f"⏱️ [PERF] read_table_filtered(leases) for update took {time.time() - read_start:.2f}s")
        except Exception as e:
            # Fallback to full read if filtered read fails
            logger.warning(f"Filtered read failed, falling back to full read: {e}")
            leases_df = read_table(NAMESPACE, LEASES_TABLE)
            leases_df = leases_df[leases_df["id"] == str(lease_id)]
            logger.info(f"⏱️ [PERF] read_table(leases) for update (fallback) took {time.time() - read_start:.2f}s")
        
        if len(leases_df) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version (highest updated_at) for append-only pattern
        leases_df = leases_df.sort_values("updated_at", ascending=False)
        existing_lease = leases_df.iloc[0]
        
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
            # Explicitly handle 0, False, and empty string as valid values (not None)
            if value is not None or key in ["garage_back_door_keys", "has_garage_door_opener", "garage_door_opener_fee"]:
                # For these specific fields, allow 0/False to be set explicitly
                if key in ["garage_back_door_keys", "has_garage_door_opener", "garage_door_opener_fee"]:
                    lease_dict[key] = value
                elif value is not None:
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
        
        # OPTIMIZATION: Use delete + append instead of upsert (upsert is slow - 60+ seconds!)
        # Delete is fast with predicate pushdown, append is fast
        # Ensure the new record has is_active = True
        lease_dict["is_active"] = True
        
        # Get schema columns for proper ordering
        schema_start = time.time()
        table = load_table(NAMESPACE, LEASES_TABLE)
        schema_columns = [field.name for field in table.schema().fields]
        logger.info(f"⏱️ [PERF] Getting schema columns for update took {time.time() - schema_start:.2f}s")
        
        # Delete existing row(s) for this lease ID (fast with predicate pushdown)
        delete_start = time.time()
        from pyiceberg.expressions import EqualTo
        table.delete(EqualTo("id", str(lease_id)))
        logger.info(f"⏱️ [PERF] table.delete() for update took {time.time() - delete_start:.2f}s")
        
        # Append updated lease (fast)
        append_start = time.time()
        df = pd.DataFrame([lease_dict])
        
        # Debug: Log garage door fields before reindex
        logger.info(f"🔍 [DEBUG] Before reindex - garage_back_door_keys: {lease_dict.get('garage_back_door_keys')}, has_garage_door_opener: {lease_dict.get('has_garage_door_opener')}, garage_door_opener_fee: {lease_dict.get('garage_door_opener_fee')}")
        
        # Reindex but preserve explicit values (don't overwrite with None if they exist)
        df = df.reindex(columns=schema_columns, fill_value=None)
        
        # Explicitly set garage door fields if they were in the update
        if "garage_back_door_keys" in update_dict:
            df["garage_back_door_keys"] = update_dict["garage_back_door_keys"]
        if "has_garage_door_opener" in update_dict:
            df["has_garage_door_opener"] = update_dict["has_garage_door_opener"]
        if "garage_door_opener_fee" in update_dict:
            df["garage_door_opener_fee"] = update_dict["garage_door_opener_fee"]
        
        # Debug: Log after explicit setting
        logger.info(f"🔍 [DEBUG] After explicit set - garage_back_door_keys: {df['garage_back_door_keys'].iloc[0] if 'garage_back_door_keys' in df.columns else 'MISSING'}, has_garage_door_opener: {df['has_garage_door_opener'].iloc[0] if 'has_garage_door_opener' in df.columns else 'MISSING'}, garage_door_opener_fee: {df['garage_door_opener_fee'].iloc[0] if 'garage_door_opener_fee' in df.columns else 'MISSING'}")
        append_data(NAMESPACE, LEASES_TABLE, df)
        logger.info(f"⏱️ [PERF] append_data(leases) for update took {time.time() - append_start:.2f}s")
        logger.info(f"Updated lease {lease_id} (version {lease_dict['lease_version']}) via delete+append")
        
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
            tenants_read_start = time.time()
            tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
            lease_tenants = tenants_df[(tenants_df["lease_id"] == str(lease_id)) & (tenants_df.get("is_active", True) == True)]
            logger.info(f"⏱️ [PERF] read_table(tenants) for existing tenants took {time.time() - tenants_read_start:.2f}s")
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
        property_summary_start = time.time()
        property_summary = _get_property_summary(lease_dict["property_id"], lease_dict.get("unit_id"))
        logger.info(f"⏱️ [PERF] _get_property_summary for update took {time.time() - property_summary_start:.2f}s")
        
        # Build response
        response_start = time.time()
        response_dict = lease_dict.copy()
        
        # Replace NaN values with None for numeric fields before Pydantic validation
        for key, value in response_dict.items():
            if pd.isna(value):
                response_dict[key] = None
        
        response_dict["id"] = lease_id
        response_dict["user_id"] = UUID(user_id)
        response_dict["property_id"] = UUID(lease_dict["property_id"])
        response_dict["unit_id"] = UUID(lease_dict["unit_id"]) if lease_dict.get("unit_id") else None
        # Handle lease_number - default to 0 if missing (for existing leases created before this field was added)
        response_dict["lease_number"] = int(lease_dict.get("lease_number", 0)) if lease_dict.get("lease_number") is not None and not pd.isna(lease_dict.get("lease_number")) else 0
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
    import time
    endpoint_start = time.time()
    logger.info(f"⏱️ [PERF] list_leases started")
    
    try:
        user_id = current_user["sub"]
        
        # Get user's properties first (leases are filtered by property ownership)
        properties_start = time.time()
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        user_property_ids = properties_df[properties_df["user_id"] == user_id]["id"].tolist()
        logger.info(f"⏱️ [PERF] read_table(properties) took {time.time() - properties_start:.2f}s")
        
        if not user_property_ids:
            return {"leases": [], "total": 0}
        
        # Read leases and filter by user's properties
        # Note: Predicate pushdown was tested but didn't improve performance (5.08s vs 4.88s)
        # Reverting to read_table() + pandas filtering for simplicity
        leases_start = time.time()
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        logger.info(f"⏱️ [PERF] read_table(leases) took {time.time() - leases_start:.2f}s")
        
        filter_start = time.time()
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
        logger.info(f"⏱️ [PERF] Filtering leases took {time.time() - filter_start:.2f}s")
        
        # Read tenants
        tenants_start = time.time()
        tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
        logger.info(f"⏱️ [PERF] read_table(tenants) took {time.time() - tenants_start:.2f}s")
        # Also filter tenants for active only
        if "is_active" in tenants_df.columns:
            tenants_df = tenants_df[tenants_df["is_active"].fillna(True) == True]
        
        # Build response
        build_start = time.time()
        lease_items = []
        for _, lease in leases_df.iterrows():
            try:
                # Get property summary (pass the already-loaded properties_df to avoid re-reading)
                property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"), properties_df)
                
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
        logger.info(f"⏱️ [PERF] Building lease items took {time.time() - build_start:.2f}s")
        
        total_time = time.time() - endpoint_start
        logger.info(f"⏱️ [PERF] list_leases completed in {total_time:.2f}s")
        
        return LeaseListResponse(leases=lease_items, total=len(lease_items))
        
    except Exception as e:
        total_time = time.time() - endpoint_start
        logger.error(f"⏱️ [PERF] list_leases failed after {total_time:.2f}s: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing leases: {str(e)}")


@router.get("/{lease_id}", response_model=LeaseResponse)
async def get_lease(
    lease_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed lease information"""
    try:
        user_id = current_user["sub"]
        
        # OPTIMIZATION: Use predicate pushdown to filter by lease_id at storage layer
        # This is much faster than reading all leases and filtering in memory
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import read_table_filtered
        
        import time
        read_start = time.time()
        try:
            leases_df = read_table_filtered(NAMESPACE, LEASES_TABLE, EqualTo("id", str(lease_id)))
            logger.info(f"⏱️ [PERF] read_table_filtered(leases) for get_lease took {time.time() - read_start:.2f}s")
        except Exception as e:
            # Fallback to full read if filtered read fails
            logger.warning(f"Filtered read failed, falling back to full read: {e}")
            leases_df = read_table(NAMESPACE, LEASES_TABLE)
            leases_df = leases_df[leases_df["id"] == str(lease_id)]
            logger.info(f"⏱️ [PERF] read_table(leases) for get_lease (fallback) took {time.time() - read_start:.2f}s")
        
        if len(leases_df) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version (highest updated_at) for append-only pattern
        leases_df = leases_df.sort_values("updated_at", ascending=False)
        lease = leases_df.iloc[0]
        
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
        # Handle lease_number - default to 0 if missing (for existing leases created before this field was added)
        response_dict["lease_number"] = int(lease.get("lease_number", 0)) if lease.get("lease_number") is not None and not pd.isna(lease.get("lease_number")) else 0
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
        
        # Convert pandas Series values to proper Python types
        # Handle NaN values and ensure proper type conversion
        for key, value in lease_dict.items():
            if pd.isna(value):
                lease_dict[key] = None
            elif isinstance(value, (pd.Timestamp, pd.DatetimeTZDtype)):
                lease_dict[key] = value.to_pydatetime() if hasattr(value, 'to_pydatetime') else None
            elif isinstance(value, pd.Series):
                lease_dict[key] = value.iloc[0] if len(value) > 0 else None
        
        # Debug: Log the garage door fields before passing to generator
        logger.info(f"🔍 [DEBUG] Lease data before PDF generation:")
        logger.info(f"  garage_back_door_keys: {lease_dict.get('garage_back_door_keys')} (type: {type(lease_dict.get('garage_back_door_keys'))})")
        logger.info(f"  has_garage_door_opener: {lease_dict.get('has_garage_door_opener')} (type: {type(lease_dict.get('has_garage_door_opener'))})")
        logger.info(f"  garage_door_opener_fee: {lease_dict.get('garage_door_opener_fee')} (type: {type(lease_dict.get('garage_door_opener_fee'))})")
        
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


@router.get("/{lease_id}/pdf/proxy")
async def proxy_lease_pdf_download(
    lease_id: UUID,
    document_type: str = Query("lease", description="Type of document: 'lease' or 'holding_fee'"),
    current_user: dict = Depends(get_current_user)
):
    """Proxy download for lease PDF or holding fee addendum (forces actual download instead of opening in browser - IE compatible)"""
    try:
        user_id = current_user["sub"]
        
        # Get lease
        leases_df = read_table(NAMESPACE, LEASES_TABLE)
        lease_rows = leases_df[leases_df["id"] == str(lease_id)]
        
        if len(lease_rows) == 0:
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Get the latest version
        lease_rows = lease_rows.sort_values("updated_at", ascending=False)
        lease = lease_rows.iloc[0]
        
        # Verify ownership
        if lease["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Determine which PDF to download
        if document_type == "holding_fee":
            # For holding fee, we need to get it from the generate response
            # Since it's not stored in the lease record, we'll need to reconstruct the blob name
            # Holding fee PDFs are stored in the same location as lease PDFs with a different name
            lease_pdf_blob = lease.get("generated_pdf_document_id")
            if not lease_pdf_blob:
                raise HTTPException(status_code=404, detail="Lease PDF not found - generate lease PDF first")
            
            # Holding fee PDF follows naming pattern: replace lease PDF name with holding fee name
            # Format: leases/generated/{user_id}/{lease_id}_holding_fee_addendum.pdf
            pdf_blob = lease_pdf_blob.replace('.pdf', '_holding_fee_addendum.pdf')
            download_filename = "Holding_Fee_Addendum.pdf"
        else:
            # Default to lease PDF
            pdf_blob = lease.get("generated_pdf_document_id")
            if not pdf_blob:
                raise HTTPException(status_code=404, detail="PDF not generated for this lease")
            
            # Use lease number and property address for filename if available
            property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"))
            property_address = property_summary.get("address", "property") if property_summary else "property"
            # Sanitize filename
            safe_address = "".join(c for c in property_address if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
            lease_number = lease.get("lease_number", "")
            download_filename = f"Lease_{lease_number}_{safe_address}.pdf" if lease_number else f"Lease_{safe_address}.pdf"
        
        if not adls_service.blob_exists(pdf_blob):
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        # Download blob content
        blob_content, content_type, filename = adls_service.download_blob(pdf_blob)
        
        # Return as streaming response with Content-Disposition header to force download
        return StreamingResponse(
            io.BytesIO(blob_content),
            media_type=content_type or "application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{download_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying lease PDF download: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error downloading lease PDF: {str(e)}")


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

