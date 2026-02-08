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
    TerminateLeaseRequest, TerminateLeaseResponse, PropertySummary, MoveOutCostItem, PetInfo
)
from app.core.iceberg import read_table, append_data, upsert_data, table_exists, load_table, get_catalog
from app.core.logging import get_logger
from app.services.lease_defaults import apply_lease_defaults, get_default_moveout_costs_json
from app.services.lease_generator_service import LeaseGeneratorService
from app.services.adls_service import adls_service

NAMESPACE = ("investflow",)
LEASES_TABLE = "leases"
PROPERTIES_TABLE = "properties"

router = APIRouter(prefix="/leases", tags=["leases"])
logger = get_logger(__name__)

# Strict field order for leases table (must match Iceberg schema exactly)
# Schema changes:
# - Removed: user_id, utilities_provided_by_owner_city, pets, pets_allowed, max_children, max_pets
# - Removed: parking_spaces, parking_small_vehicles, parking_large_trucks
# - Removed: garage_outlets_prohibited, has_garage, has_attic, attic_usage, has_basement, moveout_inspection_rights
# - Removed: military_termination_days
# - Restructured: pet_fee (amount), pets (JSON string like tenants)
# - Renamed: snow_removal_responsibility -> tenant_snow_removal (boolean)
# - Renamed: lead_paint_year_built -> disclosure_lead_paint
# - Renamed: methamphetamine_disclosure -> disclosure_methamphetamine
# - Merged: owner_address + manager_address -> manager_address
# - Added: tenants (JSON column)
# EXACT field order matching actual Iceberg table schema (from inspect_table.py output)
# Verified order from table inspection:
# id, property_id, unit_id, status, state, lease_date, lease_start, lease_end, monthly_rent, rent_due_by_time,
# payment_method, prorated_first_month_rent, late_fee_day_1_10, late_fee_day_11, late_fee_day_16, late_fee_day_21,
# nsf_fee, security_deposit, holding_fee_amount, holding_fee_date, utilities_tenant, utilities_landlord,
# pet_fee, pets, garage_spaces, key_replacement_fee, shared_driveway_with, garage_door_opener_fee,
# appliances_provided, early_termination_fee_amount, moveout_costs, owner_name, manager_name, manager_address,
# generated_pdf_document_id, template_used, tenants, notes, auto_convert_month_to_month, show_prorated_rent,
# include_holding_fee_addendum, has_shared_driveway, tenant_lawn_mowing, tenant_snow_removal, tenant_lawn_care,
# has_garage_door_opener, lead_paint_disclosure, early_termination_allowed, disclosure_methamphetamine, is_active,
# lease_number, lease_version, rent_due_day, rent_due_by_day, max_occupants, max_adults, offstreet_parking_spots,
# front_door_keys, back_door_keys, garage_back_door_keys, disclosure_lead_paint, early_termination_notice_days,
# early_termination_fee_months, created_at, updated_at
LEASES_FIELD_ORDER = [
    "id", "property_id", "unit_id",
    "status", "state",
    "lease_date", "lease_start", "lease_end",
    "monthly_rent", "rent_due_by_time",
    "payment_method",
    "prorated_first_month_rent",
    "late_fee_day_1_10", "late_fee_day_11", "late_fee_day_16", "late_fee_day_21",
    "nsf_fee",
    "security_deposit",
    "holding_fee_amount", "holding_fee_date",
    "utilities_tenant", "utilities_landlord",
    "pet_fee", "pets",
    "garage_spaces",
    "key_replacement_fee",
    "shared_driveway_with",
    "garage_door_opener_fee",
    "appliances_provided",
    "early_termination_fee_amount",
    "moveout_costs",
    "owner_name", "manager_name", "manager_address",
    "generated_pdf_document_id", "template_used",
    "tenants",
    "notes",
    "auto_convert_month_to_month",
    "show_prorated_rent",
    "include_holding_fee_addendum",
    "has_shared_driveway",
    "tenant_lawn_mowing", "tenant_snow_removal", "tenant_lawn_care",
    "has_garage_door_opener",
    "lead_paint_disclosure",
    "early_termination_allowed",
    "disclosure_methamphetamine",
    "is_active",
    "lease_number", "lease_version",
    "rent_due_day", "rent_due_by_day",
    "max_occupants", "max_adults",
    "offstreet_parking_spots",
    "front_door_keys", "back_door_keys", "garage_back_door_keys",
    "disclosure_lead_paint",
    "early_termination_notice_days",
    "early_termination_fee_months",
    "created_at", "updated_at",
]


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


