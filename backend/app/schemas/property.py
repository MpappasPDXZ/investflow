"""Pydantic schemas for property-related API requests and responses"""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, Any
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal

from app.core.coerce import to_int_required, to_int_or_none


class PropertyBase(BaseModel):
    """
    Base property schema with fields ordered to match Iceberg schema column order.
    Fields are grouped by type: string, int64, float64, date32, decimal128, bool, timestamp
    """
    # STRING fields (in Iceberg order)
    display_name: Optional[str] = Field(None, max_length=255, description="Property display name")
    property_status: Optional[Literal["own", "evaluating", "rehabbing", "listed_for_rent", "listed_for_sale", "sold", "rented", "hide"]] = Field(
        default="evaluating",
        description="Property status"
    )
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    property_type: Optional[str] = Field(
        None, 
        max_length=50,
        description="Property type: 'single_family', 'multi_family', 'condo', 'townhouse'"
    )
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # INT64 fields (in Iceberg order)
    purchase_price: int = Field(..., ge=0, description="Property purchase price in dollars (int64)")
    down_payment: Optional[int] = Field(None, ge=0, description="Down payment amount in dollars (int64)")
    cash_invested: Optional[int] = Field(None, ge=0, description="Total cash invested in dollars (int64)")
    current_market_value: Optional[int] = Field(None, ge=0, description="Current estimated market value in dollars (int64)")
    unit_count: Optional[int] = Field(None, ge=0, description="Number of units (int64)")
    bedrooms: Optional[int] = Field(None, ge=0, description="Number of bedrooms (int64)")
    square_feet: Optional[int] = Field(None, ge=0, description="Square footage (int64)")
    year_built: Optional[int] = Field(None, ge=1800, le=2100, description="Year built (int64)")
    
    # FLOAT64 fields (in Iceberg order)
    vacancy_rate: float = Field(
        default=0.07,
        ge=0.0,
        le=1.0,
        description="Expected vacancy rate as float (e.g., 0.07 for 7%) (float64)"
    )
    bathrooms: Optional[float] = Field(None, ge=0.0, description="Number of bathrooms (float64)")
    current_monthly_rent: Optional[float] = Field(None, ge=0.0, description="Current monthly rent (float64)")
    
    # DATE32 fields (in Iceberg order)
    purchase_date: Optional[date] = Field(
        default=None,
        description="Date property was purchased (date32)"
    )
    
    # DECIMAL128 fields (in Iceberg order)
    monthly_rent_to_income_ratio: Optional[Decimal] = Field(
        default=Decimal("2.75"), 
        ge=0, 
        description="Default ratio: annual income / (rent x 12) must be >= this value (decimal128)"
    )
    
    # BOOL fields (in Iceberg order)
    has_units: Optional[bool] = Field(False, description="True for multi-family/duplex properties")


class PropertyCreate(PropertyBase):
    """Schema for creating a new property"""
    pass  # user_id will be added from authenticated user


class PropertyUpdate(BaseModel):
    """Schema for updating a property - fields ordered to match exact Iceberg schema order"""
    # Order matches Iceberg schema exactly (excluding id, user_id, created_at, updated_at):
    display_name: Optional[str] = Field(None, max_length=255)
    property_status: Optional[Literal["own", "evaluating", "rehabbing", "listed_for_rent", "listed_for_sale", "sold", "rented", "hide"]] = None
    purchase_date: Optional[date] = None
    monthly_rent_to_income_ratio: Optional[Decimal] = Field(None, ge=0)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    property_type: Optional[str] = Field(None, max_length=50)
    has_units: Optional[bool] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    purchase_price: Optional[int] = Field(None, ge=0)
    square_feet: Optional[int] = Field(None, ge=0)
    down_payment: Optional[int] = Field(None, ge=0)
    cash_invested: Optional[int] = Field(None, ge=0)
    current_market_value: Optional[int] = Field(None, ge=0)
    vacancy_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    unit_count: Optional[int] = Field(None, ge=0)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[float] = Field(None, ge=0.0)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)
    current_monthly_rent: Optional[float] = Field(None, ge=0.0)


class PropertyResponse(PropertyBase):
    """
    Schema for property response - includes system fields in Iceberg order.
    Coerces int64 fields only (Decimal/numpy -> int) so endpoints can pass row dicts.
    """
    # System fields (in Iceberg order - these come after PropertyBase fields)
    id: UUID  # string in Iceberg
    user_id: UUID  # string in Iceberg
    is_active: bool  # bool in Iceberg
    created_at: datetime  # timestamp in Iceberg
    updated_at: datetime  # timestamp in Iceberg

    @model_validator(mode="before")
    @classmethod
    def coerce_int64_fields(cls, data: Any) -> Any:
        """Only coerce int fields from Decimal/float/numpy. Everything else unchanged."""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if "purchase_price" in d:
            d["purchase_price"] = to_int_required(d["purchase_price"])
        for key in ("down_payment", "cash_invested", "current_market_value", "unit_count", "bedrooms", "square_feet", "year_built"):
            if key in d:
                d[key] = to_int_or_none(d[key])
        return d

    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    """Schema for paginated property list response"""
    items: list[PropertyResponse]
    total: int
    page: int
    limit: int

