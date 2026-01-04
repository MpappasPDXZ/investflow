"""API routes for rent payment management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Union
from uuid import UUID
import uuid
from datetime import date, datetime, time
from calendar import monthrange
from decimal import Decimal
import pandas as pd

from app.core.dependencies import get_current_user
from app.schemas.rent import (
    RentCreate, RentUpdate, RentResponse, RentListResponse
)
from app.core.iceberg import read_table, append_data, table_exists, load_table, read_table_filtered, upsert_data
from pyiceberg.expressions import EqualTo
from app.core.logging import get_logger
from app.services.document_service import document_service
from fastapi import UploadFile, File, Form

NAMESPACE = ("investflow",)
TABLE_NAME = "rents"

router = APIRouter(prefix="/rent", tags=["rent"])
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



def _invalidate_financial_performance_cache(property_id: UUID, user_id: str, unit_id: Optional[UUID] = None):
    """Helper to invalidate financial performance cache after rent changes (async, non-blocking)"""
    try:
        import asyncio
        from app.services.financial_performance_service import financial_performance_service
        # Fire and forget - don't block rent operations
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    asyncio.to_thread(
                        financial_performance_service.invalidate_cache,
                        property_id,
                        UUID(user_id),  # Convert string to UUID
                        unit_id
                    )
                )
            else:
                # If no loop is running, just run it synchronously but log warning
                logger.warning("No running event loop, invalidating cache synchronously")
                financial_performance_service.invalidate_cache(property_id, UUID(user_id), unit_id)
        except RuntimeError:
            # No event loop, fall back to synchronous
            logger.warning("Could not create async task, invalidating cache synchronously")
            financial_performance_service.invalidate_cache(property_id, UUID(user_id), unit_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate financial performance cache: {e}")


def build_rent_dict(
    rent_id: str,
    property_id: str,
    property_name: Optional[str],
    unit_id: Optional[str],
    unit_name: Optional[str],
    tenant_id: Optional[str],
    tenant_name: Optional[str],
    revenue_description: Optional[str],
    is_non_irs_revenue: bool,
    is_one_time_fee: bool,
    amount: Decimal,
    rent_period_month: Optional[int],
    rent_period_year: Optional[int],
    rent_period_start: date,
    rent_period_end: date,
    payment_date: date,
    payment_method: Optional[str],
    transaction_reference: Optional[str],
    is_late: bool,
    late_fee: Optional[Decimal],
    notes: Optional[str],
    document_storage_id: Optional[str],
    now: pd.Timestamp,
    existing_rent: Optional[pd.Series] = None,
    is_update: bool = False,
    created_by_user_id: Optional[str] = None
) -> dict:
    """
    Build rent dict for create or update operations (ordered by dtype to match Iceberg schema).
    
    Args:
        existing_rent: Optional existing rent record (for updates)
        is_update: If True, preserve created_at/created_by_user_id from existing_rent
        created_by_user_id: User ID who created/updated the record
    """
    rent_dict = {
        # STRING fields (in Iceberg order)
        "id": str(rent_id),
        "property_id": str(property_id),
        "property_name": property_name,
        "unit_id": str(unit_id) if unit_id else None,
        "unit_name": unit_name,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "tenant_name": tenant_name,
        "revenue_description": revenue_description,
        "payment_method": payment_method if payment_method else None,
        "transaction_reference": transaction_reference,
        "notes": notes,
        "document_storage_id": document_storage_id,
        "created_by_user_id": created_by_user_id,
        
        # DECIMAL128 fields (in Iceberg order)
        "amount": amount,
        "late_fee": Decimal(str(late_fee)) if late_fee else None,
        
        # INT32 fields (in Iceberg order)
        "rent_period_month": rent_period_month,
        "rent_period_year": rent_period_year,
        
        # DATE32 fields (in Iceberg order)
        "rent_period_start": parse_date_midday(rent_period_start),
        "rent_period_end": parse_date_midday(rent_period_end),
        "payment_date": parse_date_midday(payment_date),
        
        # BOOLEAN fields (in Iceberg order)
        "is_non_irs_revenue": is_non_irs_revenue,
        "is_one_time_fee": is_one_time_fee,
        "is_late": is_late if is_late else False,
        
        # TIMESTAMP fields (in Iceberg order)
        "updated_at": now,
    }
    
    if is_update and existing_rent is not None:
        # Preserve created_at and created_by_user_id for updates
        rent_dict["created_at"] = existing_rent.get("created_at")
        if "created_by_user_id" in existing_rent and pd.notna(existing_rent.get("created_by_user_id")):
            rent_dict["created_by_user_id"] = str(existing_rent.get("created_by_user_id"))
    else:
        # Set new timestamps for creates
        rent_dict["created_at"] = now
    
    return rent_dict


def prepare_rent_dataframe(rent_dict: dict) -> pd.DataFrame:
    """
    Prepare DataFrame for rent data with correct types to match table schema.
    This ensures required fields are not optional and types match exactly.
    Uses explicit dtype specification to prevent pandas from inferring optional types.
    """
    # Create DataFrame with explicit dtype=object to prevent type inference
    # Then we'll explicitly convert each column to the correct type
    df = pd.DataFrame([rent_dict], dtype=object)
    
    # Ensure required string fields are strings and not None
    required_string_fields = ["id", "property_id"]
    for field in required_string_fields:
        if field in df.columns:
            # Convert to string, ensuring no None values
            df[field] = df[field].astype(str)
            if df[field].isna().any() or (df[field] == 'None').any() or (df[field] == 'nan').any():
                raise ValueError(f"Required field {field} cannot be None")
    
    # Ensure required date fields are not None (already pd.Timestamp from parse_date_midday)
    required_date_fields = ["rent_period_start", "rent_period_end", "payment_date"]
    for field in required_date_fields:
        if field in df.columns:
            if df[field].isna().any():
                raise ValueError(f"Required field {field} cannot be None")
    
    # Ensure required decimal field is Decimal and not None
    if "amount" in df.columns:
        if df["amount"].isna().any():
            raise ValueError("Required field amount cannot be None")
        # Convert to Decimal explicitly
        df["amount"] = df["amount"].apply(lambda x: Decimal(str(x)) if pd.notna(x) and x is not None else None)
        if df["amount"].isna().any():
            raise ValueError("Required field amount cannot be None after conversion")
    
    # Convert nullable integer fields to Int32 (not Int64/long) - schema expects int32
    # Use pd.to_numeric first to handle any string/int conversions, then Int32
    if "rent_period_month" in df.columns:
        df["rent_period_month"] = pd.to_numeric(df["rent_period_month"], errors='coerce').astype("Int32")
    if "rent_period_year" in df.columns:
        df["rent_period_year"] = pd.to_numeric(df["rent_period_year"], errors='coerce').astype("Int32")
    
    # Ensure optional string fields are strings (not object/unknown)
    optional_string_fields = ["property_name", "unit_id", "unit_name", "tenant_id", 
                             "tenant_name", "revenue_description", "payment_method", 
                             "transaction_reference", "notes", "document_storage_id", "created_by_user_id"]
    for field in optional_string_fields:
        if field in df.columns:
            # Convert None/NaN to None, otherwise to string
            df[field] = df[field].apply(lambda x: str(x) if pd.notna(x) and x is not None and str(x) != 'nan' else None)
    
    # Ensure boolean fields are booleans
    boolean_fields = ["is_non_irs_revenue", "is_one_time_fee", "is_late"]
    for field in boolean_fields:
        if field in df.columns:
            df[field] = df[field].astype(bool)
    
    # Ensure optional Decimal field is Decimal
    if "late_fee" in df.columns:
        df["late_fee"] = df["late_fee"].apply(lambda x: Decimal(str(x)) if pd.notna(x) and x is not None else None)
    
    return df


def get_rent_period_dates(year: int, month: int) -> tuple[date, date]:
    """Get start and end dates for a rent period (month)"""
    start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end = date(year, month, last_day)
    return start, end


def rent_to_response(row: pd.Series) -> dict:
    """Convert a DataFrame row to a RentResponse dict with denormalized fields"""
    try:
        # Helper to safely convert dates to strings
        def safe_date_str(value):
            if pd.isna(value):
                return None
            if isinstance(value, pd.Timestamp):
                return value.strftime("%Y-%m-%d")
            if isinstance(value, (datetime, date)):
                return value.strftime("%Y-%m-%d")
            return str(value)
        
        return {
            # STRING fields (in Iceberg order)
            "id": str(row["id"]),
            "property_id": str(row["property_id"]),
            "property_name": str(row["property_name"]) if pd.notna(row.get("property_name")) else None,
            "unit_id": str(row["unit_id"]) if pd.notna(row.get("unit_id")) else None,
            "unit_name": str(row["unit_name"]) if pd.notna(row.get("unit_name")) else None,
            "tenant_id": str(row["tenant_id"]) if pd.notna(row.get("tenant_id")) else None,
            "tenant_name": str(row["tenant_name"]) if pd.notna(row.get("tenant_name")) else None,
            "revenue_description": str(row["revenue_description"]) if pd.notna(row.get("revenue_description")) else None,
            "payment_method": str(row["payment_method"]) if pd.notna(row.get("payment_method")) else None,
            "transaction_reference": str(row["transaction_reference"]) if pd.notna(row.get("transaction_reference")) else None,
            "notes": str(row["notes"]) if pd.notna(row.get("notes")) else None,
            "document_storage_id": str(row["document_storage_id"]) if pd.notna(row.get("document_storage_id")) else None,
            "created_by_user_id": str(row["created_by_user_id"]) if pd.notna(row.get("created_by_user_id")) else None,
            
            # DECIMAL128 fields (in Iceberg order)
            "amount": float(row["amount"]) if pd.notna(row.get("amount")) else 0,
            "late_fee": float(row["late_fee"]) if pd.notna(row.get("late_fee")) else None,
            
            # INT32 fields (in Iceberg order)
            "rent_period_month": int(row["rent_period_month"]) if pd.notna(row.get("rent_period_month")) else None,
            "rent_period_year": int(row["rent_period_year"]) if pd.notna(row.get("rent_period_year")) else None,
            
            # DATE32 fields (in Iceberg order)
            "rent_period_start": safe_date_str(row.get("rent_period_start")),
            "rent_period_end": safe_date_str(row.get("rent_period_end")),
            "payment_date": safe_date_str(row.get("payment_date")),
            
            # BOOLEAN fields (in Iceberg order)
            "is_non_irs_revenue": bool(row["is_non_irs_revenue"]) if pd.notna(row.get("is_non_irs_revenue")) else False,
            "is_one_time_fee": bool(row["is_one_time_fee"]) if pd.notna(row.get("is_one_time_fee")) else False,
            "is_late": bool(row["is_late"]) if pd.notna(row.get("is_late")) else False,
            
            # TIMESTAMP fields (in Iceberg order)
            "created_at": safe_date_str(row.get("created_at")),
            "updated_at": safe_date_str(row.get("updated_at")),
        }
    except Exception as e:
        logger.error(f"Error converting rent row to response: {e}, row: {row.to_dict()}", exc_info=True)
        raise


@router.post("", response_model=RentResponse, status_code=201)
async def create_rent_endpoint(
    rent_data: RentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new rent payment record (property_id required, secured by property_id)"""
    try:
        user_id = current_user["sub"]  # For created_by_user_id only
        rent_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Validate required fields
        if not rent_data.property_id:
            raise HTTPException(status_code=400, detail="property_id is required")
        if not rent_data.amount or rent_data.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be greater than 0")
        if not rent_data.payment_date:
            raise HTTPException(status_code=400, detail="payment_date is required")
        
        # Calculate rent period start/end
        is_one_time_fee = rent_data.is_one_time_fee if hasattr(rent_data, 'is_one_time_fee') else False
        
        if is_one_time_fee:
            # For one-time fees, use a single date (rent_period_start)
            if rent_data.rent_period_start:
                period_start = rent_data.rent_period_start
                period_end = rent_data.rent_period_start  # Same date for one-time fees
            else:
                # Default to payment date if not provided
                period_start = rent_data.payment_date
                period_end = rent_data.payment_date
            rent_period_month = None
            rent_period_year = None
        else:
            # For regular rent, calculate from month/year or use provided dates
            if rent_data.rent_period_start and rent_data.rent_period_end:
                period_start = rent_data.rent_period_start
                period_end = rent_data.rent_period_end
            else:
                if not rent_data.rent_period_month or not rent_data.rent_period_year:
                    raise HTTPException(status_code=400, detail="rent_period_month and rent_period_year are required for non-one-time fees")
                period_start, period_end = get_rent_period_dates(
                    rent_data.rent_period_year, 
                    rent_data.rent_period_month
                )
            rent_period_month = rent_data.rent_period_month
            rent_period_year = rent_data.rent_period_year
        
        # Fetch denormalized property name
        property_name = None
        try:
            if table_exists(NAMESPACE, "properties"):
                properties_df = read_table_filtered(
                    NAMESPACE,
                    "properties",
                    EqualTo("id", str(rent_data.property_id))
                )
                if len(properties_df) > 0:
                    prop = properties_df.iloc[0]
                    property_name = prop.get("display_name") or prop.get("address_line1") or None
        except Exception as e:
            logger.warning(f"Could not fetch property name: {e}")
        
        # Fetch denormalized unit name
        unit_name = None
        if rent_data.unit_id:
            try:
                if table_exists(NAMESPACE, "units"):
                    units_df = read_table_filtered(
                        NAMESPACE,
                        "units",
                        EqualTo("id", str(rent_data.unit_id))
                    )
                    if len(units_df) > 0:
                        unit_name = units_df.iloc[0].get("unit_number") or None
            except Exception as e:
                logger.warning(f"Could not fetch unit name: {e}")
        
        # Fetch denormalized tenant name
        tenant_name = None
        if rent_data.tenant_id:
            try:
                if table_exists(NAMESPACE, "tenants"):
                    tenants_df = read_table_filtered(
                        NAMESPACE,
                        "tenants",
                        EqualTo("id", str(rent_data.tenant_id))
                    )
                    if len(tenants_df) > 0:
                        tenant = tenants_df.iloc[0]
                        tenant_name = tenant.get("name") or f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}".strip() or None
            except Exception as e:
                logger.warning(f"Could not fetch tenant name: {e}")
        
        # Auto-check is_non_irs_revenue if revenue_description is "Deposit", "Deposit Payout", or "Exit Deposit Deduction"
        revenue_description = rent_data.revenue_description if hasattr(rent_data, 'revenue_description') else None
        is_non_irs_revenue = rent_data.is_non_irs_revenue if hasattr(rent_data, 'is_non_irs_revenue') else False
        if revenue_description in ("Deposit", "Deposit Payout", "Exit Deposit Deduction"):
            is_non_irs_revenue = True
        
        # Create rent record with denormalized fields using shared helper
        rent_dict = build_rent_dict(
            rent_id=rent_id,
            property_id=str(rent_data.property_id),
            property_name=property_name,
            unit_id=str(rent_data.unit_id) if rent_data.unit_id else None,
            unit_name=unit_name,
            tenant_id=str(rent_data.tenant_id) if rent_data.tenant_id else None,
            tenant_name=tenant_name,
            revenue_description=revenue_description,
            is_non_irs_revenue=is_non_irs_revenue,
            is_one_time_fee=is_one_time_fee,
            amount=Decimal(str(rent_data.amount)),
            rent_period_month=rent_period_month,
            rent_period_year=rent_period_year,
            rent_period_start=period_start,
            rent_period_end=period_end,
            payment_date=rent_data.payment_date,
            payment_method=rent_data.payment_method,
            transaction_reference=rent_data.transaction_reference,
            is_late=rent_data.is_late if rent_data.is_late else False,
            late_fee=rent_data.late_fee,
            notes=rent_data.notes,
            document_storage_id=str(rent_data.document_storage_id) if rent_data.document_storage_id else None,
            now=now,
            is_update=False,
            created_by_user_id=str(user_id)
        )
        
        # Log the rent_dict being saved
        logger.info(f"💾 Saving rent payment with rent_period_year={rent_period_year}, rent_period_month={rent_period_month}")
        logger.debug(f"Full rent_dict: {rent_dict}")
        
        # Prepare DataFrame with correct types (shared helper)
        df = prepare_rent_dataframe(rent_dict)
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created rent payment {rent_id} for property {rent_data.property_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(rent_data.property_id, user_id, rent_data.unit_id)
        
        # Fetch the created rent to return proper response
        created_rent = read_table_filtered(NAMESPACE, TABLE_NAME, EqualTo("id", rent_id))
        if len(created_rent) == 0:
            raise HTTPException(status_code=500, detail="Failed to retrieve created rent payment")
        
        return RentResponse(**rent_to_response(created_rent.iloc[0]))
        
    except Exception as e:
        logger.error(f"Error creating rent payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/with-receipt", response_model=RentResponse, status_code=201)
async def create_rent_with_receipt(
    property_id: UUID = Form(...),
    unit_id: Optional[str] = Form(None),
    tenant_id: Optional[str] = Form(None),
    amount: str = Form(...),
    revenue_description: Optional[str] = Form(None),
    is_non_irs_revenue: bool = Form(False),
    is_one_time_fee: bool = Form(False),
    rent_period_month: Optional[int] = Form(None),
    rent_period_year: Optional[int] = Form(None),
    rent_period_start: Optional[str] = Form(None),
    rent_period_end: Optional[str] = Form(None),
    payment_date: str = Form(...),
    payment_method: Optional[str] = Form(None),
    transaction_reference: Optional[str] = Form(None),
    is_late: bool = Form(False),
    late_fee: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    document_type: Optional[str] = Form("receipt"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Create a new rent payment with receipt/image upload"""
    try:
        user_id = UUID(current_user["sub"])
        
        # Upload document first
        file_content = await file.read()
        document = document_service.upload_document(
            user_id=user_id,
            file_content=file_content,
            filename=file.filename or "receipt",
            content_type=file.content_type or "application/octet-stream",
            document_type=document_type or "receipt",
            property_id=property_id,
            unit_id=UUID(unit_id) if unit_id else None,
            tenant_id=UUID(tenant_id) if tenant_id else None
        )
        
        # Create rent with document_storage_id
        rent_data = RentCreate(
            property_id=property_id,
            unit_id=UUID(unit_id) if unit_id else None,
            tenant_id=UUID(tenant_id) if tenant_id else None,
            amount=Decimal(amount),
            revenue_description=revenue_description,
            is_non_irs_revenue=is_non_irs_revenue,
            is_one_time_fee=is_one_time_fee,
            rent_period_month=rent_period_month,
            rent_period_year=rent_period_year,
            rent_period_start=datetime.fromisoformat(rent_period_start).date() if rent_period_start else None,
            rent_period_end=datetime.fromisoformat(rent_period_end).date() if rent_period_end else None,
            payment_date=datetime.fromisoformat(payment_date).date(),
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            is_late=is_late,
            late_fee=Decimal(late_fee) if late_fee else None,
            notes=notes,
            document_storage_id=UUID(document["id"])
        )
        
        # Use the existing create logic
        return await create_rent_endpoint(rent_data, current_user)
        
    except Exception as e:
        logger.error(f"Error creating rent payment with receipt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=RentListResponse)
async def list_rents_endpoint(
    property_id: UUID = Query(..., description="Filter by property ID (required)"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    year: Optional[int] = Query(None, description="Filter by rent period year"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List rent payments for a property (property_id required)"""
    try:
        if not table_exists(NAMESPACE, TABLE_NAME):
            return RentListResponse(items=[], total=0, page=1, limit=limit)
        
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by property_id (required)
        df = df[df["property_id"] == str(property_id)]
        
        # Apply additional filters
        if unit_id:
            df = df[df["unit_id"] == str(unit_id)]
        if year:
            # Filter by year - deposits (one-time fees) have None for rent_period_year, so exclude them
            # Only include rows where rent_period_year matches the filter year
            df = df[df["rent_period_year"].notna() & (df["rent_period_year"] == year)]
        
        total = len(df)
        
        # Sort by payment date descending (handle None values)
        if "payment_date" in df.columns and len(df) > 0:
            # Fill NaN payment dates with a very old date for sorting purposes
            df = df.copy()
            df["payment_date"] = df["payment_date"].fillna(pd.Timestamp.min)
            df = df.sort_values("payment_date", ascending=False)
            # Restore NaN values after sorting
            df["payment_date"] = df["payment_date"].replace(pd.Timestamp.min, pd.NaT)
        
        # Pagination
        df = df.iloc[skip:skip + limit]
        
        # Convert to response
        items = [RentResponse(**rent_to_response(row)) for _, row in df.iterrows()]
        
        return RentListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Error listing rent payments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rent_id}", response_model=RentResponse)
async def get_rent_endpoint(
    rent_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a rent payment by ID (secured by property_id)"""
    try:
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        df = read_table(NAMESPACE, TABLE_NAME)
        rent_rows = df[df["id"] == str(rent_id)]
        
        if len(rent_rows) == 0:
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        rent = rent_rows.iloc[0]
        return RentResponse(**rent_to_response(rent))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rent payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{rent_id}", response_model=RentResponse)
async def update_rent_endpoint(
    rent_id: UUID,
    rent_data: RentUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing rent payment record (secured by property_id)"""
    try:
        user_id = current_user["sub"]  # For created_by_user_id tracking only
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        # Get existing rent record
        df = read_table(NAMESPACE, TABLE_NAME)
        rent_rows = df[df["id"] == str(rent_id)]
        
        if len(rent_rows) == 0:
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        # Validate property_id if provided in update
        if rent_data.property_id:
            existing_property_id = str(rent_rows.iloc[0]["property_id"])
            if str(rent_data.property_id) != existing_property_id:
                raise HTTPException(status_code=400, detail="Cannot change property_id on update")
        
        existing_rent = rent_rows.iloc[0]
        now = pd.Timestamp.now()
        
        # Validate update data
        if rent_data.amount is not None and rent_data.amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be greater than 0")
        if rent_data.late_fee is not None and rent_data.late_fee < 0:
            raise HTTPException(status_code=400, detail="late_fee cannot be negative")
        
        # Use existing values if not provided in update
        property_id = str(rent_data.property_id) if rent_data.property_id else existing_rent["property_id"]
        unit_id = str(rent_data.unit_id) if rent_data.unit_id else (existing_rent.get("unit_id") if pd.notna(existing_rent.get("unit_id")) else None)
        tenant_id = str(rent_data.tenant_id) if rent_data.tenant_id else (existing_rent.get("tenant_id") if pd.notna(existing_rent.get("tenant_id")) else None)
        
        # Fetch denormalized property name if property changed
        property_name = existing_rent.get("property_name")
        if rent_data.property_id and str(rent_data.property_id) != existing_rent["property_id"]:
            try:
                if table_exists(NAMESPACE, "properties"):
                    properties_df = read_table_filtered(NAMESPACE, "properties", EqualTo("id", property_id))
                    if len(properties_df) > 0:
                        prop = properties_df.iloc[0]
                        property_name = prop.get("display_name") or prop.get("address_line1") or None
            except Exception as e:
                logger.warning(f"Could not fetch property name: {e}")
        
        # Fetch denormalized unit name if unit changed
        unit_name = existing_rent.get("unit_name")
        if rent_data.unit_id and unit_id != existing_rent.get("unit_id"):
            try:
                if table_exists(NAMESPACE, "units"):
                    units_df = read_table_filtered(NAMESPACE, "units", EqualTo("id", unit_id))
                    if len(units_df) > 0:
                        unit_name = units_df.iloc[0].get("unit_number") or None
            except Exception as e:
                logger.warning(f"Could not fetch unit name: {e}")
        
        # Fetch denormalized tenant name if tenant changed
        tenant_name = existing_rent.get("tenant_name")
        if rent_data.tenant_id and tenant_id != existing_rent.get("tenant_id"):
            try:
                if table_exists(NAMESPACE, "tenants"):
                    tenants_df = read_table_filtered(NAMESPACE, "tenants", EqualTo("id", tenant_id))
                    if len(tenants_df) > 0:
                        tenant = tenants_df.iloc[0]
                        tenant_name = tenant.get("name") or f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}".strip() or None
            except Exception as e:
                logger.warning(f"Could not fetch tenant name: {e}")
        
        # Handle revenue description and non-IRS revenue
        revenue_description = rent_data.revenue_description if rent_data.revenue_description is not None else existing_rent.get("revenue_description")
        is_non_irs_revenue = rent_data.is_non_irs_revenue if rent_data.is_non_irs_revenue is not None else existing_rent.get("is_non_irs_revenue", False)
        # Auto-check is_non_irs_revenue if revenue_description is "Deposit", "Deposit Payout", or "Exit Deposit Deduction"
        if revenue_description in ("Deposit", "Deposit Payout", "Exit Deposit Deduction"):
            is_non_irs_revenue = True
        
        # Handle one-time fee and rent period
        is_one_time_fee = rent_data.is_one_time_fee if rent_data.is_one_time_fee is not None else existing_rent.get("is_one_time_fee", False)
        
        if is_one_time_fee:
            if rent_data.rent_period_start:
                period_start = rent_data.rent_period_start
                period_end = rent_data.rent_period_start
            else:
                # Get existing dates, handling pandas Timestamps
                existing_start = existing_rent.get("rent_period_start")
                if pd.notna(existing_start):
                    if isinstance(existing_start, pd.Timestamp):
                        period_start = existing_start.date()
                    elif isinstance(existing_start, (datetime, date)):
                        period_start = existing_start.date() if isinstance(existing_start, datetime) else existing_start
                    elif isinstance(existing_start, str):
                        period_start = datetime.fromisoformat(existing_start.split('T')[0]).date()
                    else:
                        period_start = existing_start
                    period_end = period_start
                else:
                    # Fallback to payment_date if rent_period_start is missing
                    payment_dt = existing_rent.get("payment_date")
                    if pd.notna(payment_dt):
                        if isinstance(payment_dt, pd.Timestamp):
                            period_start = payment_dt.date()
                        elif isinstance(payment_dt, (datetime, date)):
                            period_start = payment_dt.date() if isinstance(payment_dt, datetime) else payment_dt
                        elif isinstance(payment_dt, str):
                            period_start = datetime.fromisoformat(payment_dt.split('T')[0]).date()
                        else:
                            period_start = payment_dt
                    else:
                        period_start = date.today()
                    period_end = period_start
            rent_period_month = None
            rent_period_year = None
        else:
            if rent_data.rent_period_start and rent_data.rent_period_end:
                period_start = rent_data.rent_period_start
                period_end = rent_data.rent_period_end
            elif rent_data.rent_period_month and rent_data.rent_period_year:
                period_start, period_end = get_rent_period_dates(rent_data.rent_period_year, rent_data.rent_period_month)
            else:
                # Get existing dates, handling pandas Timestamps
                existing_start = existing_rent.get("rent_period_start")
                existing_end = existing_rent.get("rent_period_end")
                
                if pd.notna(existing_start):
                    if isinstance(existing_start, pd.Timestamp):
                        period_start = existing_start.date()
                    elif isinstance(existing_start, (datetime, date)):
                        period_start = existing_start.date() if isinstance(existing_start, datetime) else existing_start
                    elif isinstance(existing_start, str):
                        period_start = datetime.fromisoformat(existing_start.split('T')[0]).date()
                    else:
                        period_start = existing_start
                else:
                    # Fallback - shouldn't happen but handle gracefully
                    period_start = date.today()
                
                if pd.notna(existing_end):
                    if isinstance(existing_end, pd.Timestamp):
                        period_end = existing_end.date()
                    elif isinstance(existing_end, (datetime, date)):
                        period_end = existing_end.date() if isinstance(existing_end, datetime) else existing_end
                    elif isinstance(existing_end, str):
                        period_end = datetime.fromisoformat(existing_end.split('T')[0]).date()
                    else:
                        period_end = existing_end
                else:
                    # Fallback - shouldn't happen but handle gracefully
                    period_end = date.today()
            
            rent_period_month = rent_data.rent_period_month if rent_data.rent_period_month is not None else (int(existing_rent.get("rent_period_month")) if pd.notna(existing_rent.get("rent_period_month")) else None)
            rent_period_year = rent_data.rent_period_year if rent_data.rent_period_year is not None else (int(existing_rent.get("rent_period_year")) if pd.notna(existing_rent.get("rent_period_year")) else None)
        
        # Ensure required fields are present and correctly typed
        # Get existing values for required fields if not provided
        existing_property_id = str(existing_rent.get("property_id", ""))
        existing_amount = Decimal(str(existing_rent["amount"])) if pd.notna(existing_rent.get("amount")) else Decimal("0")
        existing_payment_date = existing_rent.get("payment_date")
        if pd.notna(existing_payment_date):
            if isinstance(existing_payment_date, pd.Timestamp):
                existing_payment_date = existing_payment_date.date()
            elif isinstance(existing_payment_date, (datetime, date)):
                existing_payment_date = existing_payment_date.date() if isinstance(existing_payment_date, datetime) else existing_payment_date
            elif isinstance(existing_payment_date, str):
                existing_payment_date = datetime.fromisoformat(existing_payment_date.split('T')[0]).date()
        
        # Build update dict using shared helper - handle fallbacks to existing values
        # Handle document_storage_id deletion (empty string sentinel)
        doc_storage_id = None
        if rent_data.document_storage_id == "":  # Empty string = delete
            doc_storage_id = None
        elif rent_data.document_storage_id is not None:
            doc_storage_id = str(rent_data.document_storage_id)
        elif pd.notna(existing_rent.get("document_storage_id")):
            doc_storage_id = str(existing_rent.get("document_storage_id"))
        
        # Get existing created_by_user_id or use current user
        existing_created_by_user_id = existing_rent.get("created_by_user_id")
        if pd.notna(existing_created_by_user_id):
            created_by_user_id = str(existing_created_by_user_id)
        else:
            created_by_user_id = str(user_id)
        
        update_dict = build_rent_dict(
            rent_id=str(rent_id),
            property_id=str(property_id) if property_id else str(existing_property_id),
            property_name=property_name if property_name is not None else existing_rent.get("property_name"),
            unit_id=str(unit_id) if unit_id else (str(existing_rent.get("unit_id")) if pd.notna(existing_rent.get("unit_id")) else None),
            unit_name=unit_name if unit_name is not None else existing_rent.get("unit_name"),
            tenant_id=str(tenant_id) if tenant_id else (str(existing_rent.get("tenant_id")) if pd.notna(existing_rent.get("tenant_id")) else None),
            tenant_name=tenant_name if tenant_name is not None else existing_rent.get("tenant_name"),
            revenue_description=revenue_description if revenue_description is not None else existing_rent.get("revenue_description"),
            is_non_irs_revenue=is_non_irs_revenue if is_non_irs_revenue is not None else (bool(existing_rent.get("is_non_irs_revenue")) if pd.notna(existing_rent.get("is_non_irs_revenue")) else False),
            is_one_time_fee=is_one_time_fee if is_one_time_fee is not None else (bool(existing_rent.get("is_one_time_fee")) if pd.notna(existing_rent.get("is_one_time_fee")) else False),
            amount=Decimal(str(rent_data.amount)) if rent_data.amount is not None else existing_amount,
            rent_period_month=rent_period_month,
            rent_period_year=rent_period_year,
            rent_period_start=period_start,
            rent_period_end=period_end,
            payment_date=rent_data.payment_date if rent_data.payment_date else existing_payment_date,
            payment_method=rent_data.payment_method if rent_data.payment_method is not None else existing_rent.get("payment_method"),
            transaction_reference=rent_data.transaction_reference if rent_data.transaction_reference is not None else existing_rent.get("transaction_reference"),
            is_late=rent_data.is_late if rent_data.is_late is not None else (bool(existing_rent.get("is_late")) if pd.notna(existing_rent.get("is_late")) else False),
            late_fee=rent_data.late_fee if rent_data.late_fee is not None else (existing_rent.get("late_fee") if pd.notna(existing_rent.get("late_fee")) else None),
            notes=rent_data.notes if rent_data.notes is not None else existing_rent.get("notes"),
            document_storage_id=doc_storage_id,
            now=now,
            existing_rent=existing_rent,
            is_update=True,
            created_by_user_id=created_by_user_id
        )
        
        # Update the record using delete + append pattern (like expenses) to avoid pandas type inference issues
        # Get table reference
        table = load_table(NAMESPACE, TABLE_NAME)
        schema = table.schema().as_arrow()
        
        # Delete existing record
        table.delete(EqualTo("id", str(rent_id)))
        
        # Convert dates/timestamps to proper Python types for PyArrow
        import pyarrow as pa
        
        # Convert date fields (pa.date32()) from pd.Timestamp to date objects
        for key in ["rent_period_start", "rent_period_end", "payment_date"]:
            if key in update_dict and isinstance(update_dict[key], pd.Timestamp):
                update_dict[key] = update_dict[key].date()
            elif key in update_dict and isinstance(update_dict[key], datetime):
                update_dict[key] = update_dict[key].date()
        
        # Convert timestamp fields (pa.timestamp("us")) from pd.Timestamp to datetime objects
        for key in ["created_at", "updated_at"]:
            if key in update_dict and isinstance(update_dict[key], pd.Timestamp):
                update_dict[key] = update_dict[key].to_pydatetime()
        
        # Ensure Decimal fields are Decimal (not float)
        for key in ["amount", "late_fee"]:
            if key in update_dict and update_dict[key] is not None:
                if not isinstance(update_dict[key], Decimal):
                    update_dict[key] = Decimal(str(update_dict[key]))
        
        # Ensure integer fields are int (not long)
        for key in ["rent_period_month", "rent_period_year"]:
            if key in update_dict and update_dict[key] is not None:
                if not isinstance(update_dict[key], int):
                    update_dict[key] = int(update_dict[key])
        
        # Create PyArrow table directly from dict with schema (avoids pandas type inference)
        arrow_table = pa.Table.from_pylist([update_dict], schema=schema)
        table.append(arrow_table)
        
        logger.info(f"Updated rent payment {rent_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(UUID(property_id), user_id, UUID(unit_id) if unit_id else None)
        
        # Return updated rent
        updated_rent = read_table_filtered(NAMESPACE, TABLE_NAME, EqualTo("id", str(rent_id)))
        if len(updated_rent) == 0:
            raise HTTPException(status_code=404, detail="Rent payment not found after update")
        
        return RentResponse(**rent_to_response(updated_rent.iloc[0]))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rent payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rent_id}", status_code=204)
async def delete_rent_endpoint(
    rent_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete a rent payment (secured by property_id)"""
    try:
        user_id = current_user["sub"]  # For cache invalidation only
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Check if rent exists
        rent_rows = df[df["id"] == str(rent_id)]
        if len(rent_rows) == 0:
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        # Get property_id and unit_id before deletion for cache invalidation
        rent_row = rent_rows.iloc[0]
        property_id = UUID(rent_row['property_id'])
        unit_id = UUID(rent_row['unit_id']) if pd.notna(rent_row.get('unit_id')) else None
        
        # Use Iceberg's delete for proper deletion
        table = load_table(NAMESPACE, TABLE_NAME)
        table.delete(EqualTo("id", str(rent_id)))
        
        logger.info(f"Deleted rent payment {rent_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(property_id, user_id, unit_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rent payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