def _serialize_moveout_costs(moveout_costs: Optional[List]) -> Optional[str]:
    """Convert move-out costs list to JSON string for storage (like landlord_references)
    
    Handles both Pydantic MoveOutCostItem models and plain dicts.
    """
    if not moveout_costs:
        return None
    
    # Convert to list of dicts if needed
    costs_list = []
    for item in moveout_costs:
        # Handle Pydantic models
        if hasattr(item, 'model_dump'):
            item_dict = item.model_dump()
        elif hasattr(item, 'dict'):  # Pydantic v1
            item_dict = item.dict()
        elif isinstance(item, dict):
            item_dict = item
        else:
            # Fallback: try to convert to dict
            item_dict = dict(item) if hasattr(item, '__dict__') else {}
        
        # Ensure amount is a string for JSON
        if 'amount' in item_dict and not isinstance(item_dict['amount'], str):
            item_dict['amount'] = str(item_dict['amount'])
        
        costs_list.append(item_dict)
    
    return json.dumps(costs_list) if costs_list else None


def _deserialize_moveout_costs(moveout_costs_json: Optional[str]) -> List[MoveOutCostItem]:
    """Convert JSON string to move-out costs list (like landlord_references)"""
    if not moveout_costs_json:
        return []
    
    try:
        costs = json.loads(moveout_costs_json) if isinstance(moveout_costs_json, str) else moveout_costs_json
        return [MoveOutCostItem(**cost) for cost in costs]
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_pets(pets: Optional[List]) -> Optional[str]:
    """Convert pets list to JSON string for storage (like landlord_references)
    
    Handles both Pydantic PetInfo models and plain dicts.
    """
    if not pets:
        return None
    
    # Convert to list of dicts if needed
    pets_list = []
    for pet in pets:
        # Handle Pydantic models
        if hasattr(pet, 'model_dump'):
            pet_dict = pet.model_dump()
        elif hasattr(pet, 'dict'):  # Pydantic v1
            pet_dict = pet.dict()
        elif isinstance(pet, dict):
            pet_dict = pet
        else:
            # Fallback: try to convert to dict
            pet_dict = dict(pet) if hasattr(pet, '__dict__') else {}
        
        pets_list.append(pet_dict)
    
    return json.dumps(pets_list) if pets_list else None


def _deserialize_pets(pets_json: Optional[str]) -> List[dict]:
    """Convert JSON string to pets list (like landlord_references)"""
    if not pets_json:
        return []
    
    try:
        return json.loads(pets_json) if isinstance(pets_json, str) else pets_json
    except (json.JSONDecodeError, TypeError):
        return []


def _serialize_tenants(tenants: Optional[List]) -> Optional[str]:
    """Convert tenant list to JSON string for storage (like landlord_references)
    
    Handles both Pydantic TenantCreate/TenantUpdate models and plain dicts.
    Note: signed_date is not collected/stored for leases.
    """
    if not tenants:
        return None
    
    # Convert to list of dicts if needed
    tenants_list = []
    for idx, tenant in enumerate(tenants):
        # Handle Pydantic models
        if hasattr(tenant, 'model_dump'):
            tenant_dict = tenant.model_dump()
        elif hasattr(tenant, 'dict'):  # Pydantic v1
            tenant_dict = tenant.dict()
        elif isinstance(tenant, dict):
            tenant_dict = tenant.copy()
        else:
            # Fallback: try to convert to dict
            tenant_dict = dict(tenant) if hasattr(tenant, '__dict__') else {}
        
        # Remove signed_date if present (we don't collect it)
        tenant_dict.pop('signed_date', None)
        
        # Ensure tenant_order is set
        if 'tenant_order' not in tenant_dict:
            tenant_dict['tenant_order'] = idx + 1
        
        # Ensure id is a string if present
        if 'id' in tenant_dict and tenant_dict['id']:
            tenant_dict['id'] = str(tenant_dict['id'])
        elif 'id' not in tenant_dict or not tenant_dict.get('id'):
            tenant_dict['id'] = str(uuid.uuid4())
        
        tenants_list.append(tenant_dict)
    
    return json.dumps(tenants_list) if tenants_list else None


