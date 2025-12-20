"""Pydantic schemas for property-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


class PropertyBase(BaseModel):
    """Base property schema with common fields"""
    display_name: Optional[str] = Field(None, max_length=255, description="Property display name")
    purchase_price: Decimal = Field(..., ge=0, description="Property purchase price")
    purchase_date: Optional[datetime] = Field(
        default=datetime(2024, 10, 23),
        description="Date property was purchased"
    )
    down_payment: Optional[Decimal] = Field(None, ge=0, description="Down payment amount")
    cash_invested: Optional[Decimal] = Field(None, ge=0, description="Total cash invested (manual entry for CoC)")
    current_market_value: Optional[Decimal] = Field(None, ge=0, description="Current estimated market value")
    property_status: Optional[Literal["own", "evaluating", "rehabbing", "listed_for_rent", "listed_for_sale", "sold", "hide"]] = Field(
        default="evaluating",
        description="Property status"
    )
    vacancy_rate: Decimal = Field(
        default=Decimal("0.07"),
        ge=0,
        le=1,
        description="Expected vacancy rate as decimal (e.g., 0.07 for 7%)"
    )
    monthly_rent_to_income_ratio: Decimal = Field(
        default=Decimal("2.75"), 
        ge=0, 
        description="Default ratio: annual income / (rent x 12) must be >= this value"
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
    has_units: Optional[bool] = Field(False, description="True for multi-family/duplex properties")
    unit_count: Optional[int] = Field(None, ge=0, description="Number of units")
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[Decimal] = Field(None, ge=0)
    square_feet: Optional[int] = Field(None, ge=0)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)
    current_monthly_rent: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = Field(None, description="Additional notes")


class PropertyCreate(PropertyBase):
    """Schema for creating a new property"""
    pass  # user_id will be added from authenticated user


class PropertyUpdate(BaseModel):
    """Schema for updating a property"""
    display_name: Optional[str] = Field(None, max_length=255)
    purchase_price: Optional[Decimal] = Field(None, ge=0)
    purchase_date: Optional[datetime] = None
    down_payment: Optional[Decimal] = Field(None, ge=0)
    cash_invested: Optional[Decimal] = Field(None, ge=0)
    current_market_value: Optional[Decimal] = Field(None, ge=0)
    property_status: Optional[Literal["own", "evaluating", "rehabbing", "listed_for_rent", "listed_for_sale", "sold", "hide"]] = None
    vacancy_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    monthly_rent_to_income_ratio: Optional[Decimal] = Field(None, ge=0)
    address_line1: Optional[str] = Field(None, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=20)
    property_type: Optional[str] = Field(None, max_length=50)
    has_units: Optional[bool] = None
    unit_count: Optional[int] = Field(None, ge=0)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[Decimal] = Field(None, ge=0)
    square_feet: Optional[int] = Field(None, ge=0)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)
    current_monthly_rent: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PropertyResponse(PropertyBase):
    """Schema for property response"""
    id: UUID
    user_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertyListResponse(BaseModel):
    """Schema for paginated property list response"""
    items: list[PropertyResponse]
    total: int
    page: int
    limit: int

