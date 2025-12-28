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
            "id": str(row["id"]),
            # Denormalized fields
            "user_id": str(row["user_id"]) if pd.notna(row.get("user_id")) else None,
            "user_name": str(row["user_name"]) if pd.notna(row.get("user_name")) else None,
            "property_id": str(row["property_id"]),
            "property_name": str(row["property_name"]) if pd.notna(row.get("property_name")) else None,
            "unit_id": str(row["unit_id"]) if pd.notna(row.get("unit_id")) else None,
            "unit_name": str(row["unit_name"]) if pd.notna(row.get("unit_name")) else None,
            "tenant_id": str(row["tenant_id"]) if pd.notna(row.get("tenant_id")) else None,
            "tenant_name": str(row["tenant_name"]) if pd.notna(row.get("tenant_name")) else None,
            # Revenue classification
            "revenue_description": str(row["revenue_description"]) if pd.notna(row.get("revenue_description")) else None,
            "is_non_irs_revenue": bool(row["is_non_irs_revenue"]) if pd.notna(row.get("is_non_irs_revenue")) else False,
            # Rent period
            "is_one_time_fee": bool(row["is_one_time_fee"]) if pd.notna(row.get("is_one_time_fee")) else False,
            "rent_period_month": int(row["rent_period_month"]) if pd.notna(row.get("rent_period_month")) else None,
            "rent_period_year": int(row["rent_period_year"]) if pd.notna(row.get("rent_period_year")) else None,
            "rent_period_start": safe_date_str(row.get("rent_period_start")),
            "rent_period_end": safe_date_str(row.get("rent_period_end")),
            # Payment details
            "amount": float(row["amount"]) if pd.notna(row.get("amount")) else 0,
            "payment_date": safe_date_str(row.get("payment_date")),
            "payment_method": str(row["payment_method"]) if pd.notna(row.get("payment_method")) else None,
            "transaction_reference": str(row["transaction_reference"]) if pd.notna(row.get("transaction_reference")) else None,
            "is_late": bool(row["is_late"]) if pd.notna(row.get("is_late")) else False,
            "late_fee": float(row["late_fee"]) if pd.notna(row.get("late_fee")) else None,
            "notes": str(row["notes"]) if pd.notna(row.get("notes")) else None,
            "document_storage_id": str(row["document_storage_id"]) if pd.notna(row.get("document_storage_id")) else None,
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
    """Create a new rent payment record with denormalized fields for speed"""
    try:
        user_id = current_user["sub"]
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or None
        rent_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
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
        
        # Create rent record with denormalized fields
        rent_dict = {
            "id": rent_id,
            "user_id": user_id,
            "user_name": user_name,
            "property_id": str(rent_data.property_id),
            "property_name": property_name,
            "unit_id": str(rent_data.unit_id) if rent_data.unit_id else None,
            "unit_name": unit_name,
            "tenant_id": str(rent_data.tenant_id) if rent_data.tenant_id else None,
            "tenant_name": tenant_name,
            "revenue_description": revenue_description,
            "is_non_irs_revenue": is_non_irs_revenue,
            "is_one_time_fee": is_one_time_fee,
            "amount": Decimal(str(rent_data.amount)),
            "rent_period_month": rent_period_month,
            "rent_period_year": rent_period_year,
            "rent_period_start": parse_date_midday(period_start),
            "rent_period_end": parse_date_midday(period_end),
            "payment_date": parse_date_midday(rent_data.payment_date),
            "payment_method": rent_data.payment_method if rent_data.payment_method else None,
            "transaction_reference": rent_data.transaction_reference,
            "is_late": rent_data.is_late if rent_data.is_late else False,
            "late_fee": Decimal(str(rent_data.late_fee)) if rent_data.late_fee else None,
            "notes": rent_data.notes,
            "document_storage_id": str(rent_data.document_storage_id) if rent_data.document_storage_id else None,
            "created_at": now,
            "updated_at": now,
        }
        
        # Log the rent_dict being saved
        logger.info(f"💾 Saving rent payment with rent_period_year={rent_period_year}, rent_period_month={rent_period_month}")
        logger.debug(f"Full rent_dict: {rent_dict}")
        
        # Append to Iceberg table
        df = pd.DataFrame([rent_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created rent payment {rent_id} for property {rent_data.property_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(rent_data.property_id, user_id, rent_data.unit_id)
        
        return RentResponse(
            id=UUID(rent_id),
            user_id=UUID(user_id),
            user_name=user_name,
            property_id=rent_data.property_id,
            property_name=property_name,
            unit_id=rent_data.unit_id,
            unit_name=unit_name,
            tenant_id=rent_data.tenant_id,
            tenant_name=tenant_name,
            revenue_description=revenue_description,
            is_non_irs_revenue=is_non_irs_revenue,
            is_one_time_fee=is_one_time_fee,
            amount=rent_data.amount,
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
            document_storage_id=rent_data.document_storage_id if hasattr(rent_data, 'document_storage_id') else None,
        )
        
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
    property_id: Optional[UUID] = Query(None, description="Filter by property ID"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    year: Optional[int] = Query(None, description="Filter by rent period year"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List rent payments for the current user"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            return RentListResponse(items=[], total=0, page=1, limit=limit)
        
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Filter by user
        df = df[df["user_id"] == user_id]
        
        # Apply filters
        if property_id:
            df = df[df["property_id"] == str(property_id)]
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
    """Get a rent payment by ID"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        df = read_table(NAMESPACE, TABLE_NAME)
        rent_rows = df[(df["id"] == str(rent_id)) & (df["user_id"] == user_id)]
        
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
    """Update an existing rent payment record"""
    try:
        user_id = current_user["sub"]
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or None
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        # Get existing rent record
        df = read_table(NAMESPACE, TABLE_NAME)
        rent_rows = df[(df["id"] == str(rent_id)) & (df["user_id"] == user_id)]
        
        if len(rent_rows) == 0:
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        existing_rent = rent_rows.iloc[0]
        now = pd.Timestamp.now()
        
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
                period_start = existing_rent["rent_period_start"]
                period_end = existing_rent["rent_period_start"]
            rent_period_month = None
            rent_period_year = None
        else:
            if rent_data.rent_period_start and rent_data.rent_period_end:
                period_start = rent_data.rent_period_start
                period_end = rent_data.rent_period_end
            elif rent_data.rent_period_month and rent_data.rent_period_year:
                period_start, period_end = get_rent_period_dates(rent_data.rent_period_year, rent_data.rent_period_month)
            else:
                period_start = existing_rent["rent_period_start"]
                period_end = existing_rent["rent_period_end"]
            rent_period_month = rent_data.rent_period_month if rent_data.rent_period_month is not None else existing_rent.get("rent_period_month")
            rent_period_year = rent_data.rent_period_year if rent_data.rent_period_year is not None else existing_rent.get("rent_period_year")
        
        # Build update dict with all fields
        update_dict = {
            "id": str(rent_id),
            "user_id": user_id,
            "user_name": user_name,
            "property_id": property_id,
            "property_name": property_name,
            "unit_id": unit_id,
            "unit_name": unit_name,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "revenue_description": revenue_description,
            "is_non_irs_revenue": is_non_irs_revenue,
            "is_one_time_fee": is_one_time_fee,
            "amount": Decimal(str(rent_data.amount)) if rent_data.amount is not None else Decimal(str(existing_rent["amount"])),
            "rent_period_month": rent_period_month,
            "rent_period_year": rent_period_year,
            "rent_period_start": parse_date_midday(period_start),
            "rent_period_end": parse_date_midday(period_end),
            "payment_date": parse_date_midday(rent_data.payment_date) if rent_data.payment_date else parse_date_midday(existing_rent["payment_date"]),
            "payment_method": rent_data.payment_method if rent_data.payment_method is not None else existing_rent.get("payment_method"),
            "transaction_reference": rent_data.transaction_reference if rent_data.transaction_reference is not None else existing_rent.get("transaction_reference"),
            "is_late": rent_data.is_late if rent_data.is_late is not None else existing_rent.get("is_late", False),
            "late_fee": Decimal(str(rent_data.late_fee)) if rent_data.late_fee is not None else (Decimal(str(existing_rent["late_fee"])) if pd.notna(existing_rent.get("late_fee")) else None),
            "notes": rent_data.notes if rent_data.notes is not None else existing_rent.get("notes"),
            "document_storage_id": str(rent_data.document_storage_id) if rent_data.document_storage_id is not None else (str(existing_rent.get("document_storage_id")) if pd.notna(existing_rent.get("document_storage_id")) else None),
            "created_at": existing_rent.get("created_at"),
            "updated_at": now,
            "created_by_user_id": existing_rent.get("created_by_user_id"),
        }
        
        # Upsert the updated record
        df_update = pd.DataFrame([update_dict])
        upsert_data(NAMESPACE, TABLE_NAME, df_update)
        
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
    """Delete a rent payment"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, TABLE_NAME):
            raise HTTPException(status_code=404, detail="Rent payment not found")
        
        df = read_table(NAMESPACE, TABLE_NAME)
        
        # Check if rent exists and belongs to user
        rent_rows = df[(df["id"] == str(rent_id)) & (df["user_id"] == user_id)]
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
