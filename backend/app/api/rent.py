"""API routes for rent payment management"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from uuid import UUID
import uuid
from datetime import date
from calendar import monthrange
from decimal import Decimal
import pandas as pd

from app.core.dependencies import get_current_user
from app.schemas.rent import (
    RentCreate, RentUpdate, RentResponse, RentListResponse
)
from app.core.iceberg import read_table, append_data, table_exists, load_table
from app.core.logging import get_logger

NAMESPACE = ("investflow",)
TABLE_NAME = "rents"

router = APIRouter(prefix="/rent", tags=["rent"])
logger = get_logger(__name__)


def _invalidate_financial_performance_cache(property_id: UUID, unit_id: Optional[UUID] = None):
    """Helper to invalidate financial performance cache after rent changes"""
    try:
        from app.services.financial_performance_service import financial_performance_service
        financial_performance_service.invalidate_cache(property_id, unit_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate financial performance cache: {e}")


def get_rent_period_dates(year: int, month: int) -> tuple[date, date]:
    """Get start and end dates for a rent period (month)"""
    start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end = date(year, month, last_day)
    return start, end


def rent_to_response(row: pd.Series) -> dict:
    """Convert a DataFrame row to a RentResponse dict"""
    return {
        "id": str(row["id"]),
        "property_id": str(row["property_id"]),
        "unit_id": str(row["unit_id"]) if pd.notna(row.get("unit_id")) else None,
        "client_id": str(row["client_id"]) if pd.notna(row.get("client_id")) else None,
        "amount": float(row["amount"]) if pd.notna(row.get("amount")) else 0,
        "rent_period_month": int(row["rent_period_month"]) if pd.notna(row.get("rent_period_month")) else 1,
        "rent_period_year": int(row["rent_period_year"]) if pd.notna(row.get("rent_period_year")) else 2024,
        "rent_period_start": str(row["rent_period_start"]) if pd.notna(row.get("rent_period_start")) else None,
        "rent_period_end": str(row["rent_period_end"]) if pd.notna(row.get("rent_period_end")) else None,
        "payment_date": str(row["payment_date"]) if pd.notna(row.get("payment_date")) else None,
        "payment_method": str(row["payment_method"]) if pd.notna(row.get("payment_method")) else None,
        "transaction_reference": str(row["transaction_reference"]) if pd.notna(row.get("transaction_reference")) else None,
        "is_late": bool(row["is_late"]) if pd.notna(row.get("is_late")) else False,
        "late_fee": float(row["late_fee"]) if pd.notna(row.get("late_fee")) else None,
        "notes": str(row["notes"]) if pd.notna(row.get("notes")) else None,
        "created_at": str(row["created_at"]) if pd.notna(row.get("created_at")) else None,
        "updated_at": str(row["updated_at"]) if pd.notna(row.get("updated_at")) else None,
    }


@router.post("", response_model=RentResponse, status_code=201)
async def create_rent_endpoint(
    rent_data: RentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new rent payment record"""
    try:
        user_id = current_user["sub"]
        rent_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Calculate rent period start/end from month/year
        period_start, period_end = get_rent_period_dates(
            rent_data.rent_period_year, 
            rent_data.rent_period_month
        )
        
        # Create rent record
        rent_dict = {
            "id": rent_id,
            "user_id": user_id,
            "property_id": str(rent_data.property_id),
            "unit_id": str(rent_data.unit_id) if rent_data.unit_id else None,
            "client_id": str(rent_data.client_id) if rent_data.client_id else None,
            "amount": Decimal(str(rent_data.amount)),
            "rent_period_month": rent_data.rent_period_month,
            "rent_period_year": rent_data.rent_period_year,
            "rent_period_start": pd.Timestamp(period_start),
            "rent_period_end": pd.Timestamp(period_end),
            "payment_date": pd.Timestamp(rent_data.payment_date),
            "payment_method": rent_data.payment_method if rent_data.payment_method else None,
            "transaction_reference": rent_data.transaction_reference,
            "is_late": rent_data.is_late if rent_data.is_late else False,
            "late_fee": Decimal(str(rent_data.late_fee)) if rent_data.late_fee else None,
            "notes": rent_data.notes,
            "created_at": now,
            "updated_at": now,
        }
        
        # Append to Iceberg table
        df = pd.DataFrame([rent_dict])
        append_data(NAMESPACE, TABLE_NAME, df)
        
        logger.info(f"Created rent payment {rent_id} for property {rent_data.property_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(rent_data.property_id, rent_data.unit_id)
        
        return RentResponse(
            id=rent_id,
            property_id=str(rent_data.property_id),
            unit_id=str(rent_data.unit_id) if rent_data.unit_id else None,
            client_id=str(rent_data.client_id) if rent_data.client_id else None,
            amount=float(rent_data.amount),
            rent_period_month=rent_data.rent_period_month,
            rent_period_year=rent_data.rent_period_year,
            rent_period_start=str(period_start),
            rent_period_end=str(period_end),
            payment_date=str(rent_data.payment_date),
            payment_method=rent_data.payment_method,
            transaction_reference=rent_data.transaction_reference,
            is_late=rent_data.is_late if rent_data.is_late else False,
            late_fee=float(rent_data.late_fee) if rent_data.late_fee else None,
            notes=rent_data.notes,
        )
        
    except Exception as e:
        logger.error(f"Error creating rent payment: {e}", exc_info=True)
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
            df = df[df["rent_period_year"] == year]
        
        total = len(df)
        
        # Sort by payment date descending
        if "payment_date" in df.columns and len(df) > 0:
            df = df.sort_values("payment_date", ascending=False)
        
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
        
        # Filter out the rent to delete
        df = df[df["id"] != str(rent_id)]
        
        # Overwrite the table
        table = load_table(NAMESPACE, TABLE_NAME)
        table.overwrite(df)
        
        logger.info(f"Deleted rent payment {rent_id}")
        
        # Invalidate financial performance cache
        _invalidate_financial_performance_cache(property_id, unit_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rent payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