def _deserialize_tenants(tenants_json: Optional[str]) -> List[TenantResponse]:
    """Convert JSON string from leases table to TenantResponse list (like landlord_references)"""
    if not tenants_json:
        return []
    
    try:
        tenant_list = json.loads(tenants_json) if isinstance(tenants_json, str) else tenants_json
        return [
            TenantResponse(
                id=UUID(tenant.get("id", str(uuid.uuid4()))),
                lease_id=UUID("00000000-0000-0000-0000-000000000000"),  # Will be set by caller
                tenant_order=tenant.get("tenant_order", 0),
                first_name=tenant.get("first_name", ""),
                last_name=tenant.get("last_name", ""),
                email=tenant.get("email"),
                phone=tenant.get("phone"),
                signed_date=None,  # Not collected/stored for leases
                created_at=datetime.utcnow(),  # Not stored in JSON, use current time
                updated_at=datetime.utcnow(),  # Not stored in JSON, use current time
            )
            for tenant in tenant_list
        ]
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning(f"Error deserializing tenants JSON: {e}")
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
        # Since user_id is removed, we filter by property ownership instead
        lease_number_start = time.time()
        from pyiceberg.expressions import EqualTo
        from app.core.iceberg import read_table_filtered
        
        # Get user's property IDs to filter leases
        properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
        user_property_ids = properties_df[properties_df["user_id"] == user_id]["id"].tolist()
        
        # Read leases for this user's properties to get max lease_number
        if user_property_ids:
            # Filter leases by property_id (using IN predicate if possible, or read all and filter)
            leases_df = read_table(NAMESPACE, LEASES_TABLE)
            user_leases_df = leases_df[leases_df["property_id"].isin(user_property_ids)]
        else:
            user_leases_df = pd.DataFrame()
        
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
        lease_dict["lease_number"] = lease_number
        lease_dict["lease_version"] = 1
        lease_dict["created_at"] = now
        lease_dict["updated_at"] = now
        lease_dict["is_active"] = True
        lease_dict["generated_pdf_document_id"] = None
        lease_dict["template_used"] = f"{lease_data.state}_residential_v1"
        
        # Apply state-specific defaults
        lease_dict = apply_lease_defaults(lease_dict, lease_data.state)
        
        # Serialize moveout_costs as JSON (like tenants)
        if lease_data.moveout_costs:
            lease_dict["moveout_costs"] = _serialize_moveout_costs(lease_data.moveout_costs)
        else:
            lease_dict["moveout_costs"] = None
        
        # Serialize pets as JSON (like tenants)
        if lease_data.pets:
            lease_dict["pets"] = _serialize_pets(lease_data.pets)
        else:
            lease_dict["pets"] = None
        
        # Serialize tenants as JSON
        if lease_data.tenants:
            lease_dict["tenants"] = _serialize_tenants(lease_data.tenants)
        else:
            lease_dict["tenants"] = None
        
        # Convert UUIDs and dates to strings for Iceberg
        lease_dict["property_id"] = str(lease_data.property_id)
        lease_dict["unit_id"] = str(lease_data.unit_id) if lease_data.unit_id else None
        # Parse dates using Midday Strategy (12:00 PM) to prevent timezone shifting
        lease_dict["lease_start"] = parse_date_midday(lease_data.lease_start)
        lease_dict["lease_end"] = parse_date_midday(lease_data.lease_end)
        lease_dict["lease_date"] = parse_date_midday(lease_data.lease_date) if lease_data.lease_date else None
        
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
        
        # Tenants are already serialized as JSON in lease_dict["tenants"]
        # Deserialize to create tenant responses
        tenants_start = time.time()
        tenant_responses = []
        if lease_data.tenants:
            for idx, tenant in enumerate(lease_data.tenants):
                tenant_id = str(uuid.uuid4())
                tenant_responses.append(TenantResponse(
                    id=UUID(tenant_id),
                    lease_id=UUID(lease_id),
                    tenant_order=idx + 1,
                    first_name=tenant.first_name,
                    last_name=tenant.last_name,
                    email=tenant.email,
                    phone=tenant.phone,
                    signed_date=None,  # Not collected/stored for leases
                    created_at=now.to_pydatetime(),
                    updated_at=now.to_pydatetime()
                ))
        logger.info(f"⏱️ [PERF] Processing {len(lease_data.tenants)} tenants took {time.time() - tenants_start:.2f}s")
        
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
        # Deserialize moveout_costs from JSON (like tenants)
        moveout_costs_json = lease_dict.get("moveout_costs")
        response_dict["moveout_costs"] = lease_data.moveout_costs if lease_data.moveout_costs else _deserialize_moveout_costs(moveout_costs_json)
        
        # Deserialize pets from JSON (like tenants)
        pets_json = lease_dict.get("pets")
        if lease_data.pets:
            response_dict["pets"] = lease_data.pets
        else:
            # Try pets column first, then fallback to pet_description for backward compatibility
            if pets_json:
                response_dict["pets"] = _deserialize_pets(pets_json)
            elif lease_dict.get("pet_description"):
                try:
                    pet_descriptions = json.loads(lease_dict["pet_description"])
                    # Convert from old format to new format
                    response_dict["pets"] = [{"type": p.get("pet_type"), "breed": p.get("breed"), "name": p.get("pet_name"), "weight": p.get("weight"), "isEmotionalSupport": False} for p in pet_descriptions]
                except:
                    response_dict["pets"] = []
            else:
                response_dict["pets"] = []
        response_dict["pdf_url"] = None
        response_dict["latex_url"] = None
        # Convert midday timestamps to dates for Pydantic response
        response_dict["lease_start"] = pd.Timestamp(lease_dict["lease_start"]).date()
        response_dict["lease_end"] = pd.Timestamp(lease_dict["lease_end"]).date()
        response_dict["lease_date"] = pd.Timestamp(lease_dict["lease_date"]).date() if lease_dict.get("lease_date") and pd.notna(lease_dict.get("lease_date")) else None
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
        
        # Verify ownership via property
        _verify_property_ownership(existing_lease["property_id"], user_id)
        
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
        
        # Serialize moveout_costs as JSON (like tenants)
        if hasattr(lease_data, 'moveout_costs') and lease_data.moveout_costs is not None:
            lease_dict["moveout_costs"] = _serialize_moveout_costs(lease_data.moveout_costs)
        else:
            # Keep existing value if not provided
            existing_moveout_costs = existing_lease.get("moveout_costs")
            lease_dict["moveout_costs"] = existing_moveout_costs if existing_moveout_costs else None
        
        # Serialize pets as JSON (like tenants)
        if hasattr(lease_data, 'pets') and lease_data.pets is not None:
            lease_dict["pets"] = _serialize_pets(lease_data.pets)
        else:
            # Keep existing value if not provided, or migrate from pet_description
            existing_pets = existing_lease.get("pets")
            if existing_pets:
                lease_dict["pets"] = existing_pets
            elif existing_lease.get("pet_description"):
                # Migrate from old pet_description format
                try:
                    pet_descriptions = json.loads(existing_lease["pet_description"])
                    pet_list = [{"type": p.get("pet_type"), "breed": p.get("breed"), "name": p.get("pet_name"), "weight": p.get("weight"), "isEmotionalSupport": False} for p in pet_descriptions]
                    lease_dict["pets"] = _serialize_pets(pet_list)
                except:
                    lease_dict["pets"] = None
            else:
                lease_dict["pets"] = None
        
        # Convert dates if provided using Midday Strategy
        if hasattr(lease_data, 'lease_start') and lease_data.lease_start:
            lease_dict["lease_start"] = parse_date_midday(lease_data.lease_start)
        if hasattr(lease_data, 'lease_end') and lease_data.lease_end:
            lease_dict["lease_end"] = parse_date_midday(lease_data.lease_end)
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
        
        # Update tenants if provided - serialize as JSON
        tenant_responses = []
        if hasattr(lease_data, 'tenants') and lease_data.tenants is not None:
            # Serialize tenants as JSON and update in lease_dict
            lease_dict["tenants"] = _serialize_tenants(lease_data.tenants)
            
            # Create tenant responses
            for idx, tenant in enumerate(lease_data.tenants):
                tenant_id = str(uuid.uuid4())
                tenant_responses.append(TenantResponse(
                    id=UUID(tenant_id),
                    lease_id=lease_id,
                    tenant_order=idx + 1,
                    first_name=tenant.first_name,
                    last_name=tenant.last_name,
                    email=tenant.email,
                    phone=tenant.phone,
                    signed_date=None,  # Not collected/stored for leases
                    created_at=now.to_pydatetime(),
                    updated_at=now.to_pydatetime()
                ))
        else:
            # Get existing tenants from JSON column
            tenants_json = existing_lease.get("tenants")
            if tenants_json:
                tenant_responses = _deserialize_tenants(tenants_json)
                # Set lease_id on all tenant responses
                for tenant_resp in tenant_responses:
                    tenant_resp.lease_id = lease_id
            else:
                tenant_responses = []
        
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
        # Deserialize moveout_costs from JSON (like tenants)
        moveout_costs_json = lease_dict.get("moveout_costs")
        response_dict["moveout_costs"] = lease_data.moveout_costs if (hasattr(lease_data, 'moveout_costs') and lease_data.moveout_costs is not None) else _deserialize_moveout_costs(moveout_costs_json)
        
        # Deserialize pets from JSON (like tenants)
        pets_json = lease_dict.get("pets")
        if hasattr(lease_data, 'pets') and lease_data.pets is not None:
            response_dict["pets"] = lease_data.pets
        else:
            # Try pets column first, then fallback to pet_description for backward compatibility
            if pets_json:
                response_dict["pets"] = _deserialize_pets(pets_json)
            elif lease_dict.get("pet_description"):
                try:
                    pet_descriptions = json.loads(lease_dict["pet_description"])
                    response_dict["pets"] = [{"type": p.get("pet_type"), "breed": p.get("breed"), "name": p.get("pet_name"), "weight": p.get("weight"), "isEmotionalSupport": False} for p in pet_descriptions]
                except:
                    response_dict["pets"] = []
            else:
                response_dict["pets"] = []
        
        # Convert Timestamp dates to date objects for Pydantic
        if "lease_start" in lease_dict and lease_dict["lease_start"] is not None:
            response_dict["lease_start"] = pd.Timestamp(lease_dict["lease_start"]).date() if isinstance(lease_dict["lease_start"], pd.Timestamp) else lease_dict["lease_start"]
        if "lease_end" in lease_dict and lease_dict["lease_end"] is not None:
            response_dict["lease_end"] = pd.Timestamp(lease_dict["lease_end"]).date() if isinstance(lease_dict["lease_end"], pd.Timestamp) else lease_dict["lease_end"]
        if "lease_date" in lease_dict and lease_dict["lease_date"] is not None:
            response_dict["lease_date"] = pd.Timestamp(lease_dict["lease_date"]).date() if isinstance(lease_dict["lease_date"], pd.Timestamp) else lease_dict["lease_date"]
        
        # Get PDF URL if exists (guard against NaN)
        pdf_doc_id = lease_dict.get("generated_pdf_document_id")
        if isinstance(pdf_doc_id, float) and pd.isna(pdf_doc_id):
            pdf_doc_id = None
        if pdf_doc_id:
            response_dict["pdf_url"] = adls_service.get_blob_download_url(str(pdf_doc_id))
            latex_blob = str(pdf_doc_id).replace('.pdf', '.tex')
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
        
        # Build response
        build_start = time.time()
        lease_items = []
        for _, lease in leases_df.iterrows():
            try:
                # Get property summary (pass the already-loaded properties_df to avoid re-reading)
                property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"), properties_df)
                
                # Get tenants from JSON column (guard against NaN)
                tenants_json = lease.get("tenants")
                if isinstance(tenants_json, float) and pd.isna(tenants_json):
                    tenants_json = None
                lease_tenants = _deserialize_tenants(tenants_json) if tenants_json else []
                # Set lease_id on all tenant responses
                for tenant_resp in lease_tenants:
                    tenant_resp.lease_id = UUID(lease["id"])
                tenant_list = [
                    {"first_name": t.first_name, "last_name": t.last_name}
                    for t in lease_tenants
                ]
                
                # Get PDF URL if exists (guard against NaN - NaN is truthy!)
                pdf_url = None
                pdf_doc_id = lease.get("generated_pdf_document_id")
                if pdf_doc_id is not None and not (isinstance(pdf_doc_id, float) and pd.isna(pdf_doc_id)):
                    pdf_url = adls_service.get_blob_download_url(str(pdf_doc_id))
                
                # Handle dates - similar to get_lease
                lease_start = lease.get("lease_start")
                lease_end = lease.get("lease_end")
                
                if lease_start and pd.notna(lease_start):
                    lease_start_date = pd.Timestamp(lease_start).date()
                else:
                    # Default to today if missing
                    lease_start_date = date.today()
                
                if lease_end and pd.notna(lease_end):
                    lease_end_date = pd.Timestamp(lease_end).date()
                else:
                    # Default to lease_start + 1 year if missing
                    lease_end_date = lease_start_date + pd.Timedelta(days=365)
                
                # Ensure lease_end >= lease_start (fix invalid data)
                if lease_end_date < lease_start_date:
                    logger.warning(f"Lease {lease['id']} has invalid dates: lease_end ({lease_end_date}) < lease_start ({lease_start_date}). Setting lease_end = lease_start.")
                    lease_end_date = lease_start_date
                
                # Guard unit_id against NaN
                unit_id_val = lease.get("unit_id")
                if isinstance(unit_id_val, float) and pd.isna(unit_id_val):
                    unit_id_val = None

                # Guard status against NaN
                status_val = lease.get("status", "draft")
                if isinstance(status_val, float) and pd.isna(status_val):
                    status_val = "draft"

                lease_items.append(LeaseListItem(
                    id=UUID(lease["id"]),
                    property_id=UUID(lease["property_id"]),
                    unit_id=UUID(str(unit_id_val)) if unit_id_val else None,
                    lease_number=int(lease.get("lease_number", 0) if pd.notna(lease.get("lease_number", 0)) else 0),
                    property=PropertySummary(**property_summary),
                    tenants=tenant_list,
                    lease_start=lease_start_date,
                    lease_end=lease_end_date,
                    monthly_rent=Decimal(str(lease["monthly_rent"])),
                    status=status_val,
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
        if lease.get("is_active") is False or (pd.notna(lease.get("is_active")) and not lease.get("is_active", True)):
            raise HTTPException(status_code=404, detail="Lease not found")
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
        # Get property summary
        property_summary = _get_property_summary(lease["property_id"], lease.get("unit_id"))
        
        # Get tenants from JSON column
        tenants_json = lease.get("tenants")
        tenant_responses = _deserialize_tenants(tenants_json) if tenants_json else []
        # Set lease_id on all tenant responses
        for tenant_resp in tenant_responses:
            tenant_resp.lease_id = lease_id
        
        # Get PDF and LaTeX URLs if they exist (guard against NaN)
        pdf_url = None
        latex_url = None
        pdf_doc_id = lease.get("generated_pdf_document_id")
        if isinstance(pdf_doc_id, float) and pd.isna(pdf_doc_id):
            pdf_doc_id = None
        if pdf_doc_id:
            pdf_blob = str(pdf_doc_id)
            latex_blob = pdf_blob.replace('.pdf', '.tex')
            
            if adls_service.blob_exists(pdf_blob):
                pdf_url = adls_service.get_blob_download_url(pdf_blob)
            if adls_service.blob_exists(latex_blob):
                latex_url = adls_service.get_blob_download_url(latex_blob)
        
        # Build response
        response_dict = lease.to_dict()
        
        # Replace NaN values with None (guard against non-scalar types like lists/dicts)
        for key, value in response_dict.items():
            try:
                if isinstance(value, float) and pd.isna(value):
                    response_dict[key] = None
            except (TypeError, ValueError):
                pass  # Non-scalar (list, dict) - leave as-is
        
        response_dict["id"] = UUID(lease["id"])
        response_dict["user_id"] = UUID(user_id)  # Get from current_user, not from lease (since user_id is removed from schema)
        response_dict["property_id"] = UUID(lease["property_id"])
        unit_id_val = response_dict.get("unit_id")
        response_dict["unit_id"] = UUID(str(unit_id_val)) if unit_id_val else None
        # Handle lease_number - default to 0 if missing (for existing leases created before this field was added)
        response_dict["lease_number"] = int(lease.get("lease_number", 0)) if lease.get("lease_number") is not None and not pd.isna(lease.get("lease_number")) else 0
        response_dict["property"] = PropertySummary(**property_summary)
        response_dict["tenants"] = tenant_responses
        # Deserialize moveout_costs from JSON (like tenants) - use response_dict (NaN already cleaned)
        moveout_costs_json = response_dict.get("moveout_costs")
        response_dict["moveout_costs"] = _deserialize_moveout_costs(moveout_costs_json) if moveout_costs_json and isinstance(moveout_costs_json, str) else []
        
        # Deserialize pets from JSON (like tenants) - use response_dict (NaN already cleaned)
        pets_json = response_dict.get("pets")
        if pets_json and isinstance(pets_json, str):
            response_dict["pets"] = _deserialize_pets(pets_json)
        elif response_dict.get("pet_description") and isinstance(response_dict.get("pet_description"), str):
            # Fallback to old pet_description format for backward compatibility
            try:
                pet_descriptions = json.loads(lease["pet_description"])
                response_dict["pets"] = [{"type": p.get("pet_type"), "breed": p.get("breed"), "name": p.get("pet_name"), "weight": p.get("weight"), "isEmotionalSupport": False} for p in pet_descriptions]
            except:
                response_dict["pets"] = []
        else:
            response_dict["pets"] = []
        response_dict["pdf_url"] = pdf_url
        response_dict["latex_url"] = latex_url
        
        # Convert dates - handle potential None/NaN values
        lease_start = lease.get("lease_start")
        lease_end = lease.get("lease_end")
        
        if lease_start and pd.notna(lease_start):
            response_dict["lease_start"] = pd.Timestamp(lease_start).date()
        else:
            # Default to today if missing
            response_dict["lease_start"] = date.today()
            
        if lease_end and pd.notna(lease_end):
            response_dict["lease_end"] = pd.Timestamp(lease_end).date()
        else:
            # Default to lease_start + 1 year if missing
            response_dict["lease_end"] = response_dict["lease_start"] + pd.Timedelta(days=365)
        
        # Ensure lease_end >= lease_start (fix invalid data)
        if response_dict["lease_end"] < response_dict["lease_start"]:
            logger.warning(f"Lease {lease_id} has invalid dates: lease_end ({response_dict['lease_end']}) < lease_start ({response_dict['lease_start']}). Setting lease_end = lease_start.")
            response_dict["lease_end"] = response_dict["lease_start"]
        
        response_dict["lease_date"] = pd.Timestamp(lease["lease_date"]).date() if lease.get("lease_date") and pd.notna(lease.get("lease_date")) else None
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
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
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
        
        # Get tenants from JSON column
        tenants_json = lease.get("tenants")
        lease_tenants = _deserialize_tenants(tenants_json) if tenants_json else []
        tenants = [
            {
                "first_name": t.first_name,
                "last_name": t.last_name,
                "email": t.email,
                "phone": t.phone
            }
            for t in lease_tenants
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
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
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
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
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
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
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
        logger.info(f"Hard deleted all rows for lease {lease_id} (tenants are stored in JSON column, so no separate deletion needed)")
        
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
        
        lease = lease_row.iloc[0]
        
        # Verify ownership via property
        _verify_property_ownership(lease["property_id"], user_id)
        
        # Get tenants from JSON column
        tenants_json = lease.get("tenants")
        tenant_responses = _deserialize_tenants(tenants_json) if tenants_json else []
        # Set lease_id on all tenant responses
        for tenant_resp in tenant_responses:
            tenant_resp.lease_id = lease_id
        
        return tenant_responses
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing tenants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing tenants: {str(e)}")

