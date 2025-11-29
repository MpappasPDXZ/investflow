"""Pydantic schemas for unit-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class UnitBase(BaseModel):
    """Base unit schema with common fields"""
    unit_number: str = Field(..., max_length=50, description="Unit number (e.g., 'Unit 1', '1A', 'Apt 201')")
    bedrooms: Optional[int] = Field(None, ge=0, description="Number of bedrooms")
    bathrooms: Optional[float] = Field(None, ge=0, description="Number of bathrooms")
    square_feet: Optional[int] = Field(None, ge=0, description="Square footage")
    current_monthly_rent: Optional[float] = Field(None, ge=0, description="Current monthly rent")
    notes: Optional[str] = Field(None, description="Additional notes")


class UnitCreate(UnitBase):
    """Schema for creating a unit"""
    property_id: str = Field(..., description="Parent property ID")


class UnitUpdate(BaseModel):
    """Schema for updating a unit"""
    unit_number: Optional[str] = Field(None, max_length=50)
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[float] = Field(None, ge=0)
    square_feet: Optional[int] = Field(None, ge=0)
    current_monthly_rent: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class UnitResponse(UnitBase):
    """Schema for unit response"""
    id: str
    property_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UnitListResponse(BaseModel):
    """Schema for unit list response"""
    items: List[UnitResponse]
    total: int

