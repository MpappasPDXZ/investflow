"""Pydantic schemas for unit-related API requests and responses"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class UnitBase(BaseModel):
    """
    Base unit schema with fields ordered to match Iceberg schema column order.
    Fields are grouped by type: string, int64, float64, bool, timestamp
    """
    # STRING fields (in Iceberg order)
    unit_number: str = Field(..., max_length=50, description="Unit number (e.g., 'Unit 1', '1A', 'Apt 201')")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # INT64 fields (in Iceberg order)
    bedrooms: Optional[int] = Field(None, ge=0, description="Number of bedrooms (int64)")
    square_feet: Optional[int] = Field(None, ge=0, description="Square footage (int64)")
    
    # FLOAT64 fields (in Iceberg order)
    bathrooms: Optional[float] = Field(None, ge=0.0, description="Number of bathrooms (float64)")
    current_monthly_rent: Optional[float] = Field(None, ge=0.0, description="Current monthly rent (float64)")
    
    # BOOL fields (in Iceberg order)
    is_active: Optional[bool] = Field(True, description="Whether unit is active")


class UnitCreate(UnitBase):
    """Schema for creating a unit"""
    property_id: str = Field(..., description="Parent property ID")


class UnitUpdate(BaseModel):
    """Schema for updating a unit - fields ordered by Iceberg type"""
    # STRING fields
    unit_number: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    
    # INT64 fields
    bedrooms: Optional[int] = Field(None, ge=0)
    square_feet: Optional[int] = Field(None, ge=0)
    
    # FLOAT64 fields
    bathrooms: Optional[float] = Field(None, ge=0.0)
    current_monthly_rent: Optional[float] = Field(None, ge=0.0)
    
    # BOOL fields
    is_active: Optional[bool] = None


class UnitResponse(UnitBase):
    """
    Schema for unit response - includes system fields in Iceberg order.
    Fields ordered: UnitBase fields + id, property_id (string), is_active (bool), created_at, updated_at (timestamp)
    """
    # System fields (in Iceberg order - these come after UnitBase fields)
    id: str  # string in Iceberg
    property_id: str  # string in Iceberg
    is_active: bool  # bool in Iceberg
    created_at: datetime  # timestamp in Iceberg
    updated_at: datetime  # timestamp in Iceberg

    class Config:
        from_attributes = True


class UnitListResponse(BaseModel):
    """Schema for unit list response"""
    items: List[UnitResponse]
    total: int

